"""
Celery 配置入口，供 Django 项目使用。
"""
import os

from celery import Celery

# 设置 Django 默认配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Kaleido.settings')

app = Celery('Kaleido')

# 从 Django settings 中读取 CELERY_ 前缀的配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现所有已安装 app 下的 tasks.py
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
