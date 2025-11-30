from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/device-updates/$', consumers.DeviceUpdateConsumer.as_asgi()),
]