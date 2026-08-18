from django.contrib import messages as flash
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404

from .forms import (
    SignUpForm, ProfileForm, ServiceListingForm, ExchangeRequestForm, RatingForm, MessageForm,
)
from .models import ServiceListing, Profile, ExchangeRequest, Transaction, Rating, Message
from .recommend import get_recommendations, find_complementary_users


# ---------------------------------------------------------------- general --
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    recent = ServiceListing.objects.filter(is_active=True)[:6]
    return render(request, "core/home.html", {"recent": recent})


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user)
            Transaction.objects.create(
                user=user, amount=Profile._meta.get_field("credits").default,
                transaction_type="bonus", note="Signup bonus",
            )
            login(request, user)
            flash.success(request, "Welcome! You start with a few free credits — go list a skill.")
            return redirect("dashboard")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


# ------------------------------------------------------------- dashboard --
@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    recommended_listings = get_recommendations(request.user, top_n=5)
    recommended_people = find_complementary_users(request.user, top_n=5)
    my_listings = ServiceListing.objects.filter(user=request.user)
    pending_received = ExchangeRequest.objects.filter(provider=request.user, status="pending")
    active_exchanges = ExchangeRequest.objects.filter(
        Q(requester=request.user) | Q(provider=request.user)
    ).exclude(status__in=["completed", "rejected", "cancelled"])

    return render(request, "core/dashboard.html", {
        "profile": profile,
        "recommended_listings": recommended_listings,
        "recommended_people": recommended_people,
        "my_listings": my_listings,
        "pending_received": pending_received,
        "active_exchanges": active_exchanges,
    })


@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            flash.success(request, "Profile updated.")
            return redirect("dashboard")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "core/profile_edit.html", {"form": form})


def public_profile(request, username):
    person = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=person)
    listings = ServiceListing.objects.filter(user=person, is_active=True)
    ratings = Rating.objects.filter(to_user=person)
    return render(request, "core/public_profile.html", {
        "person": person, "profile": profile, "listings": listings, "ratings": ratings,
    })


# --------------------------------------------------------------- listings --
def listing_list(request):
    listings = ServiceListing.objects.filter(is_active=True)
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    location = request.GET.get("location", "").strip()

    if query:
        listings = listings.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(skills__icontains=query)
        )
    if category:
        listings = listings.filter(category=category)
    if location:
        listings = listings.filter(location__icontains=location)

    return render(request, "core/listing_list.html", {
        "listings": listings, "query": query, "category": category, "location": location,
        "categories": ServiceListing.CATEGORY_CHOICES,
    })


def listing_detail(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk)
    already_requested = False
    if request.user.is_authenticated:
        already_requested = ExchangeRequest.objects.filter(
            listing=listing, requester=request.user, status__in=["pending", "accepted", "scheduled"]
        ).exists()
    return render(request, "core/listing_detail.html", {
        "listing": listing, "already_requested": already_requested,
    })


@login_required
def listing_create(request):
    if request.method == "POST":
        form = ServiceListingForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.user = request.user
            listing.save()
            flash.success(request, "Your service is live.")
            return redirect("listing_detail", pk=listing.pk)
    else:
        form = ServiceListingForm()
    return render(request, "core/listing_form.html", {"form": form, "mode": "Create"})


@login_required
def listing_edit(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk, user=request.user)
    if request.method == "POST":
        form = ServiceListingForm(request.POST, instance=listing)
        if form.is_valid():
            form.save()
            flash.success(request, "Listing updated.")
            return redirect("listing_detail", pk=listing.pk)
    else:
        form = ServiceListingForm(instance=listing)
    return render(request, "core/listing_form.html", {"form": form, "mode": "Edit"})


@login_required
def listing_delete(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk, user=request.user)
    if request.method == "POST":
        listing.delete()
        flash.info(request, "Listing removed.")
        return redirect("dashboard")
    return render(request, "core/listing_confirm_delete.html", {"listing": listing})


# ---------------------------------------------------------- exchange flow --
@login_required
def request_create(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk, is_active=True)
    if listing.user == request.user:
        flash.error(request, "You can't request your own listing.")
        return redirect("listing_detail", pk=pk)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.credits < listing.duration_hours:
        flash.error(request, "Not enough credits for this exchange yet. Offer a service first to earn some.")
        return redirect("listing_detail", pk=pk)

    if request.method == "POST":
        form = ExchangeRequestForm(request.POST)
        if form.is_valid():
            exchange = form.save(commit=False)
            exchange.listing = listing
            exchange.requester = request.user
            exchange.provider = listing.user
            exchange.save()
            flash.success(request, "Request sent!")
            return redirect("request_detail", pk=exchange.pk)
    else:
        form = ExchangeRequestForm()
    return render(request, "core/request_form.html", {"form": form, "listing": listing})


@login_required
def request_list(request):
    sent = ExchangeRequest.objects.filter(requester=request.user)
    received = ExchangeRequest.objects.filter(provider=request.user)
    return render(request, "core/request_list.html", {"sent": sent, "received": received})


@login_required
def request_detail(request, pk):
    exchange = get_object_or_404(ExchangeRequest, pk=pk)
    if request.user not in (exchange.requester, exchange.provider):
        flash.error(request, "You don't have access to that exchange.")
        return redirect("dashboard")

    other_user = exchange.provider if request.user == exchange.requester else exchange.requester
    thread = exchange.messages.all()
    my_rating = Rating.objects.filter(exchange=exchange, from_user=request.user).first()

    if request.method == "POST" and "text" in request.POST:
        msg_form = MessageForm(request.POST)
        if msg_form.is_valid():
            m = msg_form.save(commit=False)
            m.exchange = exchange
            m.sender = request.user
            m.save()
            return redirect("request_detail", pk=pk)
    else:
        msg_form = MessageForm()

    return render(request, "core/request_detail.html", {
        "exchange": exchange, "other_user": other_user, "thread": thread,
        "msg_form": msg_form, "my_rating": my_rating,
    })


@login_required
def request_update_status(request, pk, new_status):
    exchange = get_object_or_404(ExchangeRequest, pk=pk)

    # Only the provider can accept/reject; either party can cancel; both can mark complete.
    if new_status in ("accepted", "rejected") and request.user != exchange.provider:
        flash.error(request, "Only the provider can respond to this request.")
        return redirect("request_detail", pk=pk)
    if new_status == "cancelled" and request.user not in (exchange.requester, exchange.provider):
        flash.error(request, "Not allowed.")
        return redirect("request_detail", pk=pk)

    if new_status == "completed":
        _complete_exchange(exchange)
    else:
        exchange.status = new_status
        exchange.save()

    flash.success(request, f"Exchange marked as {new_status}.")
    return redirect("request_detail", pk=pk)


def _complete_exchange(exchange):
    """Move credits from requester to provider and close out the exchange."""
    if exchange.status == "completed":
        return  # already settled, don't double-charge
    hours = exchange.listing.duration_hours
    requester_profile, _ = Profile.objects.get_or_create(user=exchange.requester)
    provider_profile, _ = Profile.objects.get_or_create(user=exchange.provider)

    requester_profile.credits -= hours
    provider_profile.credits += hours
    requester_profile.save()
    provider_profile.save()

    Transaction.objects.create(
        user=exchange.requester, amount=-hours, transaction_type="spend",
        exchange=exchange, note=f"Received: {exchange.listing.title}",
    )
    Transaction.objects.create(
        user=exchange.provider, amount=hours, transaction_type="earn",
        exchange=exchange, note=f"Provided: {exchange.listing.title}",
    )

    exchange.status = "completed"
    exchange.save()


@login_required
def rating_create(request, pk):
    exchange = get_object_or_404(ExchangeRequest, pk=pk, status="completed")
    if request.user not in (exchange.requester, exchange.provider):
        flash.error(request, "Not allowed.")
        return redirect("dashboard")
    to_user = exchange.provider if request.user == exchange.requester else exchange.requester

    if request.method == "POST":
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.exchange = exchange
            rating.from_user = request.user
            rating.to_user = to_user
            rating.save()
            flash.success(request, "Thanks for the feedback!")
            return redirect("request_detail", pk=pk)
    else:
        form = RatingForm()
    return render(request, "core/rating_form.html", {"form": form, "exchange": exchange, "to_user": to_user})


# --------------------------------------------------------------- wallet --
@login_required
def wallet(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(user=request.user)
    return render(request, "core/wallet.html", {"profile": profile, "transactions": transactions})


# ------------------------------------------------------ simple admin view --
def _is_staff(user):
    return user.is_staff


@user_passes_test(_is_staff)
def admin_analytics(request):
    total_users = User.objects.count()
    total_listings = ServiceListing.objects.count()
    total_exchanges = ExchangeRequest.objects.count()
    completed = ExchangeRequest.objects.filter(status="completed").count()
    disputed = ExchangeRequest.objects.filter(status="disputed")
    category_counts = {
        label: ServiceListing.objects.filter(category=key).count()
        for key, label in ServiceListing.CATEGORY_CHOICES
    }
    success_rate = round((completed / total_exchanges) * 100, 1) if total_exchanges else 0

    return render(request, "core/admin_analytics.html", {
        "total_users": total_users, "total_listings": total_listings,
        "total_exchanges": total_exchanges, "completed": completed,
        "success_rate": success_rate, "disputed": disputed,
        "category_counts": category_counts,
    })


def user_logout(request):
    logout(request)
    return redirect('login')  # or redirect to 'signup' if needed