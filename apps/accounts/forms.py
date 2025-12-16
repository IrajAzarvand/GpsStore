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
            pass
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


class AssignDevicesToSubuserForm(forms.Form):
    """
    Form for assigning devices to sub-users
    """

    subuser = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop('owner', None)
        if self.owner is None:
            self.owner = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)

        if self.owner:
            self.fields['subuser'].queryset = User.objects.filter(
                is_subuser_of=self.owner,
                is_active=True,
            )
            self.fields['devices'].queryset = Device.objects.filter(
                owner=self.owner,
                status='active',
            ).exclude(expires_at__lt=timezone.now())

    def save(self):
        subuser = self.cleaned_data['subuser']
        devices = self.cleaned_data.get('devices')
        device_ids = set(d.id for d in devices)

        # Unassign devices currently assigned to this subuser but not selected anymore
        Device.objects.filter(
            owner=self.owner,
            assigned_subuser=subuser,
        ).exclude(id__in=device_ids).update(assigned_subuser=None)

        # Assign selected devices to this subuser
        if device_ids:
            Device.objects.filter(
                owner=self.owner,
                id__in=device_ids,
            ).update(assigned_subuser=subuser)

        return subuser


class SubUserForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    assigned_devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'is_active')

    def __init__(self, *args, **kwargs):
        self.owner = kwargs.pop('owner', None)
        super().__init__(*args, **kwargs)

        self.fields['password'].required = not bool(self.instance and self.instance.pk)

        for field_name in self.fields:
            if field_name in ('assigned_devices', 'password'):
                continue
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})

        effective_owner = self.owner or getattr(self.instance, 'is_subuser_of', None)
        if effective_owner:
            self.fields['assigned_devices'].queryset = Device.objects.filter(
                owner=effective_owner,
                status='active',
            ).exclude(expires_at__lt=timezone.now())

        if self.instance and self.instance.pk:
            self.initial['assigned_devices'] = Device.objects.filter(assigned_subuser=self.instance)

    def save(self, commit=True):
        user = super().save(commit=False)

        if self.owner is not None:
            user.is_subuser_of = self.owner

        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)

        if commit:
            user.save()

            effective_owner = self.owner or getattr(user, 'is_subuser_of', None)
            selected_devices = self.cleaned_data.get('assigned_devices')
            selected_ids = set(d.id for d in selected_devices)

            if effective_owner:
                Device.objects.filter(
                    owner=effective_owner,
                    assigned_subuser=user,
                ).exclude(id__in=selected_ids).update(assigned_subuser=None)

                if selected_ids:
                    Device.objects.filter(
                        owner=effective_owner,
                        id__in=selected_ids,
                    ).update(assigned_subuser=user)

        return user