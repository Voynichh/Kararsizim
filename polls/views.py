from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from core import ratelimit

from .forms import PollForm
from .models import Poll

POLLS_PER_PAGE = 20


def _polls_with_related():
    return Poll.objects.select_related("author").prefetch_related("options")


def feed(request):
    paginator = Paginator(_polls_with_related(), POLLS_PER_PAGE)
    # Gecersiz ya da aralik disi sayfa numarasi hata vermez; ilk/son sayfaya dusulur.
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "polls/feed.html", {"page": page})


def detail(request, pk):
    poll = get_object_or_404(_polls_with_related(), pk=pk)
    return render(request, "polls/detail.html", {"poll": poll})


@login_required
def create(request):
    if request.method == "POST":
        if ratelimit.is_limited("poll_create", request.user.pk, ratelimit.POLL_CREATE_USER):
            return ratelimit.rate_limited_response(request)
        form = PollForm(request.POST)
        if form.is_valid():
            # Yazar her zaman oturumdaki kullanicidir; istekten okunmaz.
            poll = form.save(author=request.user)
            ratelimit.record("poll_create", request.user.pk, ratelimit.POLL_CREATE_USER)
            messages.success(request, "Anketin yayında!")
            return redirect("polls:detail", pk=poll.pk)
    else:
        form = PollForm()
    return render(request, "polls/create.html", {"form": form})


@login_required
def delete(request, pk):
    # Yetki kontrolu sorgu seviyesinde: baskasinin anketi icin 404 doner.
    poll = get_object_or_404(Poll.objects.select_related("author"), pk=pk, author=request.user)
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anketin silindi.")
        return redirect("polls:feed")
    return render(request, "polls/confirm_delete.html", {"poll": poll})
