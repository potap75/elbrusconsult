from django import forms


class SubscribeForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-input",
                "autocomplete": "email",
                "placeholder": "you@example.com",
                "required": True,
            }
        )
    )
    # honeypot
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="")

    def clean_website(self) -> str:
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Spam detected.")
        return value
