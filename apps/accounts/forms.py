from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import UserProfile, Address, Customer, SubUser
from apps.gps_devices.models import Device


class UserRegistrationForm(UserCreationForm):
    """
    User registration form with profile fields
    """
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            # Create profile with phone number (only if it doesn't exist)
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'phone_number': self.cleaned_data['phone_number']}
            )
        return user


class UserLoginForm(AuthenticationForm):
    """
    Custom login form
    """
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Username or Email')})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': _('Password')})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})


class UserProfileForm(forms.ModelForm):
    """
    User profile form
    """
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = UserProfile
        fields = ('phone_number', 'date_of_birth', 'avatar')
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            # Update user fields
            user = profile.user
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.save()
            profile.save()
        return profile


class AddressForm(forms.ModelForm):
    """
    Address form
    """
    class Meta:
        model = Address
        fields = ('address_type', 'street_address', 'city', 'state', 'postal_code', 'country', 'is_default')
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-control'}),
            'street_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'value': 'Iran'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default country
        self.fields['country'].initial = 'Iran'

    def save(self, commit=True):
        address = super().save(commit=False)
        if commit:
            # If this is set as default, unset other defaults for this user and type
            if address.is_default:
                Address.objects.filter(
                    user=address.user,
                    address_type=address.address_type,
                    is_default=True
                ).exclude(pk=address.pk).update(is_default=False)
            address.save()
        return address


class SubUserForm(forms.ModelForm):
    """
    Form for creating and editing sub-users
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
        help_text="Password for the sub-user account"
    )

    class Meta:
        model = SubUser
        fields = ('username', 'email', 'assigned_devices', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'assigned_devices': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        if self.customer:
            # Limit devices to customer's devices
            self.fields['assigned_devices'].queryset = Device.objects.filter(
                customer=self.customer,
                status='active'
            ).exclude(expires_at__lt=timezone.now())  # Only active subscriptions

    def save(self, commit=True):
        subuser = super().save(commit=False)
        if self.customer:
            subuser.customer = self.customer
        if commit:
            subuser.save()
            self.save_m2m()
        return subuser


class DeviceAssignmentForm(forms.Form):
    """
    Form for assigning devices to sub-users
    """
    subuser = forms.ModelChoiceField(
        queryset=SubUser.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        if self.customer:
            self.fields['subuser'].queryset = SubUser.objects.filter(customer=self.customer)
            self.fields['devices'].queryset = Device.objects.filter(
                customer=self.customer,
                status='active'
            ).exclude(expires_at__lt=timezone.now())

    def save(self):
        subuser = self.cleaned_data['subuser']
        devices = self.cleaned_data['devices']
        subuser.assigned_devices.set(devices)
        subuser.save()
        return subuser