from django.contrib import admin

from .models import MAX_OPTIONS, MIN_OPTIONS, Option, Poll


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
