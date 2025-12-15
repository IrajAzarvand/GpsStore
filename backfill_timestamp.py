import os
import django
from django.db.models import F

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gps_store.settings')
django.setup()

from apps.gps_devices.models import LocationData

print("Updating LocationData timestamp from created_at...")
count = LocationData.objects.filter(timestamp__isnull=True).update(timestamp=F('created_at'))
print(f"Updated {count} records.")
