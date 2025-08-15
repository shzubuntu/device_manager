from django.apps import AppConfig
import os

class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'
    # Explicitly set the path to resolve multiple location issue
    path = os.path.abspath(os.path.dirname(__file__))