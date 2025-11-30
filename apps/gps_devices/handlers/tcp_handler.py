import logging
import threading
import socket
from . import ProtocolHandler
from ..models import RawGPSData

class TCPHandler(ProtocolHandler):
    def __init__(self, device, host, port):
        super().__init__(device)
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        print(f"Connected to {self.host}:{self.port}")

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
        if self.sock:
            data = self.sock.recv(1024)
            decoded_data = data.decode('utf-8')
            logging.info(f"Raw TCP data received: {decoded_data}")
            # Get source IP if possible
            try:
                source_ip = self.sock.getpeername()[0]
            except:
                source_ip = None
            # Save raw data asynchronously
            threading.Thread(target=self.save_raw_data, args=(decoded_data, source_ip)).start()
            return decoded_data
        return None

    def disconnect(self):
        if self.sock:
            self.sock.close()
            print("Disconnected")