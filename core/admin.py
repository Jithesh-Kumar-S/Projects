from django.contrib import admin

from .models import Profile, ServiceListing, ExchangeRequest, Transaction, Rating, Message


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "credits", "created_at")
    search_fields = ("user__username", "location")


@admin.register(ServiceListing)
class ServiceListingAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "category", "duration_hours", "is_active", "created_at")
    list_filter = ("category", "is_active")
    search_fields = ("title", "skills", "user__username")


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "requester", "provider", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("requester__username", "provider__username", "listing__title")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transaction_type", "created_at")
    list_filter = ("transaction_type",)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "stars", "created_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("exchange", "sender", "created_at")
