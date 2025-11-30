from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from apps.gps_devices.handlers.factory import ProtocolFactory
from apps.gps_devices.communication.service import CommunicationService
from apps.gps_devices.models import Device

class ProtocolHandlerViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def available_protocols(self, request):
        return Response({"protocols": ['tcp', 'mqtt', 'http']})

    @action(detail=False, methods=['post'])
    def test_handler(self, request):
        protocol_type = request.data.get('protocol_type')
        config = request.data.get('config', {})
        try:
            handler = ProtocolFactory.create_handler(protocol_type, **config)
            handler.connect()
            handler.disconnect()
            return Response({"status": "test successful"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def handle_device_data(self, request):
        device_id = request.data.get('device_id')
        device = Device.objects.get(id=device_id, user=request.user)
        service = CommunicationService()
        data = service.handle_data(device)
        return Response({"data": data})