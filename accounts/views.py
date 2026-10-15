from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core import ratelimit
from core.net import get_client_ip, get_safe_next
from polls.utils import anonymize_votes

from .forms import DeleteAccountForm, LoginForm, PasswordChangeForm, SignupForm


def signup(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    next_url = get_safe_next(request)
    if request.method == "POST":
        if ratelimit.hit("signup_ip", get_client_ip(request), ratelimit.SIGNUP_IP):
            return ratelimit.rate_limited_response(request)
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                # Eszamanli kayit gibi nadir durumlar: ayrinti verilmez.
                form.add_error(None, "Kayıt oluşturulamadı. Bilgilerini kontrol edip tekrar dene.")
            else:
                login(request, user)
                messages.success(request, f"Hoş geldin, @{user.username}!")
                return redirect(next_url or settings.LOGIN_REDIRECT_URL)
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form, "next": next_url})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    next_url = get_safe_next(request)
    if request.method == "POST":
        ip = get_client_ip(request)
        email = (request.POST.get("email") or "").strip().lower()[:254]
        if ratelimit.is_limited("login_ip", ip, ratelimit.LOGIN_IP) or (
            email and ratelimit.is_limited("login_email", email, ratelimit.LOGIN_EMAIL)
        ):
            return ratelimit.rate_limited_response(request)
        form = LoginForm(request, request.POST)
        if form.is_valid():
            login(request, form.user)
            return redirect(next_url or settings.LOGIN_REDIRECT_URL)
        # Yalnizca basarisiz denemeler sayilir.
        ratelimit.record("login_ip", ip, ratelimit.LOGIN_IP)
        if email:
            ratelimit.record("login_email", email, ratelimit.LOGIN_EMAIL)
    else:
        form = LoginForm(request)
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Çıkış yaptın.")
    return redirect(settings.LOGOUT_REDIRECT_URL)


@login_required
def settings_view(request):
    return render(request, "accounts/settings.html")


@login_required
def password_change(request):
    if request.method == "POST":
        if ratelimit.hit(
            "account_sensitive", request.user.pk, ratelimit.ACCOUNT_SENSITIVE_USER
        ):
            return ratelimit.rate_limited_response(request)
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Diger cihazlardaki oturumlar sona erer, mevcut oturum acik kalir.
            update_session_auth_hash(request, user)
            messages.success(request, "Parolan değiştirildi.")
            return redirect("accounts:settings")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def delete_account(request):
    if request.method == "POST":
        if ratelimit.hit(
            "account_sensitive", request.user.pk, ratelimit.ACCOUNT_SENSITIVE_USER
        ):
            return ratelimit.rate_limited_response(request)
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            with transaction.atomic():
                # Baska anketlere verilen oylar sayimda kalir ama kisiyle baglantisi kopar
                # (user=NULL, voter_key="d:<uuid4>"). Kullanicinin anketleri ve onlara gelen
                # oylar CASCADE ile silinir.
                anonymize_votes(user)
                user.delete()
            logout(request)
            messages.success(request, "Hesabın silindi.")
            return redirect(settings.LOGOUT_REDIRECT_URL)
    else:
        form = DeleteAccountForm(request.user)
    return render(request, "accounts/delete_account.html", {"form": form})
