from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Profile, ServiceListing, Transaction

DEMO_USERS = [
    {
        "username": "asha",
        "password": "demo1234",
        "bio": "Guitar teacher and part-time gardener.",
        "location": "Kottayam",
        "skills_offered": "guitar lessons, music theory, gardening",
        "skills_needed": "plumbing, home repair",
    },
    {
        "username": "rahul",
        "password": "demo1234",
        "bio": "Plumber by trade, learning Spanish on the side.",
        "location": "Kottayam",
        "skills_offered": "plumbing, home repair, pipe fitting",
        "skills_needed": "spanish tutoring, guitar lessons",
    },
    {
        "username": "meera",
        "password": "demo1234",
        "bio": "Graphic designer who wants to learn cooking.",
        "location": "Kochi",
        "skills_offered": "graphic design, logo design, photoshop",
        "skills_needed": "cooking, baking",
    },
    {
        "username": "vijay",
        "password": "demo1234",
        "bio": "Home cook, needs a website for his side business.",
        "location": "Kochi",
        "skills_offered": "cooking, baking, meal prep",
        "skills_needed": "graphic design, website design",
    },
]

DEMO_LISTINGS = [
    ("asha", "Beginner Guitar Lessons", "One-on-one acoustic guitar basics.", "tutoring", "guitar, music theory, acoustic", 1),
    ("rahul", "Fix Leaky Pipes / Home Plumbing", "Small plumbing repairs around the house.", "repair", "plumbing, pipe fitting, leaks", 2),
    ("meera", "Logo & Poster Design", "Simple logo or event poster in Photoshop.", "design", "graphic design, logo, photoshop", 2),
    ("vijay", "Home-Cooked Meal Prep", "Learn to batch-cook 5 healthy meals.", "wellness", "cooking, baking, meal prep", 2),
]


class Command(BaseCommand):
    help = "Creates demo users, profiles, and listings so the app isn't empty on first run."

    def handle(self, *args, **options):
        for u in DEMO_USERS:
            # get_or_create so a partially-failed previous run (e.g. user
            # created but profile step crashed) can't leave anyone stuck.
            user, user_created = User.objects.get_or_create(username=u["username"])
            if user_created:
                user.set_password(u["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user {u['username']} (password: demo1234)"))

            profile, profile_created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    "bio": u["bio"], "location": u["location"],
                    "skills_offered": u["skills_offered"], "skills_needed": u["skills_needed"],
                    "credits": 5,
                },
            )
            if profile_created:
                Transaction.objects.create(user=user, amount=5, transaction_type="bonus", note="Signup bonus")
                self.stdout.write(self.style.SUCCESS(f"Created profile for {u['username']}"))

        for username, title, desc, cat, skills, hours in DEMO_LISTINGS:
            user = User.objects.get(username=username)
            if ServiceListing.objects.filter(user=user, title=title).exists():
                continue
            ServiceListing.objects.create(
                user=user, title=title, description=desc, category=cat, skills=skills, duration_hours=hours,
                location=user.profile.location,
            )
            self.stdout.write(self.style.SUCCESS(f"Created listing: {title}"))

        self.stdout.write(self.style.SUCCESS(
            "\nDemo data ready. Log in as any of: asha / rahul / meera / vijay (password: demo1234)"
        ))
