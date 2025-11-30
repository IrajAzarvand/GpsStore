import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, UpdateView, TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import UserProfile, Address, Customer, SubUser
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, AddressForm, SubUserForm, DeviceAssignmentForm
from apps.gps_devices.models import Device

logger = logging.getLogger(__name__)


class RegisterView(CreateView):
    """
    User registration view
    """
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        user = form.save()
        # Create UserProfile
        UserProfile.objects.create(user=user)
        messages.success(self.request, _('Account created successfully. Please log in.'))
        return super().form_valid(form)


class LoginView(TemplateView):
    """
    User login view
    """
    template_name = 'accounts/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = UserLoginForm()
        return context

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                logger.info(f"User {user.username} logged in successfully. Session key: {request.session.session_key}")
                messages.success(request, _('Welcome back!'))
                next_url = request.GET.get('next', 'accounts:dashboard')
                return redirect(next_url)
            else:
                logger.warning(f"Failed login attempt for username/email: {username}")
                messages.error(request, _('Invalid username or password.'))
        else:
            logger.warning(f"Invalid login form submission: {form.errors}")
            messages.error(request, _('Please correct the errors below.'))

        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


def logout_view(request):
    """
    User logout view
    """
    logger.info(f"User {request.user.username if request.user.is_authenticated else 'anonymous'} logged out. Session key before logout: {request.session.session_key}")
    logout(request)
    messages.success(request, _('You have been logged out successfully.'))
    return redirect('home')


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    User dashboard view
    """
    template_name = 'accounts/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.info(f"Dashboard accessed by {self.request.user.username}. Session key: {self.request.session.session_key}")
        user = self.request.user

        # Recent orders
        context['recent_orders'] = user.orders.all()[:5]

        # Active subscriptions
        context['active_subscriptions'] = user.subscriptions.filter(status='active')[:3]

        # GPS devices
        context['gps_devices'] = user.gps_devices.filter(status='active')[:5]

        # Statistics
        context['total_orders'] = user.orders.count()
        context['total_devices'] = user.gps_devices.count()
        context['active_devices'] = user.gps_devices.filter(status='active').count()
        context['pending_orders'] = user.orders.filter(status='pending').count()

        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    """
    User profile management view
    """
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user.profile

    def form_valid(self, form):
        messages.success(self.request, _('Profile updated successfully.'))
        return super().form_valid(form)


class AddressListView(LoginRequiredMixin, ListView):
    """
    User addresses list view
    """
    model = Address
    template_name = 'accounts/addresses.html'
    context_object_name = 'addresses'

    def get_queryset(self):
        return self.request.user.addresses.all()


class AddressCreateView(LoginRequiredMixin, CreateView):
    """
    Create new address view
    """
    model = Address
    form_class = AddressForm
    template_name = 'accounts/address_form.html'
    success_url = reverse_lazy('accounts:addresses')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, _('Address added successfully.'))
        return super().form_valid(form)


class AddressUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update address view
    """
    model = Address
    form_class = AddressForm
    template_name = 'accounts/address_form.html'
    success_url = reverse_lazy('accounts:addresses')

    def get_queryset(self):
        return self.request.user.addresses.all()

    def form_valid(self, form):
        messages.success(self.request, _('Address updated successfully.'))
        return super().form_valid(form)


def address_delete_view(request, pk):
    """
    Delete address view
    """
    logger.info(f"Address delete attempt by user {request.user.username if request.user.is_authenticated else 'anonymous'} for address pk={pk}")
    address = get_object_or_404(request.user.addresses, pk=pk)
    if request.method == 'POST':
        address.delete()
        messages.success(request, _('Address deleted successfully.'))
        return redirect('accounts:addresses')
    return render(request, 'accounts/address_confirm_delete.html', {'address': address})


# Password reset views
class CustomPasswordResetView(PasswordResetView):
    """
    Custom password reset view
    """
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('accounts:password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    """
    Password reset done view
    """
    template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Password reset confirm view
    """
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    """
    Password reset complete view
    """
    template_name = 'accounts/password_reset_complete.html'


class CustomerDashboardView(LoginRequiredMixin, TemplateView):
    """
    Customer dashboard for managing devices and sub-users
    """
    template_name = 'accounts/customer_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get customer (assuming user has customer relationship)
        try:
            customer = user.customer
        except AttributeError:
            # If no direct relationship, try to find customer by user profile or create logic
            # For now, assume customer exists
            customer = None

        if customer:
            # Get all devices for this customer with active subscriptions
            devices = Device.objects.filter(
                customer=customer,
                status='active'
            ).exclude(expires_at__lt=timezone.now())

            # Get sub-users
            sub_users = customer.sub_users.all()

            context.update({
                'customer': customer,
                'devices': devices,
                'sub_users': sub_users,
                'total_devices': devices.count(),
                'total_sub_users': sub_users.count(),
            })

        return context


class SubUserDashboardView(LoginRequiredMixin, TemplateView):
    """
    Sub-user dashboard for viewing assigned devices
    """
    template_name = 'accounts/subuser_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Find sub-user record
        try:
            subuser = SubUser.objects.get(username=user.username)
            assigned_devices = subuser.assigned_devices.filter(
                status='active'
            ).exclude(expires_at__lt=timezone.now())

            context.update({
                'subuser': subuser,
                'assigned_devices': assigned_devices,
                'total_devices': assigned_devices.count(),
            })
        except SubUser.DoesNotExist:
            # Not a sub-user
            context['error'] = 'شما دسترسی به این صفحه ندارید.'

        return context


class SubUserCreateView(LoginRequiredMixin, CreateView):
    """
    Create new sub-user
    """
    model = SubUser
    form_class = SubUserForm
    template_name = 'accounts/subuser_form.html'
    success_url = reverse_lazy('accounts:customer_dashboard')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        try:
            kwargs['customer'] = self.request.user.customer
        except AttributeError:
            pass
        return kwargs

    def form_valid(self, form):
        # Create Django user for sub-user
        from django.contrib.auth.models import User
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']

        # Create Django user
        user = User.objects.create_user(
            username=username,
            email=form.cleaned_data.get('email'),
            password=password
        )

        # Set sub-user's customer
        try:
            form.instance.customer = self.request.user.customer
        except AttributeError:
            pass

        response = super().form_valid(form)
        messages.success(self.request, f'کاربر زیرمجموعه {username} با موفقیت ایجاد شد.')
        return response


class SubUserUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update sub-user
    """
    model = SubUser
    form_class = SubUserForm
    template_name = 'accounts/subuser_form.html'
    success_url = reverse_lazy('accounts:customer_dashboard')

    def get_queryset(self):
        try:
            return self.request.user.customer.sub_users.all()
        except AttributeError:
            return SubUser.objects.none()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        try:
            kwargs['customer'] = self.request.user.customer
        except AttributeError:
            pass
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'کاربر زیرمجموعه {self.object.username} با موفقیت بروزرسانی شد.')
        return response


@login_required
def assign_devices_view(request):
    """
    Assign devices to sub-users
    """
    try:
        customer = request.user.customer
    except AttributeError:
        messages.error(request, 'شما دسترسی به این صفحه ندارید.')
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = DeviceAssignmentForm(request.POST, customer=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'دستگاه‌ها با موفقیت تخصیص یافتند.')
            return redirect('accounts:customer_dashboard')
    else:
        form = DeviceAssignmentForm(customer=customer)

    context = {
        'form': form,
        'customer': customer,
    }
    return render(request, 'accounts/assign_devices.html', context)


@login_required
def subuser_delete_view(request, pk):
    """
    Delete sub-user
    """
    try:
        customer = request.user.customer
        subuser = get_object_or_404(customer.sub_users, pk=pk)
    except AttributeError:
        messages.error(request, 'شما دسترسی به این صفحه ندارید.')
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        # Delete associated Django user
        try:
            user = User.objects.get(username=subuser.username)
            user.delete()
        except User.DoesNotExist:
            pass

        subuser.delete()
        messages.success(request, f'کاربر زیرمجموعه {subuser.username} حذف شد.')
        return redirect('accounts:customer_dashboard')

    return render(request, 'accounts/subuser_confirm_delete.html', {'subuser': subuser})
