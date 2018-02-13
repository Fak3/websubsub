from django.contrib import admin
from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'topic', 'subscribe_status', 'callback_urlname')
    list_filter = ('topic',)

