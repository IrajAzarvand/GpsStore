import os
from django import forms
from django.core.exceptions import ValidationError
from .models import Device, Protocol


class DeviceForm(forms.ModelForm):
    """
    Form for creating and editing GPS devices

    Default values for HQ (TCP-based) devices:
    - protocol: TCP protocol
    - config_settings: {"host": "localhost" (dev) or "bruna.ir" (prod), "port": 5000}

    Examples for other protocols:
    - MQTT: {"broker": "mqtt.example.com", "port": 1883, "topic": "gps/data", "username": "device", "password": "secret"}
    - HTTP: {"url": "https://api.example.com/gps", "method": "POST", "headers": {"Authorization": "Bearer token"}}
    """
    class Meta:
        model = Device
        fields = [
            'customer', 'product', 'device_type', 'name',
            'imei', 'device_id', 'serial_number',
            'protocol', 'firmware_version', 'config_settings',
            'status', 'activation_code'
        ]
        widgets = {
            'config_settings': forms.Textarea(attrs={'rows': 3}),
            'firmware_version': forms.TextInput(attrs={'placeholder': 'e.g., 1.2.3'}),
            'activation_code': forms.TextInput(attrs={'placeholder': 'Leave blank for auto-generation'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make customer field optional if editing existing device
        if self.instance and self.instance.pk:
            self.fields['customer'].required = False

        # Set default values for HQ (TCP) devices
        tcp_protocol = Protocol.objects.filter(protocol_type='tcp').first()
        if tcp_protocol:
            self.fields['protocol'].initial = tcp_protocol

        # Set host based on environment
        environment = os.getenv('ENVIRONMENT', 'development')
        host = 'bruna.ir' if environment == 'production' else 'localhost'
        self.fields['config_settings'].initial = {"host": host, "port": 5000}
        self.fields['config_settings'].help_text = (
            f"Device-specific configuration as JSON. "
            f"For TCP: {{'host': '{host}', 'port': 5000}}. "
            "For MQTT: {'broker': 'mqtt.example.com', 'port': 1883, 'topic': 'gps/data'}. "
            "For HTTP: {'url': 'https://api.example.com/gps', 'method': 'POST'}."
        )

    def clean_config_settings(self):
        config_settings = self.cleaned_data.get('config_settings')
        if config_settings:
            if not isinstance(config_settings, dict):
                raise ValidationError("config_settings must be a valid JSON object.")
        return config_settings

    def clean(self):
        cleaned_data = super().clean()
        imei = cleaned_data.get('imei')
        device_id = cleaned_data.get('device_id')

        if not imei and not device_id:
            raise ValidationError("Either IMEI or Device ID must be provided.")

        return cleaned_data


class DeviceRegistrationForm(forms.ModelForm):
    """
    Simplified form for device registration (user-facing)
    """
    class Meta:
        model = Device
        fields = ['name', 'imei', 'device_id', 'serial_number', 'activation_code']
        widgets = {
            'imei': forms.TextInput(attrs={'placeholder': '15-digit IMEI number'}),
            'device_id': forms.TextInput(attrs={'placeholder': 'Alternative device identifier'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'Device serial number'}),
            'activation_code': forms.TextInput(attrs={'placeholder': 'Activation code if provided'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        imei = cleaned_data.get('imei')
        device_id = cleaned_data.get('device_id')

        if not imei and not device_id:
            raise ValidationError("Either IMEI or Device ID must be provided.")

        return cleaned_data