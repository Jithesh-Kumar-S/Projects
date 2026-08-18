from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ServiceListing, Profile, ExchangeRequest, Rating, Message


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["bio", "location", "skills_offered", "skills_needed"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3}),
            "skills_offered": forms.TextInput(attrs={"placeholder": "guitar, cooking, python"}),
            "skills_needed": forms.TextInput(attrs={"placeholder": "plumbing, spanish, resume review"}),
        }


class ServiceListingForm(forms.ModelForm):
    class Meta:
        model = ServiceListing
        fields = ["title", "description", "category", "skills", "duration_hours", "location"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class ExchangeRequestForm(forms.ModelForm):
    class Meta:
        model = ExchangeRequest
        fields = ["message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3, "placeholder": "Say hi, propose a time..."})}


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ["stars", "review"]
        widgets = {
            "stars": forms.Select(choices=[(i, f"{i} star{'s' if i != 1 else ''}") for i in range(1, 6)]),
            "review": forms.Textarea(attrs={"rows": 2}),
        }


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["text"]
        widgets = {"text": forms.TextInput(attrs={"placeholder": "Type a message..."})}
