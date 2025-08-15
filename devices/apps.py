from django.apps import AppConfig
import os


class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'devices'
    #path = '/app/devices'
    path = os.path.abspath(os.path.dirname(__file__))
