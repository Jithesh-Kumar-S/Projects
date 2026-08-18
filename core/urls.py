from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('logout/', views.user_logout, name='logout'),
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("u/<str:username>/", views.public_profile, name="public_profile"),

    path("listings/", views.listing_list, name="listing_list"),
    path("listings/new/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("listings/<int:pk>/delete/", views.listing_delete, name="listing_delete"),
    path("listings/<int:pk>/request/", views.request_create, name="request_create"),

    path("exchanges/", views.request_list, name="request_list"),
    path("exchanges/<int:pk>/", views.request_detail, name="request_detail"),
    path("exchanges/<int:pk>/status/<str:new_status>/", views.request_update_status, name="request_update_status"),
    path("exchanges/<int:pk>/rate/", views.rating_create, name="rating_create"),

    path("wallet/", views.wallet, name="wallet"),
    path("analytics/", views.admin_analytics, name="admin_analytics"),
]
