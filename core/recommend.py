"""
ML Recommendation Engine
------------------------
This is the "smart matching" piece from the project brief (FR-05, FR-07):
given a user, suggest service listings that best match what they say they
NEED, by comparing text similarity against what other users OFFER.

Technique: content-based filtering using TF-IDF vectors + cosine similarity
(scikit-learn). This is the same family of technique used by real
recommender systems, just applied to short skill/keyword text instead of
big product catalogs.

How it works, in plain terms:
1. Turn every listing's text (title + description + skills) into a vector
   of word-importance scores (TF-IDF).
2. Turn the current user's "skills_needed" text into a vector the same way.
3. Measure the angle (cosine similarity) between the user's vector and
   every listing's vector. 1.0 = extremely similar wording/topic, 0 = no
   overlap at all.
4. Sort listings by that similarity score, highest first.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.db.models import Avg, Count

from .models import Rating, ServiceListing


def get_recommendations(user, top_n=5):
    """
    Return up to `top_n` ServiceListing objects (excluding the user's own
    listings) ranked by how well they match the user's stated needs.
    """
    profile = getattr(user, "profile", None)
    needed_text = (profile.skills_needed if profile else "").strip()

    listings = list(ServiceListing.objects.filter(is_active=True).exclude(user=user).annotate(
        rating_average=Avg("user__ratings_received__stars"),
        review_count=Count("user__ratings_received", distinct=True),
    ))
    if not listings:
        return []

    community_average = Rating.objects.aggregate(average=Avg("stars"))["average"] or 3.0

    def rating_signal(listing):
        # Bayesian shrinkage gives low-count ratings less influence.
        count = listing.review_count
        average = listing.rating_average
        if not count or average is None:
            return 0.0
        adjusted = (count * average + 20 * community_average) / (count + 20)
        return (adjusted - community_average) / 2

    def rank_with_rating(pairs):
        # Preserve text matching as the main signal; reputation is a small tie-breaker.
        return sorted(pairs, key=lambda pair: pair[1] + 0.08 * rating_signal(pair[0]), reverse=True)

    # If the user hasn't described what they need yet, fall back to
    # "most recent listings" rather than showing nothing.
    if not needed_text:
        return [listing for listing, _ in rank_with_rating((listing, 0) for listing in listings)][:top_n]

    # Build the text corpus: [user's need, listing 1 text, listing 2 text, ...]
    listing_texts = [f"{l.title} {l.description} {l.skills}" for l in listings]
    corpus = [needed_text] + listing_texts

    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)

    # Row 0 is the user's need vector; the rest are listings.
    user_vector = tfidf_matrix[0:1]
    listing_vectors = tfidf_matrix[1:]

    similarities = cosine_similarity(user_vector, listing_vectors).flatten()

    # Pair each listing with its score and sort, highest similarity first.
    scored = rank_with_rating(zip(listings, similarities))

    # Only recommend things with at least a little real overlap (score > 0)
    ranked = [listing for listing, score in scored if score > 0]

    # If nothing scored above 0 (totally different vocabulary), still show
    # something recent rather than an empty page.
    if not ranked:
        return [listing for listing, _ in rank_with_rating((listing, 0) for listing in listings)][:top_n]

    return ranked[:top_n]


def find_complementary_users(user, top_n=5):
    """
    A second, simpler matching mode (FR-07 'similarity matching'):
    find OTHER USERS (not listings) whose 'skills_offered' text best
    matches this user's 'skills_needed' text, using the same TF-IDF +
    cosine similarity approach. Useful for a "people you might barter
    with" view, separate from browsing individual listings.
    """
    from django.contrib.auth.models import User

    profile = getattr(user, "profile", None)
    needed_text = (profile.skills_needed if profile else "").strip()
    if not needed_text:
        return []

    other_profiles = list(
        user.profile.__class__.objects.exclude(user=user).exclude(skills_offered="")
    )
    if not other_profiles:
        return []

    corpus = [needed_text] + [p.skills_offered for p in other_profiles]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)

    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    scored = sorted(zip(other_profiles, similarities), key=lambda pair: pair[1], reverse=True)
    ranked = [p.user for p, score in scored if score > 0]
    return ranked[:top_n]
