import logging
import threading
try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    mqtt = None
from . import ProtocolHandler
from ..models import RawGPSData

class MQTTHandler(ProtocolHandler):
    def __init__(self, device, broker, port, topic):
        super().__init__(device)
        if not PAHO_AVAILABLE:
            raise ImportError("paho-mqtt is not installed. Please install it to use MQTT functionality.")
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.received_data = None

    def save_raw_data(self, raw_data, source_ip=None):
        RawGPSData.objects.create(
            device=self.device,
            protocol=self.protocol,
            raw_data=raw_data,
            ip_address=source_ip,
            error_message='',
            unknown_sections={}
        )

    def connect(self):
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        print(f"Connected to MQTT broker {self.broker}:{self.port}")

    def receive_data(self):
        def on_message(client, userdata, msg):
            decoded_data = msg.payload.decode('utf-8')
            logging.info(f"Raw MQTT data received: {decoded_data}")
            self.received_data = decoded_data
            # Save raw data asynchronously
            threading.Thread(target=self.save_raw_data, args=(decoded_data,)).start()

        self.client.on_message = on_message
        self.client.subscribe(self.topic)
        # For simplicity, wait for a message (this is blocking for demo)
        self.client.loop(10)  # Wait up to 10 seconds for a message
        # Note: In real use, this should be non-blocking
        return self.received_data

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        print("Disconnected from MQTT broker")