# Generated manually for security enhancements

import django.db.models.deletion
from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('gps_devices', '0005_alter_rawgpsdata_device_alter_rawgpsdata_protocol'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='rawgpsdata',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='rawgpsdata',
            name='approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_raw_data', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='rawgpsdata',
            name='status',
            field=models.CharField(choices=[('pending', 'در انتظار تایید'), ('approved', 'تایید شده'), ('rejected', 'رد شده'), ('processed', 'پردازش شده')], default='pending', help_text='Approval status', max_length=20),
        ),
    ]