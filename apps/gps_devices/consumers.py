import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class DeviceUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer:
    - Accepts only authenticated users (closes if anonymous).
    - Joins groups:
        * user_group_{user.id}  --> for normal users
        * admins_group          --> if user.is_staff or user.is_superuser
    - Receives "device_update" events from channel layer and forwards to client.
    """
    async def connect(self):
        # Try to get token from query string
        query_string = self.scope.get('query_string', b'').decode()
        token = None
        if 'token=' in query_string:
            token = query_string.split('token=')[1].split('&')[0]
        
        # Authenticate using token
        if token:
            try:
                user = await self.get_user_from_token(token)
                if user:
                    self.scope['user'] = user
                    logger.info(f"User authenticated via JWT token: {user.username}")
            except Exception as e:
                logger.warning(f"Token authentication failed: {e}")
                await self.close()
                return
        
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            logger.info(f"Rejecting anonymous websocket connection: {self.scope.get('client')}")
            await self.close()
            return

        self.user = user
        self.groups_to_join = []

        # join personal group
        personal_group = f"user_group_{self.user.id}"
        self.groups_to_join.append(personal_group)

        # admins see everything
        if getattr(self.user, "is_staff", False) or getattr(self.user, "is_superuser", False):
            self.groups_to_join.append("admins_group")

        # join groups
        for g in self.groups_to_join:
            await self.channel_layer.group_add(g, self.channel_name)
            logger.debug(f"WS {self.channel_name} joined {g}")

        await self.accept()
        # initial welcome
        await self.send(text_data=json.dumps({
            "type": "connection",
            "status": "connected",
            "user_id": self.user.id,
            "groups": self.groups_to_join
        }))

    async def disconnect(self, close_code):
        for g in getattr(self, "groups_to_join", []):
            try:
                await self.channel_layer.group_discard(g, self.channel_name)
            except Exception:
                logger.exception("Error discarding group on disconnect")

    async def receive(self, text_data=None, bytes_data=None):
        # Optional: handle ping/pong or request for specific device details
        if text_data:
            try:
                data = json.loads(text_data)
            except Exception:
                return
            # Echo for debug
            if data.get("action") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))

    async def get_user_from_token(self, token_string):
        """Authenticate user from JWT token"""
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model
        from channels.db import database_sync_to_async
        
        User = get_user_model()
        
        @database_sync_to_async
        def get_user(user_id):
            try:
                return User.objects.get(id=user_id)
            except User.DoesNotExist:
                return None
        
        try:
            access_token = AccessToken(token_string)
            user_id = access_token.payload.get('user_id')
            return await get_user(user_id)
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return None

    async def device_update(self, event):
        """
        Event shape expected:
        {
            "type": "device_update",
            "device_id": "9176515388",
            "data": { ... }  # JSON-serializable payload
        }
        """
        payload = event.get("data") or {}
        # forward to client
        await self.send(text_data=json.dumps({
            "type": "device_update",
            "device": payload,
            "timestamp": event.get("timestamp")
        }))