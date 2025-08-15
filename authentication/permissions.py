from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotAuthenticated
# 自定义权限，只对写操作的api接口要求认证    
class IsAuthenticatedForWriteOnly(BasePermission):
    """
    只对写操作要求认证的权限类
    """
    def has_permission(self, request, view):
        # 如果是安全方法（GET, HEAD, OPTIONS），允许访问
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
            
        # 对于其他方法，检查用户是否已认证
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated(detail={
                'code': 401,
                'message': '请先登录后再访问'
            })
        return True 