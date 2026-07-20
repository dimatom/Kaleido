from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .models import KnowledgeRepository, Document, ChatSession, ChatMessageHistory
from . import task_store
from rest_framework import serializers
from django.http import FileResponse, Http404, StreamingHttpResponse
from .rag_core import RAGCore
from Kaleido.logger import logger
import os
import uuid


class KnowledgeRepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeRepository
        fields = ['id', 'name', 'desc', 'system_prompt', 'image', 'creator', 'createdon', 'modifiedon']
        read_only_fields = ['id', 'creator', 'createdon', 'modifiedon']


class KnowledgeRepositoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class KnowledgeRepositoryListView(APIView):
    def get(self, request):
        queryset = KnowledgeRepository.objects.filter(
            creator=request.user
        ).order_by('-createdon')
        paginator = KnowledgeRepositoryPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = KnowledgeRepositorySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class KnowledgeRepositoryDetailView(APIView):
    def get(self, request, pk):
        try:
            repo = KnowledgeRepository.objects.get(pk=pk, creator=request.user)
        except KnowledgeRepository.DoesNotExist:
            return Response(
                {'error': '知识库不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = KnowledgeRepositorySerializer(repo)
        return Response(serializer.data)


class KnowledgeRepositoryCreateUpdateView(APIView):
    def post(self, request):
        repo_id = request.data.get('id')
        if repo_id:
            try:
                repo = KnowledgeRepository.objects.get(pk=repo_id, creator=request.user)
            except KnowledgeRepository.DoesNotExist:
                return Response(
                    {'error': '知识库不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )
            serializer = KnowledgeRepositorySerializer(repo, data=request.data, partial=True)
        else:
            serializer = KnowledgeRepositorySerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(creator=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK if repo_id else status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class KnowledgeRepositoryDeleteView(APIView):
    def post(self, request, pk):
        if task_store.km_has_running_task(str(pk)) or \
           Document.objects.filter(dim_knowledge_repository_id=pk, parse_status='parsing').exists():
            return Response(
                {'error': '该知识库有正在进行的解析任务，请等待任务完成后再删除'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            repo = KnowledgeRepository.objects.get(pk=pk, creator=request.user)
            rag = RAGCore(str(pk))
            rag.delete_collection()
        except KnowledgeRepository.DoesNotExist:
            return Response(
                {'error': '知识库不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        repo.delete()
        return Response(
            {'message': '删除成功'},
            status=status.HTTP_200_OK
        )


# ==================== Document 接口 ====================

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'dim_knowledge_repository_id', 'name', 'type', 'mime_type', 'size', 'chunk', 'parse_status', 'creator', 'createdon', 'modifiedon']
        read_only_fields = ['id', 'creator', 'createdon', 'modifiedon']


class DocumentPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class DocumentListView(APIView):
    def get(self, request):
        knowledge_id = request.query_params.get('knowledge_id')
        search = request.query_params.get('search', '')

        queryset = Document.objects.filter(
            dim_knowledge_repository_id__creator=request.user
        )

        if knowledge_id:
            queryset = queryset.filter(dim_knowledge_repository_id_id=knowledge_id)

        if search:
            queryset = queryset.filter(name__icontains=search)

        queryset = queryset.order_by('-createdon')
        paginator = DocumentPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = DocumentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class DocumentUploadView(APIView):
    def post(self, request):
        knowledge_id = request.data.get('knowledge_repository_id')
        if not knowledge_id:
            return Response(
                {'error': '知识库ID不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            repo = KnowledgeRepository.objects.get(pk=knowledge_id, creator=request.user)
        except KnowledgeRepository.DoesNotExist:
            return Response(
                {'error': '知识库不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': '请选择要上传的文件'},
                status=status.HTTP_400_BAD_REQUEST
            )

        doc = Document.objects.create(
            dim_knowledge_repository_id=repo,
            filedata=file,
            creator=request.user
        )

        serializer = DocumentSerializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    def get(self, request, pk):
        try:
            doc = Document.objects.get(pk=pk, dim_knowledge_repository_id__creator=request.user)
        except Document.DoesNotExist:
            raise Http404('文件不存在')

        if not doc.filedata:
            raise Http404('文件不存在')

        try:
            response = FileResponse(doc.filedata.open('rb'))
            response['Content-Disposition'] = f'attachment; filename="{doc.name}"'
            response['Content-Type'] = doc.mime_type or 'application/octet-stream'
            return response
        except FileNotFoundError:
            raise Http404('文件不存在')


class DocumentDeleteView(APIView):
    def post(self, request, pk):
        if task_store.doc_has_running_task(str(pk)):
            return Response(
                {'error': '该文档正在解析中，请等待任务完成后再删除'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            doc = Document.objects.get(pk=pk, dim_knowledge_repository_id__creator=request.user)
            knowledge_repo_id = doc.dim_knowledge_repository_id_id
            rag = RAGCore(str(knowledge_repo_id))
            rag.delete_document([str(pk)])
        except Document.DoesNotExist:
            return Response(
                {'error': '文件不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        doc.delete()
        return Response(
            {'message': '删除成功'},
            status=status.HTTP_200_OK
        )


class DocumentParseView(APIView):
    def post(self, request):
        document_ids = request.data.get('document_ids', [])
        if not document_ids:
            return Response(
                {'error': '请提供文档ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        documents = Document.objects.filter(
            pk__in=document_ids,
            dim_knowledge_repository_id__creator=request.user
        )

        if not documents.exists():
            return Response(
                {'error': '未找到匹配的文档'},
                status=status.HTTP_404_NOT_FOUND
            )

        knowledge_repo_id = documents.first().dim_knowledge_repository_id_id
        rag = RAGCore(str(knowledge_repo_id))

        document_list = []
        for doc in documents:
            document_list.append({
                "path": doc.filedata.path,
                "metadata": {
                    "document_id": str(doc.id)
                }
            })

        parse_result = rag.parse_document(document_list)

        for item in parse_result:
            doc_id = item.get('document_id')
            chunk_count = item.get('chunk_count')
            if doc_id and chunk_count is not None:
                Document.objects.filter(pk=doc_id).update(chunk=chunk_count, parse_status='parsed')

        # 标记未能成功解析的文档为失败状态
        parsed_ids = {item.get('document_id') for item in parse_result if item.get('document_id')}
        failed_ids = [str(doc.id) for doc in documents if str(doc.id) not in parsed_ids]
        if failed_ids:
            Document.objects.filter(pk__in=failed_ids).update(parse_status='failed')

        return Response(
            {'message': f'成功解析 {len(documents)} 个文档'},
            status=status.HTTP_200_OK
        )


class DocumentParseTaskView(APIView):
    """创建文档解析异步任务"""

    def post(self, request):
        document_ids = request.data.get('document_ids', [])
        if not document_ids:
            return Response(
                {'error': '请提供文档ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        documents = Document.objects.filter(
            pk__in=document_ids,
            dim_knowledge_repository_id__creator=request.user
        )

        if not documents.exists():
            return Response(
                {'error': '未找到匹配的文档'},
                status=status.HTTP_404_NOT_FOUND
            )

        km_ids = {str(k) for k in documents.values_list('dim_knowledge_repository_id_id', flat=True)}
        if len(km_ids) > 1:
            return Response(
                {'error': '所选文档必须属于同一知识库'},
                status=status.HTTP_400_BAD_REQUEST
            )

        doc_ids = [str(d.id) for d in documents]

        # 校验是否有文档正在解析中（Redis 实时 + DB 兜底）
        conflict_ids = task_store.docs_running_conflict(doc_ids)
        if conflict_ids:
            return Response(
                {'error': f'有 {len(conflict_ids)} 个所选文档正在解析中，请稍后再试'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 校验所有选中文档是否均为未解析或者失败状态
        if documents.filter(parse_status__in=['unparsed', 'failed']).count() != len(doc_ids):
            return Response(
                {'error': '仅未解析或解析失败文档可以发起解析任务'},
                status=status.HTTP_400_BAD_REQUEST
            )

        km_id = documents.first().dim_knowledge_repository_id_id
        try:
            km = KnowledgeRepository.objects.get(pk=km_id, creator=request.user)
        except KnowledgeRepository.DoesNotExist:
            return Response(
                {'error': '知识库不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        task_id = str(uuid.uuid4())
        task_store.create_task(
            task_id=task_id,
            user_id=str(request.user.id),
            km_id=str(km_id),
            km_name=km.name,
            doc_ids=doc_ids
        )
        # 提交即标记为解析中，前端可立即反馈
        Document.objects.filter(pk__in=doc_ids).update(parse_status='parsing')

        try:
            from .tasks import parse_documents_task
            parse_documents_task.apply_async(
                args=[str(km_id), km.name, doc_ids, str(request.user.id)],
                task_id=task_id
            )
        except Exception as e:
            logger.exception('解析任务提交失败')
            task_store.finish_task(task_id, 'FAILURE', '任务提交失败', error=str(e)[:500])
            Document.objects.filter(pk__in=doc_ids).update(parse_status='unparsed')
            return Response(
                {'error': '任务提交失败，请稍后再试'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'task_id': task_id, 'message': f'已创建解析任务，共 {len(doc_ids)} 个文档'},
            status=status.HTTP_200_OK
        )


class TaskListView(APIView):
    """获取当前用户的任务列表（进行中 + 24h 内已完成）"""

    def get(self, request):
        tasks = task_store.list_user_tasks(str(request.user.id))
        running_count = sum(1 for t in tasks if t['status'] in task_store.RUNNING_STATUSES)
        return Response(
            {'tasks': tasks, 'running_count': running_count},
            status=status.HTTP_200_OK
        )


# ==================== Chat 接口 ====================

class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ['id', 'name', 'dim_knowledge_repository_id', 'creator', 'createdon', 'modifiedon']
        read_only_fields = ['id', 'creator', 'createdon', 'modifiedon']


class ChatSessionListView(APIView):
    """获取当前用户的聊天会话列表"""

    def get(self, request):
        page_index = request.query_params.get('pageIndex', '1')
        page_size = request.query_params.get('pageSize', '100')
        knowledge_repo_id = request.query_params.get('knowledge_repository_id', '')

        queryset = ChatSession.objects.filter(creator=request.user)

        if knowledge_repo_id:
            queryset = queryset.filter(dim_knowledge_repository_id_id=knowledge_repo_id)

        queryset = queryset.order_by('-createdon')

        try:
            page_index = int(page_index)
            page_size = int(page_size)
        except (ValueError, TypeError):
            return Response({'error': '分页参数格式错误'}, status=status.HTTP_400_BAD_REQUEST)

        offset = (page_index - 1) * page_size
        items = queryset[offset:offset + page_size]

        serializer = ChatSessionSerializer(items, many=True)
        return Response(serializer.data)


class ChatSessionHistoryView(APIView):
    """获取指定会话的历史消息"""

    def get(self, request):
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': 'session_id不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        messages = ChatMessageHistory.objects.filter(session_id=session_id).order_by('created_at')

        result = []
        for msg in messages:
            msg_data = msg.message
            msg_type = msg_data.get('type', 'human')
            content = ''
            if isinstance(msg_data.get('data'), dict):
                content = msg_data['data'].get('content', '')
            elif 'content' in msg_data:
                content = msg_data['content']

            result.append({
                'type': 'human' if msg_type == 'human' else 'ai',
                'data': {'content': content}
            })

        return Response(result)


class ChatSessionDeleteView(APIView):
    """删除聊天会话及相关消息"""

    def post(self, request):
        data = request.data
        if isinstance(data, list):
            ids = data
        elif isinstance(data, dict):
            ids = data.get('ids', [])
        else:
            ids = []

        if not ids:
            return Response({'error': '请提供要删除的会话ID列表'}, status=status.HTTP_400_BAD_REQUEST)

        sessions = ChatSession.objects.filter(pk__in=ids, creator=request.user)
        session_ids = list(sessions.values_list('pk', flat=True))

        if not session_ids:
            return Response({'error': '未找到匹配的会话'}, status=status.HTTP_404_NOT_FOUND)

        ChatMessageHistory.objects.filter(session_id__in=session_ids).delete()
        sessions.delete()

        return Response({'message': '删除成功', 'deleted': len(session_ids)})


class ChatSessionCreateView(APIView):
    """创建聊天会话"""

    def post(self, request):
        knowledge_repository_id = request.data.get('knowledge_repository_id')
        name = request.data.get('name', '')

        if not knowledge_repository_id:
            return Response({'error': '知识库ID不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            repo = KnowledgeRepository.objects.get(pk=knowledge_repository_id, creator=request.user)
        except KnowledgeRepository.DoesNotExist:
            return Response({'error': '知识库不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)

        session = ChatSession.objects.create(
            name=name,
            dim_knowledge_repository_id=repo,
            creator=request.user,
        )

        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatStreamView(APIView):
    """流式聊天接口（原始文本流，非 SSE 格式）"""

    def post(self, request):
        knowledge_repository_id = request.data.get('knowledge_repository_id')
        session_id = request.data.get('session_id')
        query = request.data.get('user_query')

        if not knowledge_repository_id:
            return Response({'error': '知识库ID不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if not query:
            return Response({'error': '查询内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            knowledge_repository = KnowledgeRepository.objects.get(
                pk=knowledge_repository_id, creator=request.user
            )
        except KnowledgeRepository.DoesNotExist:
            return Response({'error': '知识库不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)

        if not session_id:
            uid = uuid.uuid4()
            session_id = str(uid)
            ChatSession.objects.create(
                pk=uid,
                name=query[:100],
                dim_knowledge_repository_id=knowledge_repository,
                creator=request.user,
            )

        sys_prompt = knowledge_repository.system_prompt

        def event_stream():
            rag = RAGCore(str(knowledge_repository_id), streaming=True)
            chain = rag.build_ensemble_chain()
            try:
                for token in chain.stream(
                    {"input": query, "sys_prompt": sys_prompt},
                    config={"configurable": {"session_id": session_id}},
                ):
                    if token:
                        yield token
            except Exception as e:
                yield f"Error: {str(e)}"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/plain",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        response["X-Session-Id"] = session_id
        return response


class KnowledgeRepositorySimpleListView(APIView):
    """获取知识库列表（不分页，用于前端选择器）"""

    def get(self, request):
        queryset = KnowledgeRepository.objects.filter(
            creator=request.user
        ).order_by('-createdon')
        serializer = KnowledgeRepositorySerializer(queryset, many=True)
        return Response(serializer.data)


class TestChatView(APIView):
    def post(self, request):
        knowledge_repository_id = request.data.get('knowledge_repository_id')
        session_id = request.data.get('session_id')
        query = request.data.get('query')

        # 获取知识库的系统提示词
        knowledge_repository = KnowledgeRepository.objects.get(pk=knowledge_repository_id)
        sys_prompt = knowledge_repository.system_prompt
        rag = RAGCore(str(knowledge_repository_id))
        chain = rag.build_chain()

        resp = chain.invoke({"input": query, "sys_prompt": sys_prompt},
            # config 配置信息 configurable  {"session_id": "user123"} 配置的是用户的身份信息
            config={
                "configurable": {"session_id": session_id},
            }
        )
        return Response(
            {'message': resp},
            status=status.HTTP_200_OK
        )

class ChatView(APIView):
    def post(self, request):
        knowledge_repository_id = request.data.get('knowledge_repository_id')
        session_id = request.data.get('session_id')
        query = request.data.get('query')

        if not knowledge_repository_id:
            return Response(
                {'error': '知识库ID不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not session_id:
            return Response(
                {'error': '会话ID不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not query:
            return Response(
                {'error': '查询内容不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            knowledge_repository = KnowledgeRepository.objects.get(pk=knowledge_repository_id)
        except KnowledgeRepository.DoesNotExist:
            return Response(
                {'error': '知识库不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        sys_prompt = knowledge_repository.system_prompt

        def event_stream():
            rag = RAGCore(str(knowledge_repository_id), streaming=True)
            chain = rag.build_chain()
            try:
                for token in chain.stream(
                    {"input": query, "sys_prompt": sys_prompt},
                    config={"configurable": {"session_id": session_id}},
                ):
                    if token:
                        yield f"data: {token}\n\n"
            except Exception as e:
                yield f"data: {{'error': '{str(e)}'}}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
        