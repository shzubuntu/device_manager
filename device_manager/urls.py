"""
URL configuration for device_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # favicon.ico
    re_path(r'^favicon.ico$', RedirectView.as_view(url=r'/static/favicon.ico')),
    path('admin/', admin.site.urls),
    path('health/', csrf_exempt(lambda request: HttpResponse('OK', status=200))),
    path('auth/', include('authentication.urls')),  # 包含认证应用的 URL
    path('api/', include('devices.urls')),
    path('', include('devices.urls')),
]