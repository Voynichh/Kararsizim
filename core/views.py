from django.shortcuts import render


def privacy(request):
    return render(request, "core/privacy.html")
