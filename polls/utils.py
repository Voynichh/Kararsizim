"""Oy verenin kimligi (voter_key), imzali anonim cerez ve sonuc hesaplari."""

import uuid

from django.conf import settings
from django.core.signing import BadSignature
from django.db.models import Count, Prefetch

from .models import Option, Poll, Vote

COOKIE_NAME = "kv_voter"
COOKIE_SALT = "kararsizim.voter"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 yil


# --- voter_key -------------------------------------------------------------


def _read_anonymous_id(request):
    """Imzali cerezdeki UUID'yi dondurur; yok, bozuk ya da gecersizse None."""
    try:
        value = request.get_signed_cookie(
            COOKIE_NAME, default=None, salt=COOKIE_SALT, max_age=COOKIE_MAX_AGE
        )
    except BadSignature:
        return None
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def get_voter_key(request):
    """Mevcut istegin voter_key'ini dondurur; olusturmaz. Tanimsiz anonim icin None."""
    if request.user.is_authenticated:
        return f"u:{request.user.pk}"
    anonymous_id = _read_anonymous_id(request)
    return f"a:{anonymous_id}" if anonymous_id else None


def resolve_voter_key(request):
    """(voter_key, yeni_anonim_id) dondurur. Yeni anonim kimlik uretildiyse cerezle gonderilmeli."""
    key = get_voter_key(request)
    if key:
        return key, None
    new_id = str(uuid.uuid4())
    return f"a:{new_id}", new_id


def set_voter_cookie(response, anonymous_id):
    response.set_signed_cookie(
        COOKIE_NAME,
        anonymous_id,
        salt=COOKIE_SALT,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )


def anonymize_votes(user):
    """Hesap silinirken oylari kisiyle baglantisiz birakir (oylar sayimda kalir)."""
    votes = list(Vote.objects.filter(user=user))
    for vote in votes:
        vote.user = None
        vote.voter_key = f"d:{uuid.uuid4()}"
    Vote.objects.bulk_update(votes, ["user", "voter_key"])


# --- Sorgular ve sonuc hesabi -----------------------------------------------


def polls_queryset():
    """Anketler + yazar + secenekler + oy sayilari; sorgu sayisi anket sayisindan bagimsiz."""
    # annotate(Count) GROUP BY yaptigi icin Meta.ordering devre disi kalir; siralama acik verilir.
    return (
        Poll.objects.select_related("author")
        .annotate(total_votes=Count("votes"))
        .order_by("-created_at", "-pk")
        .prefetch_related(
            Prefetch(
                "options",
                queryset=Option.objects.annotate(vote_count=Count("votes")).order_by("order"),
            )
        )
    )


def percent_of(votes, total):
    """Tam sayiya (yari yukari) yuvarlanmis yuzde; toplam 0 ise 0."""
    if not total:
        return 0
    return (votes * 200 + total) // (2 * total)


def attach_vote_state(request, polls):
    """Her ankete gosterim durumunu ekler. Oy verilmis olanlari tek sorguda alir (N+1 yok).

    Sonuclar yalnizca oy vermis kisiye ya da anket sahibine gosterilir.
    """
    polls = list(polls)
    key = get_voter_key(request)
    voted = {}
    if key and polls:
        voted = dict(
            Vote.objects.filter(voter_key=key, poll_id__in=[p.pk for p in polls]).values_list(
                "poll_id", "option_id"
            )
        )
    user_id = request.user.pk if request.user.is_authenticated else None
    for poll in polls:
        poll.voted_option_id = voted.get(poll.pk)
        poll.is_owner = user_id is not None and poll.author_id == user_id
        poll.show_results = poll.is_owner or poll.voted_option_id is not None
        if poll.show_results:
            annotate_results(poll, poll.voted_option_id)
    return polls


def annotate_results(poll, selected_option_id):
    options = list(poll.options.all())
    top = max((o.vote_count for o in options), default=0)
    for option in options:
        option.percent = percent_of(option.vote_count, poll.total_votes)
        option.is_top = top > 0 and option.vote_count == top
        option.is_mine = option.pk == selected_option_id


def results_payload(poll, selected_option_id, already_voted):
    """Oy sonrasi JSON govdesi. Kullanici bilgisi, e-posta ve voter_key icermez."""
    annotate_results(poll, selected_option_id)
    return {
        "ok": True,
        "already_voted": already_voted,
        "selected_option_id": selected_option_id,
        "total_votes": poll.total_votes,
        "options": [
            {
                "id": option.pk,
                "text": option.text,
                "votes": option.vote_count,
                "percent": option.percent,
            }
            for option in poll.options.all()
        ],
    }
