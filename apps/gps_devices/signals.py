from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.tracking.models import LocationData
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=LocationData)
def broadcast_device_update(sender, instance, created, **kwargs):
    """
    Broadcasts device update to WebSocket groups:
    - user_group_{owner.id} (if owner exists)
    - user_group_{subuser.id} (for assigned subusers)
    - admins_group (for admins)
    """
    if not created:
        return

    try:
        channel_layer = get_channel_layer()
        device = instance.device
        
        # Prepare timestamp - handle both datetime and string
        if instance.timestamp:
            if isinstance(instance.timestamp, str):
                timestamp_str = instance.timestamp
            else:
                timestamp_str = instance.timestamp.isoformat()
        else:
            timestamp_str = None
        
        # Prepare data payload matching the format expected by frontend
        payload = {
            'id': device.id,
            'imei': device.imei,
            'device_id': device.device_id,
            'name': device.name,
            'latitude': float(instance.latitude) if instance.latitude else None,
            'longitude': float(instance.longitude) if instance.longitude else None,
            'lat': float(instance.latitude) if instance.latitude else None,
            'lng': float(instance.longitude) if instance.longitude else None,
            'speed': float(instance.speed) if instance.speed else 0,
            'angle': float(instance.heading) if instance.heading else 0,
            'heading': float(instance.heading) if instance.heading else 0,
            'timestamp': timestamp_str,
            'last_update': timestamp_str,
            'battery_level': instance.battery_level,
            'status': device.status,
            'source': 'GPS',
            'gps_valid': True
        }
        
        device_identifier = device.imei or device.device_id or device.name or device.id
        logger.info(f"Broadcasting update for device {device_identifier}")
        
        message = {
            'type': 'device_update',
            'device_id': device_identifier,
            'data': payload,
            'timestamp': timestamp_str
        }

        # 1. Send to Admins
        async_to_sync(channel_layer.group_send)('admins_group', message)
        
        # 2. Send to Owner (Customer)
        if device.customer and device.customer.user:
            async_to_sync(channel_layer.group_send)(
                f'user_group_{device.customer.user.id}', 
                message
            )

        # 3. Send to SubUsers
        # SubUser has 'username' which matches a Django User
        for subuser in device.assigned_sub_users.all():
            try:
                user = User.objects.get(username=subuser.username)
                async_to_sync(channel_layer.group_send)(f'user_group_{user.id}', message)
            except User.DoesNotExist:
                logger.warning(f"SubUser {subuser.username} has no corresponding Django User")

    except Exception as e:
        logger.error(f"Error broadcasting device update: {e}")
