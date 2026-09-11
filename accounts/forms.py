from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    class Meta:
        model = User
        fields = ("email", "role", "password1", "password2")
        widgets = {"role": forms.RadioSelect}


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"}))