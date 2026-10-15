from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kayit/", views.signup, name="signup"),
    path("giris/", views.login_view, name="login"),
    path("cikis/", views.logout_view, name="logout"),
    path("hesap/", views.settings_view, name="settings"),
    path("hesap/parola/", views.password_change, name="password_change"),
    path("hesap/sil/", views.delete_account, name="delete"),
]
