import logging
from ..handlers.factory import ProtocolFactory
from ..models import Device

class CommunicationService:
    def __init__(self):
        self.handlers = {}  # Mapping from device_id to handler instance

    def get_handler(self, device: Device):
        if device.id in self.handlers:
            return self.handlers[device.id]

        protocol_type = device.protocol.protocol_type.lower()
        kwargs = device.config_settings.copy()

        # Add port if assigned and not in config
        if 'port' not in kwargs and device.assigned_port:
            kwargs['port'] = device.assigned_port

        # Add other protocol-specific configs if needed
        if protocol_type == 'mqtt':
            if 'topic' not in kwargs:
                kwargs['topic'] = f'devices/{device.device_id or device.imei}'

        elif protocol_type == 'http':
            if 'url' not in kwargs:
                kwargs['url'] = 'http://default-url.com'  # Placeholder, adjust as needed

        handler = ProtocolFactory.create_handler(device, protocol_type, **kwargs)
        self.handlers[device.id] = handler
        return handler

    def start_communication(self, device: Device):
        handler = self.get_handler(device)
        handler.connect()

    def stop_communication(self, device: Device):
        if device.id in self.handlers:
            handler = self.handlers[device.id]
            handler.disconnect()
            del self.handlers[device.id]

    def handle_data(self, device: Device):
        handler = self.get_handler(device)
        data = handler.receive_data()
        logging.info(f"Data received from device {device.id}: {data}")
        # TODO: Process the data, e.g., parse and save to database
        return data