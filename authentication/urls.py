from django.urls import path
from .views import RegisterView, LoginView, LogoutView, CustomAuthToken, UserInfoView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('api/token/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('api/user/info/', UserInfoView.as_view(), name='user_info'),
] 