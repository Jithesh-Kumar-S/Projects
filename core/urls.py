from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.ProfileAwareLoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("post-login/", views.post_login, name="post_login"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("password-reset/", auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html", email_template_name="registration/password_reset_email.html", subject_template_name="registration/password_reset_subject.txt", success_url="/password-reset/sent/"), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html", success_url="/password-reset/complete/"), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("u/<str:username>/", views.public_profile, name="public_profile"),

    path("listings/", views.listing_list, name="listing_list"),
    path("listings/new/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("listings/<int:pk>/delete/", views.listing_delete, name="listing_delete"),
    path("listings/<int:pk>/request/", views.request_create, name="request_create"),
    path("listings/<int:pk>/direct-request/", views.request_direct_create, name="request_direct_create"),

    path("exchanges/", views.request_list, name="request_list"),
    path("exchanges/<int:pk>/", views.request_detail, name="request_detail"),
    path("exchanges/<int:pk>/status/<str:new_status>/", views.request_update_status, name="request_update_status"),
    path("exchanges/<int:pk>/direct-status/<str:new_status>/", views.direct_request_update_status, name="direct_request_update_status"),
    path("exchanges/<int:pk>/confirm-completion/", views.confirm_completion, name="confirm_completion"),
    path("exchanges/<int:pk>/rate/", views.rating_create, name="rating_create"),

    path("wallet/", views.wallet, name="wallet"),
    path("analytics/", views.admin_analytics, name="admin_analytics"),
]
