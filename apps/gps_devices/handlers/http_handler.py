import logging
import threading
import requests
from . import ProtocolHandler
from ..models import RawGPSData

class HTTPHandler(ProtocolHandler):
    def __init__(self, device, url):
        super().__init__(device)
        self.url = url
        self.session = None

    def connect(self):
        self.session = requests.Session()
        print(f"Connected to {self.url}")

    def save_raw_data(self, raw_data, source_ip=None):
        RawGPSData.objects.create(
            device=self.device,
            protocol=self.protocol,
            raw_data=raw_data,
            ip_address=source_ip,
            error_message='',
            unknown_sections={}
        )

    def receive_data(self):
        if self.session:
            response = self.session.get(self.url)
            logging.info(f"Raw HTTP data received: {response.text}")
            # Save raw data asynchronously
            threading.Thread(target=self.save_raw_data, args=(response.text,)).start()
            return response.text
        return None

    def disconnect(self):
        if self.session:
            self.session.close()
            print("Disconnected")