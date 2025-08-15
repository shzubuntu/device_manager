from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from django.urls import reverse

# 自定义登录装饰器，用于检查用户是否已登录，用于视图函数
def CustomLoginRequired(function):
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if request.user.is_authenticated:
            return function(request, *args, **kwargs)
        else:
            messages.warning(request, '请先登录后再访问此页面')
            return redirect(f"{reverse('login')}?next={request.path}")
    return wrap 