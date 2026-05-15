"""Contact form with honeypot anti-spam field."""
from __future__ import annotations

from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # Hidden honeypot - real humans won't fill this; bots usually will.
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="")

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "company", "subject", "message"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "name",
                    "placeholder": "Your name",
                    "required": True,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "email",
                    "placeholder": "you@example.com",
                    "required": True,
                }
            ),
            "company": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "autocomplete": "organization",
                    "placeholder": "Company (optional)",
                }
            ),
            "subject": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "How can we help?"}
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 6,
                    "placeholder": "Tell us a bit about what you are working on...",
                    "required": True,
                }
            ),
        }

    def clean_website(self) -> str:
        value = self.cleaned_data.get("website", "")
        if value:
            # Silently fail validation for bots.
            raise forms.ValidationError("Spam detected.")
        return value
