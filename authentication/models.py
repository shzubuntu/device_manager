from django.db import models
from django.contrib.auth.models import User
from datetime import datetime, timedelta

# 不再需要自定义用户模型 

class Token(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def is_expired(self):
        return datetime.now() > self.expires_at

    @classmethod
    def create_token(cls, user, expires_in_days=7):
        expires_at = datetime.now() + timedelta(days=expires_in_days)
        token = cls.objects.create(
            user=user,
            token=cls.generate_token(),
            expires_at=expires_at
        )
        return token

    @staticmethod
    def generate_token():
        import secrets
        return secrets.token_urlsafe(32) 