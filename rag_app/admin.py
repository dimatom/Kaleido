from django.contrib import admin
from .models import ChatSession, Document, Evaluation, EvaluationData, EvaluationRun, EvaluationTask, KnowledgeRepository

admin.site.register(KnowledgeRepository)
admin.site.register(Document)
admin.site.register(ChatSession)
admin.site.register(Evaluation)
admin.site.register(EvaluationData)
admin.site.register(EvaluationTask)
admin.site.register(EvaluationRun)