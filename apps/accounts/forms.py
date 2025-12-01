from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from apps.accounts.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import UserDevice
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