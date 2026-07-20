from django.contrib import admin
from .models import KnowledgeRepository, Document, ChatSession

admin.site.register(KnowledgeRepository)
admin.site.register(Document)
admin.site.register(ChatSession)