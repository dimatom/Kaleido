from django.urls import path
from . import views

urlpatterns = [
    # 知识库接口
    path('knowledge/list/', views.KnowledgeRepositoryListView.as_view(), name='knowledge_list'),
    path('knowledge/<uuid:pk>/', views.KnowledgeRepositoryDetailView.as_view(), name='knowledge_detail'),
    path('knowledge/save/', views.KnowledgeRepositoryCreateUpdateView.as_view(), name='knowledge_save'),
    path('knowledge/<uuid:pk>/delete/', views.KnowledgeRepositoryDeleteView.as_view(), name='knowledge_delete'),
    # 文件接口
    path('document/list/', views.DocumentListView.as_view(), name='document_list'),
    path('document/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('document/<uuid:pk>/download/', views.DocumentDownloadView.as_view(), name='document_download'),
    path('document/<uuid:pk>/delete/', views.DocumentDeleteView.as_view(), name='document_delete'),
    path('document/parse/', views.DocumentParseView.as_view(), name='document_parse'),
    path('document/parse/task/', views.DocumentParseTaskView.as_view(), name='document_parse_task'),
    path('task/list/', views.TaskListView.as_view(), name='task_list'),
    # RAG 评估接口
    path('evaluation/precheck/', views.EvaluationPrecheckView.as_view(), name='evaluation_precheck'),
    path('evaluation/', views.EvaluationListCreateView.as_view(), name='evaluation_list_create'),
    path('evaluation/<uuid:pk>/', views.EvaluationDetailView.as_view(), name='evaluation_detail'),
    path('evaluation/<uuid:evaluation_id>/data/', views.EvaluationDataListCreateView.as_view(), name='evaluation_data_list_create'),
    path('evaluation/data/<uuid:pk>/', views.EvaluationDataDetailView.as_view(), name='evaluation_data_detail'),
    path('evaluation/<uuid:evaluation_id>/tasks/', views.EvaluationTaskListCreateView.as_view(), name='evaluation_task_list_create'),
    path('evaluation/task/<uuid:pk>/', views.EvaluationTaskDetailView.as_view(), name='evaluation_task_detail'),
    path('evaluation/task/<uuid:task_id>/runs/', views.EvaluationRunListStartView.as_view(), name='evaluation_run_list_start'),
    path('evaluation/run/<uuid:pk>/download/', views.EvaluationRunDownloadView.as_view(), name='evaluation_run_download'),
    path('evaluation/task/<uuid:task_id>/apply-config/', views.EvaluationApplyConfigView.as_view(), name='evaluation_apply_config'),
    # Chat 接口
    path('testchat/', views.TestChatView.as_view(), name='testchat'),
    path('chat/', views.ChatView.as_view(), name='chat'),
    # Chat 会话管理接口
    path('chat/sessions/', views.ChatSessionListView.as_view(), name='chat_sessions_list'),
    path('chat/sessions/create/', views.ChatSessionCreateView.as_view(), name='chat_sessions_create'),
    path('chat/sessions/delete/', views.ChatSessionDeleteView.as_view(), name='chat_sessions_delete'),
    path('chat/history/', views.ChatSessionHistoryView.as_view(), name='chat_history'),
    path('chat/stream/', views.ChatStreamView.as_view(), name='chat_stream'),
    path('chat/repositories/', views.KnowledgeRepositorySimpleListView.as_view(), name='chat_repositories'),
]
