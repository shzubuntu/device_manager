from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.contrib import messages
from django.contrib.auth.models import User


class RegisterView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/')
        return render(request, 'authentication/register.html')

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            messages.error(request, '两次输入的密码不一致')
            return render(request, 'authentication/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
            return render(request, 'authentication/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, '邮箱已被使用')
            return render(request, 'authentication/register.html')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        messages.success(request, '注册成功，请登录')
        return redirect('/auth/login/')

class LoginView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/')
        next_page = request.GET.get('next', '')
        #return render(request, 'authentication/login.html')
        return render(request, 'authentication/login.html', {'next': next_page})

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next')  # 获取next参数
            if next_url:
                return redirect(next_url)  # 重定向到next参数指定的URL
            return redirect('/')  # 如果没有next参数，重定向到主页
        else:
            messages.error(request, '用户名或密码错误')
            return render(request, 'authentication/login.html')

class LogoutView(APIView):
    def get(self, request):
        logout(request)
        messages.info(request, '您已安全退出')
        next_page = request.GET.get('next', '/')
        #if next_page:
        #return redirect('/auth/login/')
        return redirect(f'/auth/login/?next={next_page}')

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                         context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user_id': user.pk,
                'username': user.username
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserInfoView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser
        })