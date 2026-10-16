import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core import ratelimit
from core.net import get_client_ip, get_safe_next

from .forms import PollForm
from .models import Option, Poll, Vote
from .utils import (
    attach_vote_state,
    polls_queryset,
    resolve_voter_key,
    results_payload,
    set_voter_cookie,
)

POLLS_PER_PAGE = 20
OPTION_ID_PATTERN = re.compile(r"^[0-9]{1,18}$")


def feed(request):
    paginator = Paginator(polls_queryset(), POLLS_PER_PAGE)
    # Gecersiz ya da aralik disi sayfa numarasi hata vermez; ilk/son sayfaya dusulur.
    page = paginator.get_page(request.GET.get("page"))
    polls = attach_vote_state(request, page.object_list)
    return render(
        request,
        "polls/feed.html",
        {"page": page, "polls": polls, "canonical_url": request.build_absolute_uri(request.path)},
    )


def detail(request, pk):
    poll = get_object_or_404(polls_queryset(), pk=pk)
    (poll,) = attach_vote_state(request, [poll])
    # Baglanti onizlemesi (Open Graph): soru ve secenekler. Sablonda otomatik kacislanir; oy sonucu icermez.
    options = " / ".join(option.text for option in poll.options.all())
    context = {
        "poll": poll,
        "og_title": poll.question,
        "meta_description": f"{options} — sen ne dersin?"[:200],
        # Kanonik adres: sorgu dizisi (?next=... vb.) olmadan.
        "canonical_url": request.build_absolute_uri(request.path),
    }
    return render(request, "polls/detail.html", context)


@login_required
def create(request):
    if request.method == "POST":
        # Hak atomik olarak ayrilir; yalnizca basarili kayitlar sayilir (gecersiz formda iade edilir).
        slot = ratelimit.reserve("poll_create", request.user.pk, ratelimit.POLL_CREATE_USER)
        if slot is None:
            return ratelimit.rate_limited_response(request)
        form = PollForm(request.POST)
        if form.is_valid():
            # Yazar her zaman oturumdaki kullanicidir; istekten okunmaz.
            poll = form.save(author=request.user)
            messages.success(request, "Anketin yayında!")
            return redirect("polls:detail", pk=poll.pk)
        ratelimit.release(slot)
    else:
        form = PollForm()
    return render(request, "polls/create.html", {"form": form})


@login_required
def delete(request, pk):
    # Yetki kontrolu sorgu seviyesinde: baskasinin anketi icin 404 doner.
    poll = get_object_or_404(polls_queryset(), pk=pk, author=request.user)
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anketin silindi.")
        return redirect("polls:feed")
    (poll,) = attach_vote_state(request, [poll])
    return render(request, "polls/confirm_delete.html", {"poll": poll})


RESULTS_MAX_IDS = 20


@require_GET
@never_cache
def results(request):
    """Sayfadaki anketlerin guncel sayilari (canli guncelleme icin).

    Gorunurluk kurali sayfalarla aynidir: toplam oy sayisi herkese, secenek bazli sonuclar yalnizca
    oy vermis kisiye ve anket sahibine verilir. Kullanici bilgisi, e-posta ve voter_key icermez.
    """
    ids = [
        int(part)
        for part in request.GET.get("ids", "").split(",")[:RESULTS_MAX_IDS]
        if OPTION_ID_PATTERN.match(part)
    ]
    items = []
    if ids:
        for poll in attach_vote_state(request, polls_queryset().filter(pk__in=ids)):
            item = {"id": poll.pk, "total_votes": poll.total_votes}
            if poll.show_results:
                item["options"] = [
                    {"id": o.pk, "votes": o.vote_count, "percent": o.percent}
                    for o in poll.options.all()
                ]
            items.append(item)
    return JsonResponse({"ok": True, "polls": items})


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def _vote_error(request, poll, status, message):
    if _wants_json(request):
        return JsonResponse({"ok": False, "error": message}, status=status)
    if status == 400:
        return render(request, "400.html", status=400)
    messages.error(request, message)
    return redirect("polls:detail", pk=poll.pk)


@require_POST
def vote(request, pk):
    # Her deneme sayilir (IP basina dakikada 30).
    if ratelimit.hit("vote_ip", get_client_ip(request), ratelimit.VOTE_IP):
        return ratelimit.rate_limited_response(request)

    poll = get_object_or_404(Poll, pk=pk)

    if request.user.is_authenticated and poll.author_id == request.user.pk:
        return _vote_error(request, poll, 403, "Kendi anketine oy veremezsin.")

    raw_option = request.POST.get("option", "")
    if not OPTION_ID_PATTERN.match(raw_option):
        return _vote_error(request, poll, 400, "Geçersiz seçenek.")
    # Secenek bu ankete ait olmali.
    option = Option.objects.filter(pk=int(raw_option), poll_id=poll.pk).first()
    if option is None:
        return _vote_error(request, poll, 400, "Geçersiz seçenek.")

    voter_key, new_anonymous_id = resolve_voter_key(request)
    already_voted = False
    try:
        with transaction.atomic():
            Vote.objects.create(
                poll=poll,
                option=option,
                user=request.user if request.user.is_authenticated else None,
                voter_key=voter_key,
            )
        selected_option_id = option.pk
    except IntegrityError:
        # Ayni kisi ayni ankete ikinci kez oy veremez (eszamanli istekler dahil).
        already_voted = True
        selected_option_id = (
            Vote.objects.filter(poll=poll, voter_key=voter_key)
            .values_list("option_id", flat=True)
            .first()
        )

    if _wants_json(request):
        fresh_poll = get_object_or_404(polls_queryset(), pk=poll.pk)
        response = JsonResponse(results_payload(fresh_poll, selected_option_id, already_voted))
    else:
        if already_voted:
            messages.info(request, "Bu ankete zaten oy verdin.")
        else:
            messages.success(request, "Oyun kaydedildi.")
        response = redirect(get_safe_next(request) or reverse("polls:detail", kwargs={"pk": poll.pk}))

    if new_anonymous_id and not already_voted:
        set_voter_cookie(response, new_anonymous_id)
    return response
