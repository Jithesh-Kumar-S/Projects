from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.conf import settings
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ExchangeRequest, Profile, Rating, ServiceListing, Transaction


class LoginOnboardingFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sam", email="sam@example.com", password="Existing-pass-482!"
        )
        self.profile = Profile.objects.create(user=self.user)
        ServiceListing.objects.create(
            user=self.user, title="Python help", description="Intro lessons",
            category="tech", skills="Python, Django", duration_hours=1,
        )

    def test_login_redirects_first_time_users_to_onboarding(self):
        response = self.client.post(reverse("login"), {
            "username": "sam", "password": "Existing-pass-482!",
            "next": reverse("wallet"),
        })
        self.assertRedirects(response, reverse("post_login"), fetch_redirect_response=False)
        response = self.client.get(reverse("post_login"))
        self.assertRedirects(response, reverse("onboarding"), fetch_redirect_response=False)

    def test_completed_user_keeps_protected_page_redirect(self):
        self.profile.onboarding_complete = True
        self.profile.save(update_fields=["onboarding_complete"])
        response = self.client.post(reverse("login"), {
            "username": "sam", "password": "Existing-pass-482!", "next": reverse("wallet"),
        })
        self.assertRedirects(response, reverse("wallet"), fetch_redirect_response=False)

    def test_invalid_and_empty_login_are_rejected(self):
        for credentials in (
            {"username": "sam", "password": "incorrect"},
            {"username": "", "password": ""},
        ):
            response = self.client.post(reverse("login"), credentials)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_registration_still_creates_one_profile_and_starts_onboarding(self):
        response = self.client.post(reverse("signup"), {
            "username": "new-member", "email": "new@example.com",
            "password1": "A-new-member-pass-372!", "password2": "A-new-member-pass-372!",
        })
        self.assertRedirects(response, reverse("post_login"), fetch_redirect_response=False)
        new_user = User.objects.get(username="new-member")
        self.assertEqual(Profile.objects.filter(user=new_user).count(), 1)
        self.assertRedirects(self.client.get(reverse("post_login")), reverse("onboarding"), fetch_redirect_response=False)

    def test_onboarding_saves_existing_profile_fields_and_does_not_repeat(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("onboarding"))
        self.assertContains(response, "Python")
        self.assertContains(response, "What can you teach?")
        response = self.client.post(reverse("onboarding"), {
            "teach": ["Python", "Django"], "learn": ["Django"],
            "display_name": "Sam Example", "location": "Pune", "bio": "I enjoy teaching.",
            "profile_picture": "https://example.com/sam.jpg",
            "experience_level": "intermediate", "availability": "Weekday evenings",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(self.profile.onboarding_complete)
        self.assertEqual(self.profile.skills_offered, "Python, Django")
        self.assertEqual(self.profile.skills_needed, "Django")
        self.assertEqual(self.profile.location, "Pune")
        self.assertEqual(self.profile.profile_picture, "https://example.com/sam.jpg")
        self.assertEqual(self.profile.experience_level, "intermediate")
        self.assertEqual(self.profile.availability, "Weekday evenings")
        self.assertEqual(self.user.first_name, "Sam Example")
        self.assertRedirects(self.client.get(reverse("post_login")), reverse("dashboard"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("onboarding")), reverse("dashboard"), fetch_redirect_response=False)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_changes_password_and_returns_to_login(self):
        response = self.client.post(reverse("password_reset"), {"email": self.user.email})
        self.assertRedirects(response, reverse("password_reset_done"), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        reset_url = next(line for line in mail.outbox[0].body.splitlines() if "/password-reset/" in line)
        path = urlparse(reset_url).path
        response = self.client.get(path, follow=True)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(response.wsgi_request.path, {
            "new_password1": "New-secure-pass-932!",
            "new_password2": "New-secure-pass-932!",
        })
        self.assertRedirects(response, reverse("password_reset_complete"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-secure-pass-932!"))
        self.assertEqual(self.client.get(reverse("password_reset_complete")).status_code, 200)

    def test_profile_edit_remains_available_for_onboarding_data(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("profile_edit"), {
            "display_name": "Sam", "bio": "Updated", "location": "Delhi",
            "profile_picture": "https://example.com/avatar.jpg",
            "experience_level": "advanced", "availability": "Weekends",
            "skills_offered": "Python", "skills_needed": "Django",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.skills_offered, "Python")
        self.assertEqual(self.user.first_name, "Sam")
        self.assertEqual(self.profile.availability, "Weekends")


class PersistentSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="member", password="Existing-pass-482!"
        )
        Profile.objects.create(user=self.user, onboarding_complete=True)

    def test_login_session_persists_across_requests_and_is_not_cached(self):
        response = self.client.post(reverse("login"), {
            "username": "member", "password": "Existing-pass-482!",
        })
        self.assertRedirects(response, reverse("post_login"), fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"], settings.SESSION_COOKIE_AGE)

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        response = self.client.get(reverse("wallet"))
        self.assertEqual(response.status_code, 200)

    def test_private_url_redirects_anonymous_user_to_login_with_return_path(self):
        response = self.client.get(reverse("wallet"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('wallet')}", fetch_redirect_response=False
        )

    def test_logout_flushes_session_and_get_logout_is_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        response = self.client.get(reverse("wallet"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_stale_session_from_another_tab_shows_expiration_message(self):
        self.client.force_login(self.user)
        second_tab = self.client_class()
        second_tab.cookies[settings.SESSION_COOKIE_NAME] = self.client.cookies[settings.SESSION_COOKIE_NAME].value

        self.client.post(reverse("logout"))
        response = second_tab.get(reverse("wallet"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("session_expired=1", response["Location"])
        response = second_tab.get(response["Location"])
        self.assertContains(response, "Your session has expired. Please log in again.")

    def test_expired_session_redirects_and_keeps_public_routes_public(self):
        self.client.force_login(self.user)
        session = self.client.session
        session.set_expiry(-1)
        session.save()
        response = self.client.get(reverse("wallet"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("session_expired=1", response["Location"])
        self.assertEqual(self.client.get(reverse("signup")).status_code, 200)


class DirectExchangeTests(TestCase):
    def setUp(self):
        self.alex = User.objects.create_user(username="alex", password="Existing-pass-482!")
        self.blair = User.objects.create_user(username="blair", password="Existing-pass-482!")
        self.alex_profile = Profile.objects.create(
            user=self.alex, skills_offered="Python, SQL", credits=10, onboarding_complete=True
        )
        self.blair_profile = Profile.objects.create(
            user=self.blair, skills_offered="Photoshop", credits=7, onboarding_complete=True
        )
        self.listing = ServiceListing.objects.create(
            user=self.blair, title="Photoshop tutoring", description="Learn image editing",
            category="design", skills="Photoshop, Graphic Design", duration_hours=2,
        )
        self.create_url = reverse("request_direct_create", args=[self.listing.pk])
        self.payload = {
            "offered_skill": "Python", "requested_skill": "Photoshop",
            "message": "I can teach Python in return.",
        }

    def create_direct(self):
        self.client.force_login(self.alex)
        response = self.client.post(self.create_url, self.payload)
        self.assertEqual(response.status_code, 302)
        return ExchangeRequest.objects.get(exchange_type="direct")

    def status_url(self, exchange, status):
        return reverse("direct_request_update_status", args=[exchange.pk, status])

    def test_valid_direct_request_records_both_skills_and_uses_no_credits(self):
        self.client.force_login(self.alex)
        detail = self.client.get(reverse("listing_detail", args=[self.listing.pk]))
        self.assertContains(detail, "Request with Credits")
        self.assertContains(detail, "Request Direct Exchange")
        response = self.client.get(self.create_url)
        self.assertContains(response, "Direct Skill Exchange")
        self.assertContains(response, "Credits required:")
        response = self.client.post(self.create_url, self.payload)
        self.assertEqual(response.status_code, 302)
        exchange = ExchangeRequest.objects.get(exchange_type="direct")
        self.assertEqual(exchange.requester, self.alex)
        self.assertEqual(exchange.provider, self.blair)
        self.assertEqual(exchange.offered_skill, "Python")
        self.assertEqual(exchange.requested_skill, "Photoshop")
        self.assertEqual(exchange.status, "pending")
        self.alex_profile.refresh_from_db()
        self.blair_profile.refresh_from_db()
        self.assertEqual((self.alex_profile.credits, self.blair_profile.credits), (10, 7))
        self.assertFalse(Transaction.objects.filter(exchange=exchange).exists())

        self.client.force_login(self.blair)
        detail = self.client.get(reverse("request_detail", args=[exchange.pk]))
        self.assertContains(detail, "offers Python to learn Photoshop from")
        self.assertContains(detail, "Accept")
        self.assertContains(detail, "Reject")

    def test_provider_can_accept_and_reject_without_credit_changes(self):
        accepted = self.create_direct()
        self.client.force_login(self.blair)
        response = self.client.post(self.status_url(accepted, "accepted"))
        self.assertEqual(response.status_code, 302)
        accepted.refresh_from_db()
        self.assertEqual(accepted.status, "accepted")
        self.alex_profile.refresh_from_db()
        self.blair_profile.refresh_from_db()
        self.assertEqual((self.alex_profile.credits, self.blair_profile.credits), (10, 7))

        self.client.force_login(self.alex)
        rejected = self.client.post(self.create_url, {
            **self.payload, "offered_skill": "SQL",
        })
        self.assertEqual(rejected.status_code, 302)
        rejected_exchange = ExchangeRequest.objects.exclude(pk=accepted.pk).get(exchange_type="direct")
        self.client.force_login(self.blair)
        self.client.post(self.status_url(rejected_exchange, "rejected"))
        rejected_exchange.refresh_from_db()
        self.assertEqual(rejected_exchange.status, "rejected")
        self.alex_profile.refresh_from_db()
        self.blair_profile.refresh_from_db()
        self.assertEqual((self.alex_profile.credits, self.blair_profile.credits), (10, 7))

    def test_direct_completion_never_settles_credits(self):
        exchange = self.create_direct()
        self.client.force_login(self.blair)
        self.client.post(self.status_url(exchange, "accepted"))
        confirm_url = reverse("confirm_completion", args=[exchange.pk])
        self.client.post(confirm_url)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "accepted")
        self.assertTrue(exchange.provider_confirmed)
        self.assertFalse(exchange.requester_confirmed)
        self.assertEqual(Transaction.objects.filter(exchange=exchange).count(), 0)

        # Repeating the same participant's request is harmless and does not complete it.
        self.client.post(confirm_url)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "accepted")

        self.client.force_login(self.alex)
        self.client.post(confirm_url)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "completed")
        self.assertTrue(exchange.requester_confirmed)
        self.assertTrue(exchange.provider_confirmed)
        self.alex_profile.refresh_from_db()
        self.blair_profile.refresh_from_db()
        self.assertEqual((self.alex_profile.credits, self.blair_profile.credits), (10, 7))
        self.assertFalse(Transaction.objects.filter(exchange=exchange).exists())

    def test_offer_must_belong_to_requester_and_request_cannot_be_self_exchange(self):
        self.client.force_login(self.alex)
        response = self.client.post(self.create_url, {**self.payload, "offered_skill": "Photoshop"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ExchangeRequest.objects.filter(exchange_type="direct").exists())
        response = self.client.post(self.create_url, {**self.payload, "requested_skill": "Not a listing skill"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ExchangeRequest.objects.filter(exchange_type="direct").exists())

        self.client.force_login(self.blair)
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ExchangeRequest.objects.filter(exchange_type="direct").exists())

    def test_duplicate_active_direct_exchange_is_blocked(self):
        exchange = self.create_direct()
        self.client.force_login(self.alex)
        response = self.client.post(self.create_url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ExchangeRequest.objects.filter(exchange_type="direct").count(), 1)
        duplicate_listing = ServiceListing.objects.create(
            user=self.blair, title="Photoshop mentoring", description="A second active listing",
            category="design", skills="Photoshop", duration_hours=1,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExchangeRequest.objects.create(
                    listing=duplicate_listing, requester=self.alex, provider=self.blair,
                    exchange_type="direct", offered_skill=exchange.offered_skill,
                    requested_skill=exchange.requested_skill,
                )

    def test_direct_creation_and_actions_require_authentication(self):
        response = self.client.post(self.create_url, self.payload)
        self.assertEqual(response.status_code, 302)
        exchange = self.create_direct()
        self.client.logout()
        response = self.client.post(self.status_url(exchange, "accepted"))
        self.assertEqual(response.status_code, 302)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "pending")

        intruder = User.objects.create_user(username="intruder", password="Existing-pass-482!")
        self.client.force_login(intruder)
        self.client.post(reverse("confirm_completion", args=[exchange.pk]))
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "pending")
        self.assertFalse(exchange.requester_confirmed)
        self.assertFalse(exchange.provider_confirmed)

    def test_cancelled_direct_exchange_cannot_be_confirmed(self):
        exchange = self.create_direct()
        self.client.force_login(self.blair)
        self.client.post(self.status_url(exchange, "accepted"))
        self.client.post(self.status_url(exchange, "cancelled"))
        self.client.post(reverse("confirm_completion", args=[exchange.pk]))
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "cancelled")
        self.assertFalse(exchange.provider_confirmed)
        self.assertFalse(exchange.requester_confirmed)

    def test_existing_credit_request_and_settlement_are_unchanged(self):
        self.client.force_login(self.alex)
        response = self.client.post(reverse("request_create", args=[self.listing.pk]), {"message": "Please teach me."})
        self.assertEqual(response.status_code, 302)
        exchange = ExchangeRequest.objects.get(exchange_type="credit")
        self.assertEqual(exchange.status, "pending")
        self.client.force_login(self.blair)
        self.client.get(reverse("request_update_status", args=[exchange.pk, "accepted"]))
        self.client.force_login(self.alex)
        confirm_url = reverse("confirm_completion", args=[exchange.pk])
        self.client.post(confirm_url)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "accepted")
        self.assertFalse(Transaction.objects.filter(exchange=exchange).exists())
        self.assertFalse(Rating.objects.filter(exchange=exchange).exists())
        self.assertEqual(self.client.get(reverse("rating_create", args=[exchange.pk])).status_code, 404)
        self.client.force_login(self.blair)
        self.client.post(confirm_url)
        exchange.refresh_from_db()
        self.assertEqual(exchange.status, "completed")
        self.assertTrue(exchange.requester_confirmed)
        self.assertTrue(exchange.provider_confirmed)
        self.alex_profile.refresh_from_db()
        self.blair_profile.refresh_from_db()
        self.assertEqual((self.alex_profile.credits, self.blair_profile.credits), (8, 9))
        self.assertEqual(Transaction.objects.filter(exchange=exchange).count(), 2)


class RatingIntegrationTests(TestCase):
    def setUp(self):
        self.provider = User.objects.create_user(username="teacher", password="Existing-pass-482!")
        self.reviewer = User.objects.create_user(username="learner", password="Existing-pass-482!")
        Profile.objects.create(user=self.provider)
        Profile.objects.create(user=self.reviewer, skills_needed="Python")
        self.listing = ServiceListing.objects.create(
            user=self.provider, title="Python lessons", description="Learn Python",
            category="tech", skills="Python", duration_hours=1,
        )
        self.exchange = ExchangeRequest.objects.create(
            listing=self.listing, requester=self.reviewer, provider=self.provider, status="completed",
        )

    def test_rating_is_validated_and_appears_in_search_and_profile(self):
        self.client.force_login(self.reviewer)
        url = reverse("rating_create", args=[self.exchange.pk])
        response = self.client.post(url, {"stars": "6", "review": "Invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Rating.objects.exists())

        response = self.client.post(url, {"stars": "5", "review": "Great lesson"})
        self.assertRedirects(response, reverse("request_detail", args=[self.exchange.pk]), fetch_redirect_response=False)
        self.assertEqual(Rating.objects.get().stars, 5)
        search = self.client.get(reverse("listing_list"), {"q": "Python"})
        self.assertContains(search, "5.0 / 5")
        self.assertContains(search, "1 review")
        detail = self.client.get(reverse("listing_detail", args=[self.listing.pk]))
        self.assertContains(detail, "5.0 / 5")
        profile = self.client.get(reverse("public_profile", args=[self.provider.username]))
        self.assertContains(profile, "5.0 / 5")
        self.assertContains(profile, "Great lesson")

    def test_unreviewed_listing_shows_no_reviews_and_duplicate_is_rejected(self):
        self.client.force_login(self.reviewer)
        detail = self.client.get(reverse("listing_detail", args=[self.listing.pk]))
        self.assertContains(detail, "No reviews yet")
        url = reverse("rating_create", args=[self.exchange.pk])
        self.client.post(url, {"stars": "4", "review": "Useful"})
        response = self.client.post(url, {"stars": "1", "review": "Changed"})
        self.assertRedirects(response, reverse("request_detail", args=[self.exchange.pk]), fetch_redirect_response=False)
        self.assertEqual(Rating.objects.count(), 1)
        self.assertEqual(Rating.objects.get().stars, 4)

    def test_rating_submission_requires_completed_exchange_participant(self):
        outsider = User.objects.create_user(username="outsider", password="Existing-pass-482!")
        self.client.force_login(outsider)
        response = self.client.post(reverse("rating_create", args=[self.exchange.pk]), {"stars": "5"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Rating.objects.exists())


class ListingSearchSortingTests(TestCase):
    def setUp(self):
        self.python_one = self.make_listing("Python lessons", [5])
        self.python_many = self.make_listing("Python mentoring", [4, 4, 4])
        self.python_unreviewed = self.make_listing("Python basics", [])
        self.other_skill = self.make_listing("Java lessons", [5])

    def make_listing(self, title, stars):
        provider = User.objects.create_user(username=f"provider-{User.objects.count()}")
        listing = ServiceListing.objects.create(
            user=provider, title=title, description="Skill session",
            category="tech", skills=title.split()[0],
        )
        for star in stars:
            reviewer = User.objects.create_user(username=f"reviewer-{User.objects.count()}")
            exchange = ExchangeRequest.objects.create(
                listing=listing, requester=reviewer, provider=provider, status="completed",
            )
            Rating.objects.create(exchange=exchange, from_user=reviewer, to_user=provider, stars=star)
        return listing

    def listing_ids(self, response):
        return list(response.context["listings"].values_list("pk", flat=True))

    def test_search_combines_with_rating_sort_and_minimum_filter(self):
        url = reverse("listing_list")
        highest = self.client.get(url, {"q": "Python", "sort": "rating"})
        self.assertEqual(self.listing_ids(highest), [
            self.python_one.pk, self.python_many.pk, self.python_unreviewed.pk,
        ])
        self.assertNotIn(self.other_skill.pk, self.listing_ids(highest))

        most_reviewed = self.client.get(url, {"q": "Python", "sort": "reviews"})
        self.assertEqual(self.listing_ids(most_reviewed), [
            self.python_many.pk, self.python_one.pk, self.python_unreviewed.pk,
        ])

        filtered = self.client.get(url, {"q": "Python", "sort": "rating", "min_rating": "4.5"})
        self.assertEqual(self.listing_ids(filtered), [self.python_one.pk])
        self.assertContains(filtered, "4.5★ and above")

    def test_unreviewed_listing_does_not_pass_rating_filter_and_invalid_params_fall_back(self):
        url = reverse("listing_list")
        filtered = self.client.get(url, {"q": "Python", "min_rating": "4"})
        self.assertEqual(set(self.listing_ids(filtered)), {self.python_one.pk, self.python_many.pk})
        self.assertNotIn(self.python_unreviewed.pk, self.listing_ids(filtered))

        invalid = self.client.get(url, {"sort": "unknown", "min_rating": "100"})
        self.assertEqual(invalid.context["sort_by"], "relevance")
        self.assertEqual(invalid.context["min_rating"], "")
        self.assertContains(invalid, "Clear search and filters")
