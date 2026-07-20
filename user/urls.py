from django.contrib import admin
from django.urls import path,include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    # 测试接口
    path('test/', views.TestAPIView.as_view(), name='test'),
    # JWT 登录接口（获取 Token）
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # 刷新 Token 接口
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('getuser/', views.GetUser.as_view(), name='getuser')
]