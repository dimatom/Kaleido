from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView
from rest_framework.response import Response

class TestAPIView(APIView):
    def get(self, request):
        return Response({"message": "鉴权成功"})

    def post(self, request):
        return Response({
            "username": request.user.username,
            "email": request.user.email
        })

# 获取用户信息
class GetUser(APIView):
    def get(self, request):
        return Response({
            "username": request.user.username,
            "email": request.user.email
        })