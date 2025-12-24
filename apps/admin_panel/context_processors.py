from datetime import timedelta

from django.db.models import DateTimeField, OuterRef, Q, Subquery
from django.utils import timezone

from apps.gps_devices.models import Device, LocationData


def admin_dashboard_stats(request):
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return {}

    resolver_match = getattr(request, 'resolver_match', None)
    if not resolver_match:
        return {}

    if resolver_match.app_name != 'admin' or resolver_match.url_name != 'index':
        return {}

    now = timezone.now()

    active_qs = Device.objects.filter(status='active').filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))

    active_devices = active_qs.count()

    latest_seen_subquery = (
        LocationData.objects.filter(device_id=OuterRef('pk'))
        .order_by('-created_at')
        .values('created_at')[:1]
    )

    online_cutoff = now - timedelta(minutes=10)
    online_devices = (
        active_qs.annotate(last_seen=Subquery(latest_seen_subquery, output_field=DateTimeField()))
        .filter(last_seen__gte=online_cutoff)
        .count()
    )

    expiring_cutoff = now + timedelta(days=7)
    expiring_devices = active_qs.filter(expires_at__isnull=False, expires_at__lte=expiring_cutoff).count()

    expired_devices = Device.objects.filter(expires_at__isnull=False, expires_at__lt=now).count()

    return {
        'admin_device_stats': {
            'active': active_devices,
            'online': online_devices,
            'offline': max(active_devices - online_devices, 0),
            'expiring': expiring_devices,
            'expired': expired_devices,
        }
    }
