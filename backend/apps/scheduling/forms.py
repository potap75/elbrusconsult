from django import forms

from .models import BookingInquiry


class BookingInquiryForm(forms.ModelForm):
    class Meta:
        model = BookingInquiry
        fields = [
            "name",
            "email",
            "company",
            "phone",
            "service",
            "preferred_date",
            "timezone_label",
            "notes",
        ]
