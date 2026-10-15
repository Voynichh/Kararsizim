from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("gizlilik/", views.privacy, name="privacy"),
]
