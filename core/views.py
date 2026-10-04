from django.contrib import messages as flash
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.db import DatabaseError, IntegrityError, transaction as db_transaction
from django.db.models import Avg, Count, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    SignUpForm, ProfileForm, ServiceListingForm, ExchangeRequestForm, DirectExchangeForm, RatingForm, MessageForm,
)
from .models import ServiceListing, Profile, ExchangeRequest, Transaction, Rating, Message
from .recommend import get_recommendations, find_complementary_users


class ProfileAwareLoginView(LoginView):
    """Send new or incomplete profiles through setup before honoring saved destinations."""

    def get_success_url(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        if not profile.onboarding_complete:
            return reverse("post_login")
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["session_expired"] = self.request.GET.get("session_expired") == "1"
        return context


# ---------------------------------------------------------------- general --
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    recent = _with_rating_summary(ServiceListing.objects.filter(is_active=True))[:6]
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
            return redirect("post_login")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


# ------------------------------------------------------------- dashboard --
@login_required
def post_login(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return redirect("dashboard" if profile.onboarding_complete else "onboarding")


def _available_skills():
    """Build choices from skills already used by this community."""
    values = set()
    for listing in ServiceListing.objects.values_list("skills", flat=True):
        values.update(part.strip() for part in listing.split(",") if part.strip())
    for value in Profile.objects.values_list("skills_offered", flat=True):
        values.update(part.strip() for part in value.split(",") if part.strip())
    for value in Profile.objects.values_list("skills_needed", flat=True):
        values.update(part.strip() for part in value.split(",") if part.strip())
    if not values:
        values.update(label for _, label in ServiceListing.CATEGORY_CHOICES)
    return sorted(values, key=str.casefold)


@login_required
def onboarding(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.onboarding_complete:
        return redirect("dashboard")
    if request.method == "POST":
        teach = request.POST.getlist("teach")
        learn = request.POST.getlist("learn")
        if not teach or not learn:
            flash.error(request, "Choose at least one skill in both lists to continue.")
        else:
            try:
                with db_transaction.atomic():
                    request.user.first_name = request.POST.get("display_name", "").strip()[:150]
                    request.user.save(update_fields=["first_name"])
                    profile.skills_offered = ", ".join(dict.fromkeys(s.strip() for s in teach if s.strip()))
                    profile.skills_needed = ", ".join(dict.fromkeys(s.strip() for s in learn if s.strip()))
                    profile.bio = request.POST.get("bio", "").strip()
                    profile.location = request.POST.get("location", "").strip()[:120]
                    profile.profile_picture = request.POST.get("profile_picture", "").strip()
                    profile.experience_level = request.POST.get("experience_level", "")
                    profile.availability = request.POST.get("availability", "").strip()[:160]
                    profile.onboarding_complete = True
                    profile.save()
            except DatabaseError:
                flash.error(request, "We couldn’t save your profile just now. Please try again.")
            else:
                flash.success(request, "Your profile is ready. Welcome to the community!")
                return redirect("dashboard")
    teach_selected = request.POST.getlist("teach") if request.method == "POST" else [part.strip() for part in profile.skills_offered.split(",") if part.strip()]
    learn_selected = request.POST.getlist("learn") if request.method == "POST" else [part.strip() for part in profile.skills_needed.split(",") if part.strip()]
    return render(request, "core/onboarding.html", {
        "skills": _available_skills(), "profile": profile,
        "teach_selected": teach_selected, "learn_selected": learn_selected,
        "form_errors": "Choose at least one skill in both lists to continue." if request.method == "POST" else "",
    })


@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    recommended_listings = get_recommendations(request.user, top_n=5)
    recommended_people = find_complementary_users(request.user, top_n=5)
    my_listings = _with_rating_summary(ServiceListing.objects.filter(user=request.user))
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
            request.user.first_name = form.cleaned_data["display_name"]
            request.user.save(update_fields=["first_name"])
            flash.success(request, "Profile updated.")
            return redirect("dashboard")
    else:
        form = ProfileForm(instance=profile)
        form.fields["display_name"].initial = request.user.first_name
    return render(request, "core/profile_edit.html", {"form": form})


def public_profile(request, username):
    person = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=person)
    listings = _with_rating_summary(ServiceListing.objects.filter(user=person, is_active=True))
    ratings = Rating.objects.filter(to_user=person).select_related("from_user")
    rating_summary = ratings.aggregate(average=Avg("stars"), count=Count("id"))
    return render(request, "core/public_profile.html", {
        "person": person, "profile": profile, "listings": listings, "ratings": ratings,
        "rating_average": round(rating_summary["average"], 1) if rating_summary["average"] is not None else None,
        "rating_count": rating_summary["count"],
    })


# --------------------------------------------------------------- listings --
def listing_list(request):
    listings = _with_rating_summary(ServiceListing.objects.filter(is_active=True))
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    location = request.GET.get("location", "").strip()
    sort_by = request.GET.get("sort", "relevance")
    if sort_by not in {"relevance", "rating", "reviews", "newest", "oldest"}:
        sort_by = "relevance"
    min_rating = request.GET.get("min_rating", "")
    if min_rating not in {"", "3", "4", "4.5"}:
        min_rating = ""

    if query:
        listings = listings.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(skills__icontains=query)
        )
    if category:
        listings = listings.filter(category=category)
    if location:
        listings = listings.filter(location__icontains=location)
    if min_rating:
        listings = listings.filter(rating_average__gte=float(min_rating))

    if sort_by == "rating":
        listings = listings.order_by(
            F("rating_average").desc(nulls_last=True), "-review_count", "-created_at", "-pk",
        )
    elif sort_by == "reviews":
        listings = listings.order_by(
            "-review_count", F("rating_average").desc(nulls_last=True), "-created_at", "-pk",
        )
    elif sort_by == "newest":
        listings = listings.order_by("-created_at", "-pk")
    elif sort_by == "oldest":
        listings = listings.order_by("created_at", "pk")

    return render(request, "core/listing_list.html", {
        "listings": listings, "query": query, "category": category, "location": location,
        "sort_by": sort_by, "min_rating": min_rating,
        "categories": ServiceListing.CATEGORY_CHOICES,
    })


def listing_detail(request, pk):
    listing = get_object_or_404(_with_rating_summary(ServiceListing.objects.all()), pk=pk)
    already_requested = False
    if request.user.is_authenticated:
        already_requested = ExchangeRequest.objects.filter(
            listing=listing, requester=request.user, status__in=["pending", "accepted", "scheduled"]
        ).exists()
    return render(request, "core/listing_detail.html", {
        "listing": listing, "already_requested": already_requested,
    })


def _with_rating_summary(listings):
    """Attach provider review aggregates in one query for listing cards."""
    return listings.annotate(
        rating_average=Avg("user__ratings_received__stars"),
        review_count=Count("user__ratings_received", distinct=True),
    )


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


def _skill_choices(value):
    """Return canonical, non-empty skill names from existing profile/listing data."""
    choices = {}
    for skill in value.split(","):
        skill = skill.strip()
        if skill:
            choices.setdefault(skill.casefold(), skill)
    return sorted(choices.values(), key=str.casefold)


@login_required
def request_direct_create(request, pk):
    listing = get_object_or_404(ServiceListing, pk=pk, is_active=True)
    if listing.user_id == request.user.id:
        flash.error(request, "You can’t request a direct exchange with yourself.")
        return redirect("listing_detail", pk=listing.pk)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    offered_skills = _skill_choices(profile.skills_offered)
    requested_skills = _skill_choices(listing.skills)
    form = DirectExchangeForm(
        request.POST or None,
        offered_skills=offered_skills,
        requested_skills=requested_skills,
        initial={
            "offered_skill": offered_skills[0] if offered_skills else "",
            "requested_skill": requested_skills[0] if requested_skills else "",
        },
    )

    if request.method == "POST":
        if not offered_skills:
            flash.error(request, "Add a skill you can teach to your profile before requesting a direct exchange.")
        elif not requested_skills:
            flash.error(request, "This listing has no available skills for a direct exchange.")
        elif form.is_valid():
            offered = form.cleaned_data["offered_skill"]
            requested = form.cleaned_data["requested_skill"]
            # Re-read the current profile and listing values; the form choices alone are not trusted.
            current_profile = Profile.objects.get(user=request.user)
            if offered.casefold() not in {s.casefold() for s in _skill_choices(current_profile.skills_offered)}:
                flash.error(request, "You can only offer a skill listed on your profile.")
            elif requested.casefold() not in {s.casefold() for s in _skill_choices(listing.skills)}:
                flash.error(request, "That skill is no longer available in this listing.")
            else:
                active = ExchangeRequest.objects.filter(
                    exchange_type="direct", requester=request.user, provider=listing.user,
                    offered_skill=offered, requested_skill=requested,
                    status__in=["pending", "accepted", "scheduled"],
                ).exists()
                if active:
                    flash.warning(request, "You already have an active direct exchange request for those skills.")
                else:
                    try:
                        with db_transaction.atomic():
                            exchange = ExchangeRequest.objects.create(
                                listing=listing,
                                requester=request.user,
                                provider=listing.user,
                                exchange_type="direct",
                                offered_skill=offered,
                                requested_skill=requested,
                                message=form.cleaned_data["message"],
                            )
                    except IntegrityError:
                        flash.warning(request, "You already have an active direct exchange request for those skills.")
                    else:
                        flash.success(request, "Direct exchange request sent. No credits were used.")
                        return redirect("request_detail", pk=exchange.pk)

    return render(request, "core/direct_exchange_form.html", {
        "form": form, "listing": listing, "offered_skills": offered_skills,
        "requested_skills": requested_skills,
    })


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
    if exchange.exchange_type == "direct":
        flash.error(request, "Use the direct exchange actions shown on its detail page.")
        return redirect("request_detail", pk=pk)

    # Only the provider can accept/reject; either party can cancel; both can mark complete.
    if new_status in ("accepted", "rejected") and request.user != exchange.provider:
        flash.error(request, "Only the provider can respond to this request.")
        return redirect("request_detail", pk=pk)
    if new_status == "cancelled" and request.user not in (exchange.requester, exchange.provider):
        flash.error(request, "Not allowed.")
        return redirect("request_detail", pk=pk)

    if new_status == "completed":
        flash.error(request, "Both participants must confirm completion using the confirmation button.")
        return redirect("request_detail", pk=pk)

    exchange.status = new_status
    exchange.save()

    flash.success(request, f"Exchange marked as {new_status}.")
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
def direct_request_update_status(request, pk, new_status):
    exchange = get_object_or_404(ExchangeRequest, pk=pk, exchange_type="direct")
    if request.user not in (exchange.requester, exchange.provider):
        flash.error(request, "You don’t have access to that exchange.")
        return redirect("dashboard")

    allowed = {"accepted", "rejected", "cancelled"}
    if new_status not in allowed:
        flash.error(request, "That exchange update isn’t available.")
    elif exchange.status == "pending" and new_status in {"accepted", "rejected"}:
        if request.user != exchange.provider:
            flash.error(request, "Only the skill provider can accept or reject this request.")
        else:
            exchange.status = new_status
            exchange.save(update_fields=["status", "updated_at"])
            flash.success(request, f"Direct exchange {new_status}.")
    elif exchange.status in {"pending", "accepted", "scheduled"} and new_status == "cancelled":
        exchange.status = "cancelled"
        exchange.save(update_fields=["status", "updated_at"])
        flash.success(request, "Direct exchange cancelled.")
    else:
        flash.warning(request, "This exchange has already changed status and can’t be updated that way.")
    return redirect("request_detail", pk=pk)


@login_required
@require_POST
def confirm_completion(request, pk):
    """Record only the authenticated participant's confirmation; settle on the second."""
    result = "unauthorized"
    with db_transaction.atomic():
        exchange = get_object_or_404(
            ExchangeRequest.objects.select_for_update(), pk=pk,
        )
        if request.user.pk not in (exchange.requester_id, exchange.provider_id):
            result = "unauthorized"
        elif exchange.status == "completed":
            result = "completed"
        elif exchange.status not in {"accepted", "scheduled"}:
            result = "ineligible"
        else:
            field = "requester_confirmed" if request.user.pk == exchange.requester_id else "provider_confirmed"
            if getattr(exchange, field):
                result = "already_confirmed"
            else:
                setattr(exchange, field, True)
                exchange.save(update_fields=[field, "updated_at"])
                if exchange.requester_confirmed and exchange.provider_confirmed:
                    _complete_exchange(exchange)
                    result = "completed_now"
                else:
                    result = "confirmed"

    if result == "unauthorized":
        flash.error(request, "Only participants in this exchange can confirm completion.")
        return redirect("dashboard")
    if result == "ineligible":
        flash.error(request, "This exchange is not ready for completion confirmation.")
    elif result == "completed":
        flash.info(request, "This exchange is already completed.")
    elif result == "already_confirmed":
        flash.info(request, "You have already confirmed this exchange.")
    elif result == "confirmed":
        flash.success(request, "Your confirmation was saved. Waiting for the other participant.")
    else:
        if exchange.exchange_type == "direct":
            flash.success(request, "Both participants confirmed. The direct exchange is complete; no credits were used.")
        else:
            flash.success(request, "Both participants confirmed. The exchange is complete and credits were settled.")
    return redirect("request_detail", pk=pk)


def _complete_exchange(exchange):
    """Move credits from requester to provider and close out the exchange."""
    if exchange.exchange_type == "direct":
        exchange.status = "completed"
        exchange.save(update_fields=["status", "updated_at"])
        return
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

    if Rating.objects.filter(exchange=exchange, from_user=request.user).exists():
        flash.info(request, "You’ve already reviewed this exchange.")
        return redirect("request_detail", pk=pk)

    if request.method == "POST":
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.exchange = exchange
            rating.from_user = request.user
            rating.to_user = to_user
            try:
                rating.save()
            except IntegrityError:
                flash.info(request, "You’ve already reviewed this exchange.")
                return redirect("request_detail", pk=pk)
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


@require_POST
def user_logout(request):
    logout(request)
    return redirect("login")
