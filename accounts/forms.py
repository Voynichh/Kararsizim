from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import User, username_validator

EMAIL_TAKEN_MESSAGE = "Bu e-posta ile kayıt oluşturulamadı. Zaten hesabın varsa giriş yap."
LOGIN_ERROR_MESSAGE = "E-posta veya parola hatalı."


class SignupForm(forms.Form):
    email = forms.EmailField(
        label="E-posta",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    username = forms.CharField(
        label="Kullanıcı adı",
        validators=[username_validator],
        help_text="3–20 karakter; harf, rakam ve _ kullanabilirsin. Herkese açık görünür.",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autocapitalize": "none",
                "spellcheck": "false",
                "minlength": "3",
                "maxlength": "20",
            }
        ),
    )
    password1 = forms.CharField(
        label="Parola",
        strip=False,
        help_text="En az 10 karakter.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Parola (tekrar)",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError(EMAIL_TAKEN_MESSAGE)
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Bu kullanıcı adı zaten alınmış.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2:
            if password1 != password2:
                self.add_error("password2", "Parolalar eşleşmiyor.")
            else:
                candidate = User(
                    email=cleaned.get("email", ""), username=cleaned.get("username", "")
                )
                try:
                    validate_password(password1, user=candidate)
                except ValidationError as error:
                    self.add_error("password1", error)
        return cleaned

    def save(self):
        with transaction.atomic():
            return User.objects.create_user(
                self.cleaned_data["email"],
                self.cleaned_data["username"],
                self.cleaned_data["password1"],
            )


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="E-posta",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Parola",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        password = cleaned.get("password")
        if email and password:
            user = authenticate(self.request, username=email.strip().lower(), password=password)
            if user is None:
                # Hangi alanin yanlis oldugu belirtilmez.
                raise ValidationError(LOGIN_ERROR_MESSAGE)
            self.user = user
        return cleaned


class PasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].help_text = "En az 10 karakter."


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Parolan",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Parola hatalı.")
        return password
