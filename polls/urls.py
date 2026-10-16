from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("anket/yeni/", views.create, name="create"),
    path("anket/sonuclar/", views.results, name="results"),
    path("anket/<int:pk>/", views.detail, name="detail"),
    path("anket/<int:pk>/oy/", views.vote, name="vote"),
    path("anket/<int:pk>/sil/", views.delete, name="delete"),
]
