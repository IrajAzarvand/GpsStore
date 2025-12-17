from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required

from apps.accounts.models import User
from apps.accounts.forms import AssignDevicesToSubuserForm, SubUserForm
from apps.gps_devices.models import Device, get_visible_devices_queryset
from django.http import HttpResponseForbidden
from django.db.models import Count

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('products:home')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('products:home')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('products:home')

@login_required
def dashboard_view(request):
    if getattr(request.user, 'is_subuser_of_id', None):
        return redirect('accounts:subuser_dashboard')
    return redirect('accounts:customer_dashboard')


@login_required
def customer_dashboard(request):
    if getattr(request.user, 'is_subuser_of_id', None):
        return HttpResponseForbidden()

    devices = get_visible_devices_queryset(request.user, only_active=True)
    sub_users = User.objects.filter(is_subuser_of=request.user, is_active=True).annotate(
        assigned_devices_count=Count('subuser_assigned_devices')
    )

    context = {
        'devices': devices,
        'total_devices': devices.count(),
        'sub_users': sub_users,
        'total_sub_users': sub_users.count(),
    }
    return render(request, 'accounts/customer_dashboard.html', context)


@login_required
def subuser_dashboard(request):
    if not getattr(request.user, 'is_subuser_of_id', None):
        return HttpResponseForbidden()

    assigned_devices = get_visible_devices_queryset(request.user, only_active=True)
    context = {
        'assigned_devices': assigned_devices,
        'total_devices': assigned_devices.count(),
    }
    return render(request, 'accounts/subuser_dashboard.html', context)


@login_required
def subuser_add(request):
    if getattr(request.user, 'is_subuser_of_id', None):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = SubUserForm(request.POST, owner=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:customer_dashboard')
    else:
        form = SubUserForm(owner=request.user)
    return render(request, 'accounts/subuser_form.html', {'form': form})


@login_required
def subuser_edit(request, pk):
    if getattr(request.user, 'is_subuser_of_id', None):
        return HttpResponseForbidden()

    subuser = User.objects.filter(pk=pk, is_subuser_of=request.user).first()
    if not subuser:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = SubUserForm(request.POST, instance=subuser, owner=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:customer_dashboard')
    else:
        form = SubUserForm(instance=subuser, owner=request.user)
    return render(request, 'accounts/subuser_form.html', {'form': form})


@login_required
def subuser_delete(request, pk):
    if getattr(request.user, 'is_subuser_of_id', None):
        return HttpResponseForbidden()

    subuser = User.objects.filter(pk=pk, is_subuser_of=request.user).first()
    if not subuser:
        return HttpResponseForbidden()

    if request.method == 'POST':
        Device.objects.filter(owner=request.user, assigned_subuser=subuser).update(assigned_subuser=None)
        subuser.delete()
        return redirect('accounts:customer_dashboard')

    return render(request, 'accounts/subuser_confirm_delete.html', {'subuser': subuser})


@login_required
def assign_devices(request):
    if getattr(request.user, 'is_subuser_of_id', None):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = AssignDevicesToSubuserForm(request.POST, owner=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:customer_dashboard')
    else:
        form = AssignDevicesToSubuserForm(owner=request.user)

    return render(request, 'accounts/assign_devices.html', {'form': form})
