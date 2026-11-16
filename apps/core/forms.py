from django import forms

from apps.core.models import ContactMessage


class StyledFormMixin:
    """Applies consistent design-system classes to all widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "checkbox"
            elif isinstance(widget, forms.Select):
                css = "select"
            elif isinstance(widget, forms.Textarea):
                css = "textarea"
            elif isinstance(widget, forms.FileInput):
                css = "file-input"
            elif isinstance(widget, forms.RadioSelect):
                continue
            else:
                css = "input"
            existing = widget.attrs.get("class", "")
            if css not in existing.split():
                widget.attrs["class"] = f"{existing} {css}".strip()
            if field.required and not isinstance(widget, (forms.CheckboxInput, forms.FileInput)):
                widget.attrs.setdefault("required", "required")


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass


class StyledForm(StyledFormMixin, forms.Form):
    pass


class NewsletterForm(StyledForm):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
    )
    name = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ContactForm(StyledModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "subject", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5, "maxlength": 3000})}

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please provide a little more detail (at least 10 characters).")
        return message
