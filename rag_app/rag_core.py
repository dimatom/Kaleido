import json
import os
import re
import time
from typing import Sequence
from urllib import error, request

import psycopg
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate, MessagesPlaceholder
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_classic.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from operator import itemgetter
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.documents import Document
import ollama
from Kaleido.environment import get_env, get_int
from Kaleido.logger import logger

class RAGConfig:
    # Kaleido 配置
    # LLM 配置
    Kaleido_BASE_URL = get_env(
        "KALEIDO_LLM_BASE_URL",
        aliases=("Kaleido_BASE_URL",),
    )
    Kaleido_API_KEY = get_env(
        "KALEIDO_LLM_API_KEY",
        aliases=("Kaleido_API_KEY",),
    )
    Kaleido_MODEL = get_env("KALEIDO_LLM_MODEL", default="deepseek-v4-pro")
    # 嵌入模型配置WS
    Kaleido_OLLAMA_BASE_URL = get_env(
        "KALEIDO_OLLAMA_BASE_URL",
        default="http://127.0.0.1:11434",
    )
    Kaleido_EMBEDDING_MODEL = get_env(
        "KALEIDO_EMBEDDING_MODEL",
        default="qwen3-embedding",
    )
    Kaleido_EMBEDDING_BASE_URL = get_env(
        "KALEIDO_EMBEDDING_BASE_URL",
        default=Kaleido_OLLAMA_BASE_URL,
    )
    Kaleido_RERANK_MODEL = get_env(
        "KALEIDO_RERANK_MODEL",
        default="dengcao/Qwen3-Reranker-4B:Q5_K_M",
    )
    RerankCandidateCount = get_int("KALEIDO_RERANK_CANDIDATE_COUNT", 6)
    RerankTopN = get_int("KALEIDO_RERANK_TOP_N", 3)
    RerankTimeout = get_int("KALEIDO_RERANK_TIMEOUT", 15)
    ChunkSize = get_int("KALEIDO_CHUNK_SIZE", 500)
    ChunkOverlap = get_int("KALEIDO_CHUNK_OVERLAP", 100)


class OllamaRerankCompressor(BaseDocumentCompressor):
    """将本地 Ollama 重排模型适配为 LangChain 文档压缩器。"""

    model: str
    base_url: str
    top_n: int = RAGConfig.RerankTopN
    timeout: int = RAGConfig.RerankTimeout
    ollama_client: object

    def _fallback_documents(self, documents: Sequence[Document]) -> list[Document]:
        """重排服务不可用时保持融合检索的原有排序。"""
        return list(documents[:self.top_n])

    def _call_rerank_api(self, query: str, documents: Sequence[Document]) -> list[dict]:
        """调用 Ollama 专用重排接口，返回原始结果列表。"""
        payload = json.dumps({
            "model": self.model,
            "query": query,
            "documents": [doc.page_content for doc in documents],
            "top_n": self.top_n,
        }).encode("utf-8")
        api_request = request.Request(
            f"{self.base_url.rstrip('/')}/api/rerank",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(api_request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise ValueError("Ollama 重排响应缺少 results 列表")
        return results

    def _call_generate_fallback(self, query: str, documents: Sequence[Document]) -> list[dict]:
        """兼容未提供 /api/rerank 的本地 Ollama 版本。"""
        candidates = "\n\n".join(
            f"[{index}]\n{doc.page_content}" for index, doc in enumerate(documents)
        )
        prompt = (
            "你是文档重排器。根据用户问题对候选文档按相关性排序，最多返回 "
            f"{self.top_n} 个文档。只返回 JSON："
            '{"results":[{"index":0,"score":0.98}]}。\n\n'
            f"用户问题：\n{query}\n\n候选文档：\n{candidates}"
        )
        response = self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            format="json",
            options={"temperature": 0},
        )
        body = json.loads(getattr(response, "response", "") or "{}")
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise ValueError("兼容重排响应缺少 results 列表")
        return results

    def _to_ranked_documents(
        self,
        documents: Sequence[Document],
        results: Sequence[dict],
    ) -> list[Document]:
        ranked_documents = []
        seen_indexes = set()
        for result in results:
            if not isinstance(result, dict):
                continue
            index = result.get("index")
            if isinstance(index, bool):
                continue
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if index < 0 or index >= len(documents) or index in seen_indexes:
                continue

            metadata = dict(documents[index].metadata or {})
            score = result.get("relevance_score", result.get("score"))
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                metadata["rerank_score"] = float(score)
            ranked_documents.append(Document(
                page_content=documents[index].page_content,
                metadata=metadata,
                id=documents[index].id,
            ))
            seen_indexes.add(index)
            if len(ranked_documents) >= self.top_n:
                break
        return ranked_documents

    def compress_documents(self, documents: Sequence[Document], query: str, callbacks=None) -> Sequence[Document]:
        if not documents:
            return []

        started_at = time.perf_counter()
        try:
            # try:
            #     results = self._call_rerank_api(query, documents)
            # except (error.HTTPError, error.URLError) as api_error:
            #     logger.info(f"Ollama 专用重排接口不可用，使用兼容模式：{api_error}")
            #     results = self._call_generate_fallback(query, documents)
            results = self._call_generate_fallback(query, documents)
            ranked_documents = self._to_ranked_documents(documents, results)
            if not ranked_documents:
                raise ValueError("重排结果中没有有效文档索引")
            elapsed = time.perf_counter() - started_at
            logger.info(f"文档重排完成：候选 {len(documents)} 条，返回 {len(ranked_documents)} 条，耗时 {elapsed:.2f}s")
            return ranked_documents
        except Exception as exc:
            logger.warning(f"文档重排失败，回退到融合结果：{type(exc).__name__}: {exc}")
            return self._fallback_documents(documents)


class RAGCore:
    
    def __init__(self, kmid, streaming=False, rag_config=None, collection_name=None) -> None:
        if not RAGConfig.Kaleido_BASE_URL or not RAGConfig.Kaleido_API_KEY:
            raise ImproperlyConfigured(
                "KALEIDO_LLM_BASE_URL and KALEIDO_LLM_API_KEY must be set"
            )
        from .evaluation_service import normalize_rag_config

        self.rag_config = normalize_rag_config(rag_config)
        self.collection_name = collection_name or str(kmid)
        # LLM Client
        self.llm_client = ChatOpenAI(
            base_url=RAGConfig.Kaleido_BASE_URL,
            api_key=RAGConfig.Kaleido_API_KEY,
            model=RAGConfig.Kaleido_MODEL,
            streaming=streaming)
        # LLM Embeddings
        self.llm_embeddings = OllamaEmbeddings(
            model=RAGConfig.Kaleido_EMBEDDING_MODEL,
            base_url=RAGConfig.Kaleido_EMBEDDING_BASE_URL
        )
        self.ollama_client = ollama.Client(host=RAGConfig.Kaleido_OLLAMA_BASE_URL)
        # VectorStore
        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.llm_embeddings,
            persist_directory="./chroma_db"
        )

    @staticmethod
    def detect_file_encoding(file_path: str) -> str:
        """尝试用常见编码解码文件，返回首个可用的编码。"""
        encodings = ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'gb2312', 'big5', 'latin-1']
        with open(file_path, 'rb') as f:
            raw = f.read()
        for encoding in encodings:
            try:
                raw.decode(encoding)
                return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        return 'utf-8'

    def load_document(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        try:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith('.docx'):
                loader = Docx2txtLoader(file_path)
            elif file_path.endswith(('.txt', '.md')):
                encoding = self.detect_file_encoding(file_path)
                loader = TextLoader(file_path, encoding=encoding)
                logger.info(f"检测到文件编码：{encoding}")
            else:
                logger.info("不支持的文件格式")
                logger.info("支持格式：.pdf, .docx, .txt, .md")
                return None

            documents = loader.load()
            logger.info(f"成功加载文档：{file_path}")
            total_len = sum(len(d.page_content) for d in documents)
            logger.info(f"文档信息：共 {len(documents)} 页/段，总字符数：{total_len}")
            return documents

        except Exception as e:
            logger.info(f"加载文档失败：{str(e)}")
            return None

    def splitter(self, docs):
        indexing = self.rag_config["indexing"]
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=indexing["chunk_size"],
            chunk_overlap=indexing["chunk_overlap"],
        )
        documents = splitter.split_documents(docs)
        return documents

    def save_document(self, documents, batch_size=20):
        """
        将文档分批写入向量库，避免一次性向 Ollama 提交过多文本导致 runner 崩溃。

        参数:
            documents: 待入库的 Document 列表
            batch_size: 每批嵌入的 chunk 数量，默认 20（可在此调整）
        """
        total = len(documents)
        for i in range(0, total, batch_size):
            batch = documents[i:i + batch_size]
            self.vectorstore.add_documents(documents=batch)
            logger.info(f"向量入库进度：已处理 {min(i + batch_size, total)}/{total} 个 chunk")

    def get_retriever(self):
        return self.vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    def parse_document(self, document_list, progress_callback=None):
        """
        解析文档列表。

        document_list 格式：[{
            "path": "文档路径",
            "metadata": {
                "document_id": "xxxx-xxxx-xxxx-xxxxxx"
            }
        }]
        返回格式: [{"document_id": "xxx", "chunk_count": 10}, ...]

        progress_callback(index, total, stage, doc) 可选回调：
            stage: 'loading' | 'splitting' | 'saving' | 'done'
            index: 当前文档索引（从 0 开始）
        """
        result = []
        if not document_list:
            return result
        total = len(document_list)
        for index, doc in enumerate(document_list):
            if progress_callback:
                progress_callback(index, total, 'loading', doc)
            documents = self.load_document(doc['path'])
            if not documents:
                # 单文档加载失败，仍触发 done 阶段以便任务进度准确
                if progress_callback:
                    progress_callback(index + 1, total, 'done', doc)
                continue
            for d in documents:
                d.metadata.update(doc['metadata'])
            if progress_callback:
                progress_callback(index, total, 'splitting', doc)
            documents = self.splitter(documents)
            if progress_callback:
                progress_callback(index, total, 'saving', doc)
            self.save_document(documents)
            result.append({
                "document_id": doc['metadata'].get('document_id'),
                "chunk_count": len(documents)
            })
            if progress_callback:
                progress_callback(index + 1, total, 'done', doc)
        return result

    def delete_document(self, documentid_list):
        # documentid_list 是一个文档ID列表 ["xxxx-xxxx-xxxx-xxxxxx"]
        if not documentid_list:
            return None

        try:
            result = self.vectorstore._collection.get(
                where={'document_id': {'$in': documentid_list}}
            )
            ids = result.get('ids', [])

            if ids:
                self.vectorstore._collection.delete(ids=ids)
                logger.info(f"成功删除 {len(ids)} 条向量记录")
            else:
                logger.info("未找到匹配的文档")

            return ids
        except Exception as e:
            logger.info(f"删除文档失败：{str(e)}")
            return None

    def delete_collection(self):
        try:
            self.vectorstore.delete_collection()
            logger.info(f"成功删除集合：{self.collection_name}")
            return True
        except Exception as e:
            logger.info(f"删除集合失败：{str(e)}")
            return False

    def build_chain(self):
        system_prompt = """
{sys_prompt}
上下文：<{context}>
"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        retriever = self.get_retriever()

        document_chain = create_stuff_documents_chain(self.llm_client, prompt)

        chain = (
            {
                "input": itemgetter("input"),
                "sys_prompt": itemgetter("sys_prompt"),
                "context": itemgetter("input") | retriever,
                "history": itemgetter("history"),
            }
            | document_chain
        )

        chat_with_history = RunnableWithMessageHistory(
            chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

        return chat_with_history

    def get_all_documents(self):
        """
        获取向量库中的所有文档
        
        Returns:
            list[Document]: 所有文档列表
        """
        try:
            result = self.vectorstore._collection.get()
            ids = result.get('ids', [])
            embeddings = result.get('embeddings', [])
            metadatas = result.get('metadatas', [])
            documents = result.get('documents', [])
            
            docs = []
            for i, doc_id in enumerate(ids):
                metadata = metadatas[i] if i < len(metadatas) else {}
                page_content = documents[i] if i < len(documents) else ""
                
                doc = Document(
                    page_content=page_content,
                    metadata=metadata
                )
                docs.append(doc)
            
            return docs
        except Exception as e:
            logger.info(f"获取所有文档失败：{str(e)}")
            return []

    def build_ensemble_retriever(self):
        """构建由当前实例 RAG 配置控制的混合检索器。"""
        retrieval = self.rag_config["retrieval"]
        all_docs = self.get_all_documents()
        logger.info(f"混合检索候选文档数: {len(all_docs)}")
        vector_retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": retrieval["ensemble_top_k"]},
        )

        retrievers = [vector_retriever]
        weights = [1.0]
        if all_docs:
            bm25_retriever = BM25Retriever.from_documents(all_docs)
            bm25_retriever.k = retrieval["ensemble_top_k"]
            retrievers.append(bm25_retriever)
            vector_weight = retrieval["vector_weight"]
            bm25_weight = retrieval["bm25_weight"]
            total_weight = vector_weight + bm25_weight
            weights = [vector_weight / total_weight, bm25_weight / total_weight]

        return ContextualCompressionRetriever(
            base_retriever=EnsembleRetriever(retrievers=retrievers, weights=weights),
            base_compressor=OllamaRerankCompressor(
                model=RAGConfig.Kaleido_RERANK_MODEL,
                base_url=RAGConfig.Kaleido_OLLAMA_BASE_URL,
                top_n=retrieval["rerank_top_k"],
                timeout=RAGConfig.RerankTimeout,
                ollama_client=self.ollama_client,
            ),
        )

    def _build_document_chain(self):
        system_prompt = """
{sys_prompt}
上下文：<{context}>
"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}"),
        ])
        return create_stuff_documents_chain(self.llm_client, prompt)

    def build_evaluation_answer(self, question, history_context, sys_prompt):
        """使用内存历史执行评估，不读取或写入生产聊天历史。"""
        retriever = self.build_ensemble_retriever()
        documents = retriever.invoke(question)
        document_chain = self._build_document_chain()
        answer = document_chain.invoke({
            "input": question,
            "sys_prompt": sys_prompt or "",
            "context": documents,
            "history": history_context or [],
        })
        return str(answer), documents

    def build_ensemble_chain(self):
        document_chain = self._build_document_chain()
        compression_retriever = self.build_ensemble_retriever()
        chain = (
            {
                "input": itemgetter("input"),
                "sys_prompt": itemgetter("sys_prompt"),
                "context": itemgetter("input") | compression_retriever,
                "history": itemgetter("history"),
            }
            | document_chain
        )

        return RunnableWithMessageHistory(
            chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def get_session_history(self, session_id):
        db_config = settings.DATABASES['default']
        conn = psycopg.connect(
            host=db_config['HOST'],
            port=db_config['PORT'],
            dbname=db_config['NAME'],
            user=db_config['USER'],
            password=db_config['PASSWORD'],
        )
        return PostgresChatMessageHistory(
            "chat_message_history",  # table_name
            session_id,
            sync_connection=conn,
        )

    def create_chat_message_history_tables(self):
        db_config = settings.DATABASES['default']
        conn = psycopg.connect(
            host=db_config['HOST'],
            port=db_config['PORT'],
            dbname=db_config['NAME'],
            user=db_config['USER'],
            password=db_config['PASSWORD'],
        )
        PostgresChatMessageHistory.create_tables(conn, "chat_message_history")
