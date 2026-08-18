from django.conf import settings
from django.db import models
from django.urls import reverse

SIGNUP_BONUS_CREDITS = 5  # new users start with a few credits so they can try the platform


class Profile(models.Model):
    """Extra info attached to every Django User: skills, location, credit balance."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)

    # Comma-separated keyword strings — simple on purpose. The ML layer
    # (core/recommend.py) turns this text into vectors for matching.
    skills_offered = models.TextField(
        blank=True, help_text="Comma-separated, e.g. guitar, cooking, python tutoring"
    )
    skills_needed = models.TextField(
        blank=True, help_text="Comma-separated, e.g. plumbing, spanish, resume review"
    )

    credits = models.IntegerField(default=SIGNUP_BONUS_CREDITS)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def average_rating(self):
        ratings = Rating.objects.filter(to_user=self.user)
        if not ratings.exists():
            return None
        return round(sum(r.stars for r in ratings) / ratings.count(), 1)


class ServiceListing(models.Model):
    """A skill/service a user is offering to the community."""

    CATEGORY_CHOICES = [
        ("tutoring", "Tutoring / Lessons"),
        ("repair", "Home Repair"),
        ("design", "Design / Creative"),
        ("tech", "Tech / Programming"),
        ("wellness", "Wellness / Fitness"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=150)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    skills = models.CharField(
        max_length=255, help_text="Comma-separated keywords used for matching, e.g. guitar, music theory"
    )
    duration_hours = models.PositiveIntegerField(default=1, help_text="Typical length of one session, in hours")
    location = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.user.username})"

    def get_absolute_url(self):
        return reverse("listing_detail", args=[self.pk])


class ExchangeRequest(models.Model):
    """One barter request moving through: pending -> accepted -> scheduled -> completed."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("disputed", "Disputed"),
    ]

    listing = models.ForeignKey(ServiceListing, on_delete=models.CASCADE, related_name="requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_requests"
    )  # the person who WANTS the service
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_requests"
    )  # the person offering the listing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    message = models.TextField(blank=True, help_text="Note from the requester")
    scheduled_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requester.username} -> {self.provider.username}: {self.listing.title} [{self.status}]"


class Transaction(models.Model):
    """Ledger entry for the time-credit wallet. 1 hour of a completed exchange = 1 credit."""

    TYPE_CHOICES = [("earn", "Earned"), ("spend", "Spent"), ("bonus", "Signup Bonus")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    amount = models.IntegerField(help_text="Positive for earn/bonus, negative for spend")
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    exchange = models.ForeignKey(ExchangeRequest, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.amount:+d} credits"


class Rating(models.Model):
    """Feedback left after a completed exchange. Builds the trust layer."""

    exchange = models.ForeignKey(ExchangeRequest, on_delete=models.CASCADE, related_name="ratings")
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_given")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_received")
    stars = models.PositiveSmallIntegerField()  # 1-5
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("exchange", "from_user")  # one rating per person per exchange

    def __str__(self):
        return f"{self.stars}* {self.from_user.username} -> {self.to_user.username}"


class Message(models.Model):
    """Simple in-platform chat tied to a specific exchange request."""

    exchange = models.ForeignKey(ExchangeRequest, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender.username}: {self.text[:30]}"
