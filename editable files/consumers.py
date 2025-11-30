import json
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync

class DeviceUpdateConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            self.close()
            return

        self.groups = []

        # 1. یوزر معمولی → فقط گروه خودش
        user_group = f"user_group_{self.user.id}"
        self.groups.append(user_group)

        # 2. اگر ادمین باشد → یک گروه ویژه برای همه دستگاه‌ها
        if self.user.is_staff or self.user.is_superuser:
            self.groups.append("admins_group")

        # Join all required groups
        for g in self.groups:
            async_to_sync(self.channel_layer.group_add)(g, self.channel_name)

        self.accept()

    def disconnect(self, close_code):
        for g in self.groups:
            async_to_sync(self.channel_layer.group_discard)(g, self.channel_name)

    def receive(self, text_data):
        pass

    def device_update(self, event):
        self.send(text_data=json.dumps(event["data"]))
