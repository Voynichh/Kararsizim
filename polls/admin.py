from django.contrib import admin

from .models import MAX_OPTIONS, MIN_OPTIONS, Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    min_num = MIN_OPTIONS
    max_num = MAX_OPTIONS
    validate_min = True
    validate_max = True
    ordering = ("order",)


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "created_at")
    search_fields = ("question", "author__username")
    raw_id_fields = ("author",)
    date_hierarchy = "created_at"
    inlines = [OptionInline]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    """Salt okunur. Oy gizliligi: kullanici ve voter_key admin arayuzunde de gosterilmez."""

    list_display = ("poll", "option", "created_at")
    list_filter = ("created_at",)
    fields = ("poll", "option", "created_at")
    readonly_fields = ("poll", "option", "created_at")
    list_select_related = ("poll", "option")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
