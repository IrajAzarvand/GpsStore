from abc import ABC, abstractmethod

class ProtocolHandler(ABC):
    def __init__(self, device):
        self.device = device
        self.protocol = device.protocol

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def receive_data(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass