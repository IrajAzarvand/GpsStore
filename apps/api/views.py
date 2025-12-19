from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from .serializers import SubuserCreateSerializer
from apps.accounts.models import User
from apps.gps_devices.models import Device
from apps.gps_devices.views import _sync_userdevice_from_device, _ws_broadcast_device_assignment

# Create your views here.

class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'ok': True, 'service': 'GpsStore API', 'version': 'v1'})

class SubuserCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubuserCreateSerializer(data=request.data, context={'owner': request.user})
        if not serializer.is_valid():
            return Response({'ok': False, 'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            subuser = serializer.save()
        except Exception:
            return Response({'ok': False, 'error': 'create_failed'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'ok': True,
                'subuser': {
                    'id': subuser.id,
                    'username': subuser.username,
                    'name': subuser.get_full_name() or subuser.username,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class DeviceAssignOwnerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False)):
            return Response({'ok': False, 'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        device_id = request.data.get('device_id')
        owner_id = request.data.get('owner_id')
        new_username = request.data.get('new_username')
        new_password = request.data.get('new_password')
        new_first_name = request.data.get('new_first_name', '')
        new_last_name = request.data.get('new_last_name', '')

        if not device_id:
            return Response({'ok': False, 'error': 'device_id_required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device_id_int = int(device_id)
        except (TypeError, ValueError):
            return Response({'ok': False, 'error': 'device_id_invalid'}, status=status.HTTP_400_BAD_REQUEST)

        device = Device.objects.filter(id=device_id_int).first()
        if not device:
            return Response({'ok': False, 'error': 'device_not_found'}, status=status.HTTP_404_NOT_FOUND)

        old_owner_id = device.owner_id
        old_assigned_subuser_id = device.assigned_subuser_id

        owner = None
        if owner_id:
            try:
                owner_id_int = int(owner_id)
            except (TypeError, ValueError):
                return Response({'ok': False, 'error': 'owner_id_invalid'}, status=status.HTTP_400_BAD_REQUEST)

            owner = User.objects.filter(id=owner_id_int, is_subuser_of__isnull=True, is_active=True).first()
            if not owner:
                return Response({'ok': False, 'error': 'owner_not_found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            if not (new_username and new_password):
                return Response({'ok': False, 'error': 'owner_id_or_new_user_required'}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(username=new_username).exists():
                return Response({'ok': False, 'error': 'username_exists'}, status=status.HTTP_400_BAD_REQUEST)

            owner = User.objects.create_user(
                username=new_username,
                password=new_password,
                first_name=new_first_name,
                last_name=new_last_name,
                is_active=True,
            )

        Device.objects.filter(id=device.id).update(
            owner=owner,
            assigned_subuser=None,
            assigned_by=request.user,
            updated_at=timezone.now(),
        )

        _sync_userdevice_from_device(actor_user=request.user, device_id=device.id)

        _ws_broadcast_device_assignment(
            device_id=device.id,
            owner_id=owner.id if owner else None,
            assigned_subuser_id=None,
            old_owner_id=old_owner_id,
            old_assigned_subuser_id=old_assigned_subuser_id,
            action='owner_changed',
        )

        return Response({'ok': True, 'device_id': device.id, 'owner_id': owner.id})


class DeviceAssignSubuserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, 'is_subuser_of_id', None):
            return Response({'ok': False, 'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        device_id = request.data.get('device_id')
        subuser_id = request.data.get('subuser_id')

        if not device_id:
            return Response({'ok': False, 'error': 'device_id_required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device_id_int = int(device_id)
        except (TypeError, ValueError):
            return Response({'ok': False, 'error': 'device_id_invalid'}, status=status.HTTP_400_BAD_REQUEST)

        device = Device.objects.filter(id=device_id_int, owner=request.user).first()
        if not device:
            return Response({'ok': False, 'error': 'device_not_found_or_forbidden'}, status=status.HTTP_404_NOT_FOUND)

        old_assigned_subuser_id = device.assigned_subuser_id

        if not subuser_id:
            Device.objects.filter(id=device.id).update(
                assigned_subuser=None,
                assigned_by=request.user,
                updated_at=timezone.now(),
            )

            _sync_userdevice_from_device(actor_user=request.user, device_id=device.id)

            _ws_broadcast_device_assignment(
                device_id=device.id,
                owner_id=request.user.id,
                assigned_subuser_id=None,
                old_owner_id=request.user.id,
                old_assigned_subuser_id=old_assigned_subuser_id,
                action='unassigned_subuser',
            )

            return Response({'ok': True, 'device_id': device.id, 'subuser_id': None})

        try:
            subuser_id_int = int(subuser_id)
        except (TypeError, ValueError):
            return Response({'ok': False, 'error': 'subuser_id_invalid'}, status=status.HTTP_400_BAD_REQUEST)

        subuser = User.objects.filter(id=subuser_id_int, is_subuser_of=request.user, is_active=True).first()
        if not subuser:
            return Response({'ok': False, 'error': 'subuser_not_found'}, status=status.HTTP_404_NOT_FOUND)

        Device.objects.filter(id=device.id).update(
            assigned_subuser=subuser,
            assigned_by=request.user,
            updated_at=timezone.now(),
        )

        _sync_userdevice_from_device(actor_user=request.user, device_id=device.id)

        _ws_broadcast_device_assignment(
            device_id=device.id,
            owner_id=request.user.id,
            assigned_subuser_id=subuser.id,
            old_owner_id=request.user.id,
            old_assigned_subuser_id=old_assigned_subuser_id,
            action='assigned_subuser',
        )

        return Response({'ok': True, 'device_id': device.id, 'subuser_id': subuser.id})
