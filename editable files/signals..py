@receiver(post_save, sender=RawGPSData)
def broadcast_device_update(sender, instance, created, **kwargs):
    try:
        device = instance.device
        if not device:
            return

        channel_layer = get_channel_layer()

        payload = {
            "device_id": device.device_id,
            "lat": instance.latitude,
            "lng": instance.longitude,
            "speed": instance.speed,
            "timestamp": instance.timestamp.isoformat(),
        }

        # ارسال برای صاحب دستگاه
        if device.owner:
            async_to_sync(channel_layer.group_send)(
                f"user_group_{device.owner.id}",
                {"type": "device_update", "data": payload}
            )

        # ارسال اضافه برای ادمین‌ها
        async_to_sync(channel_layer.group_send)(
            "admins_group",
            {"type": "device_update", "data": payload}
        )

    except Exception as e:
        print("Signal error:", e)
