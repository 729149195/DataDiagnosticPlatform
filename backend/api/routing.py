from django.urls import re_path
from . import websocket

websocket_urlpatterns = [
    re_path(r'ws/progress/$', websocket.ProgressConsumer.as_asgi()),
]
