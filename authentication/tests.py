from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
import json

class TokenAuthenticationTest(APITestCase):
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        # 创建测试 URL
        self.url = reverse('api_token_auth')

    def test_get_token_with_valid_credentials(self):
        """测试使用有效凭据获取 token"""
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post(self.url, data, format='json')
        print("获取到token：",json.dumps(response.data, indent=4))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIn('user_id', response.data)
        self.assertIn('username', response.data)
        self.assertEqual(response.data['username'], 'testuser')

    def test_get_token_with_invalid_credentials(self):
        """测试使用无效凭据获取 token"""
        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }
        response = self.client.post(self.url, data, format='json')
        print("获取到token：",json.dumps(response.data, indent=4))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
        self.assertEqual(response.data['non_field_errors'][0].code, 'authorization')

    def test_get_token_with_missing_credentials(self):
        """测试缺少凭据时获取 token"""
        data = {}
        response = self.client.post(self.url, data, format='json')
        print("获取到token：",json.dumps(response.data, indent=4))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('password', response.data)
        self.assertEqual(response.data['username'][0].code, 'required')
        self.assertEqual(response.data['password'][0].code, 'required')

class UserAuthenticationTest(APITestCase):
    def setUp(self):
        # 创建测试用户
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        # 创建 token
        self.token = Token.objects.create(user=self.user)
        print("获取到token：",self.token.key)
        # 设置Token认证头
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        # 设置用户信息 URL
        self.url = reverse('user_info')

    def test_authenticated_request(self):
        """测试带 token 的认证请求"""
        response = self.client.get(self.url)
        print("认证结果：",response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

    def test_unauthenticated_request(self):
        """测试未认证的请求"""
        # 清除认证头
        self.client.credentials()
        response = self.client.get(self.url)
        print("认证结果：",response.data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        """测试无效的 token"""
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token')
        response = self.client.get(self.url)
        print("认证结果：",response.data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED) 