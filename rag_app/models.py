import uuid
import os
import mimetypes

from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver


class KnowledgeRepository(models.Model):
    """知识库"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    name = models.CharField(max_length=255, verbose_name="名称")
    desc = models.TextField(blank=True, verbose_name="描述")
    system_prompt = models.TextField(blank=True, verbose_name="系统提示词")
    rag_config = models.JSONField(default=dict, verbose_name="RAG配置")
    image = models.ImageField(upload_to="knowledge_repository/images/", blank=True, null=True, verbose_name="图片")
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_knowledge_repositories",
        verbose_name="创建人",
        db_column="creator",
    )
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    modifiedon = models.DateTimeField(auto_now=True, verbose_name="修改时间")

    class Meta:
        db_table = "dim_knowledge_repository"
        verbose_name = "知识库"
        verbose_name_plural = "知识库"

    def __str__(self):
        return self.name


class Evaluation(models.Model):
    """知识库 RAG 评估事项。"""

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('generating', '生成中'),
        ('ready', '已就绪'),
        ('failed', '生成失败'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    dim_knowledge_repository_id = models.ForeignKey(
        KnowledgeRepository,
        on_delete=models.CASCADE,
        related_name="evaluations",
        verbose_name="知识库",
        db_column="dim_knowledge_repository_id",
    )
    name = models.CharField(max_length=255, verbose_name="名称")
    description = models.TextField(blank=True, verbose_name="描述")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="状态")
    progress = models.PositiveSmallIntegerField(default=0, verbose_name="数据生成进度")
    conversation_start_at = models.DateTimeField(null=True, blank=True, verbose_name="消息开始时间")
    conversation_end_at = models.DateTimeField(null=True, blank=True, verbose_name="消息结束时间")
    selected_user_ids = models.JSONField(default=list, verbose_name="筛选用户")
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_evaluations",
        verbose_name="创建人",
        db_column="creator",
    )
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    modifiedon = models.DateTimeField(auto_now=True, verbose_name="修改时间")

    class Meta:
        db_table = "dim_evaluation"
        verbose_name = "评估事项"
        verbose_name_plural = "评估事项"
        indexes = [models.Index(fields=['dim_knowledge_repository_id', '-createdon'])]

    def __str__(self):
        return self.name


class EvaluationData(models.Model):
    """一条可人工维护的 RAG 评估数据。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    dim_evaluation_id = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name="data_items",
        verbose_name="评估事项",
        db_column="dim_evaluation_id",
    )
    question = models.TextField(verbose_name="问题")
    ai_answer = models.TextField(blank=True, verbose_name="原AI回答")
    reference_answer = models.TextField(blank=True, verbose_name="标准答案")
    history_context = models.JSONField(default=list, verbose_name="历史上下文")
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    modifiedon = models.DateTimeField(auto_now=True, verbose_name="修改时间")

    class Meta:
        db_table = "dim_evaluation_data"
        verbose_name = "评估数据"
        verbose_name_plural = "评估数据"


class EvaluationTask(models.Model):
    """一组待对比的 RAG 配置。"""

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('ready', '已就绪'),
        ('running', '执行中'),
        ('success', '执行成功'),
        ('failed', '执行失败'),
    ]
    TASK_MARK_CHOICES = [
        ('baseline', '基线'),
        ('candidate', '候选'),
        ('selected', '已选择'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    dim_evaluation_id = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="评估事项",
        db_column="dim_evaluation_id",
    )
    name = models.CharField(max_length=255, verbose_name="名称")
    rag_config = models.JSONField(default=dict, verbose_name="RAG配置")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="状态")
    task_mark = models.CharField(max_length=20, choices=TASK_MARK_CHOICES, default='candidate', verbose_name="任务标记")
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_evaluation_tasks",
        verbose_name="创建人",
        db_column="creator",
    )
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    modifiedon = models.DateTimeField(auto_now=True, verbose_name="修改时间")

    class Meta:
        db_table = "dim_evaluation_task"
        verbose_name = "评估任务"
        verbose_name_plural = "评估任务"


class EvaluationRun(models.Model):
    """评估任务的一次异步执行记录。"""

    STATUS_CHOICES = [
        ('PENDING', '等待中'),
        ('PROGRESS', '执行中'),
        ('SUCCESS', '成功'),
        ('FAILURE', '失败'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    dim_evaluation_task_id = models.ForeignKey(
        EvaluationTask,
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name="评估任务",
        db_column="dim_evaluation_task_id",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="状态")
    celery_task_id = models.CharField(max_length=255, blank=True, verbose_name="Celery任务ID")
    result = models.JSONField(default=dict, verbose_name="汇总结果")
    file = models.FileField(upload_to='evaluation/reports/', null=True, blank=True, verbose_name="报告文件")
    error_message = models.TextField(blank=True, verbose_name="错误信息")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "dim_evaluation_run"
        verbose_name = "评估执行"
        verbose_name_plural = "评估执行"


class Document(models.Model):
    """文档"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    dim_knowledge_repository_id = models.ForeignKey(
        KnowledgeRepository,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="知识库",
        db_column="dim_knowledge_repository_id",
    )
    name = models.CharField(max_length=255, blank=True, verbose_name="文件名")
    type = models.CharField(max_length=50, blank=True, verbose_name="文件类型")
    mime_type = models.CharField(max_length=127, blank=True, verbose_name="媒体类型")
    filedata = models.FileField(upload_to="documents/files/", verbose_name="文件")
    size = models.PositiveBigIntegerField(blank=True, null=True, verbose_name="文件大小")
    chunk = models.BigIntegerField(default=0, verbose_name="分块数")
    PARSE_STATUS_CHOICES = [
        ('unparsed', '未解析'),
        ('parsing', '解析中'),
        ('parsed', '解析成功'),
        ('failed', '解析失败'),
    ]
    parse_status = models.CharField(
        max_length=20,
        choices=PARSE_STATUS_CHOICES,
        default='unparsed',
        verbose_name="解析状态"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_documents",
        verbose_name="创建人",
        db_column="creator",
    )
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    modifiedon = models.DateTimeField(auto_now=True, verbose_name="修改时间")

    class Meta:
        db_table = "dim_document"
        verbose_name = "文档"
        verbose_name_plural = "文档"

    def __str__(self):
        return self.name or str(self.id)


@receiver(pre_save, sender=Document)
def document_pre_save(sender, instance, **kwargs):
    """在保存前自动提取文件名、扩展名、媒体类型和文件大小"""
    file = instance.filedata
    if file and hasattr(file, "name"):
        # 文件名（不含路径）
        instance.name = os.path.basename(file.name)

        # 扩展名（小写，不含前导点）
        _, ext = os.path.splitext(file.name)
        instance.type = ext.lower().lstrip(".")

        # 媒体类型
        instance.mime_type = mimetypes.guess_type(file.name)[0] or ""

        # 文件大小
        try:
            instance.size = file.size
        except (OSError, ValueError):
            instance.size = 0


class ChatMessageHistory(models.Model):
    session_id = models.UUIDField()
    message = models.JSONField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'chat_message_history'

class ChatSession(models.Model):
    """聊天会话"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name="ID")
    name = models.CharField(max_length=255, blank=True, verbose_name="会话描述")
    dim_knowledge_repository_id = models.ForeignKey(
        KnowledgeRepository,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        verbose_name="知识库",
        db_column="dim_knowledge_repository_id",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
        verbose_name="创建人",
        db_column="creator",
    )
    createdon = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    modifiedon = models.DateTimeField(auto_now=True, verbose_name="修改时间")

    class Meta:
        db_table = "dim_chat_session"
        verbose_name = "聊天会话"
        verbose_name_plural = "聊天会话"

    def __str__(self):
        return self.name or str(self.id)