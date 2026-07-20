"""
URL configuration for Kaleido project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.static import serve


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('user.urls')),
    path('', include('rag_app.urls')),
    # Vue 打包文件直接以 /assets/ 和 /favicon.ico 提供
    path('favicon.ico', serve, {'document_root': str(settings.BASE_DIR / 'static'), 'path': 'favicon.ico'}),
    path('assets/<path:path>', serve, {'document_root': str(settings.BASE_DIR / 'static' / 'assets')}),
    # Vue SPA 入口
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
    # Vue Router history 模式：未匹配的路由都回退到 index.html
    re_path(r'^(?!admin/|assets/|media/|favicon\.ico$).*$', TemplateView.as_view(template_name='index.html')),
]

# 开发环境下提供 media 文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
