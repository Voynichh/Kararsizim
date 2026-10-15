from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import User


class UserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "username")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserCreationForm
    ordering = ("-date_joined",)
    list_display = ("username", "email", "is_staff", "date_joined", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (
            "Yetkiler",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Önemli tarihler", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "usable_password", "password1", "password2"),
            },
        ),
    )
