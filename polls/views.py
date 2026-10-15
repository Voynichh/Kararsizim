from django.shortcuts import render


def feed(request):
    # Faz 2'de anket akisi ile degistirilecek; simdilik bos durum gosterilir.
    return render(request, "polls/feed.html")
