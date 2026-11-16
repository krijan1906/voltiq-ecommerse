from django import forms

from apps.core.forms import StyledModelForm
from apps.reviews.models import Review


class ReviewForm(StyledModelForm):
    rating = forms.TypedChoiceField(
        choices=[(5, "Excellent — 5 stars"), (4, "Very good — 4 stars"), (3, "Average — 3 stars"), (2, "Poor — 2 stars"), (1, "Terrible — 1 star")],
        coerce=int,
        widget=forms.RadioSelect,
        label="Your rating",
    )

    class Meta:
        model = Review
        fields = ["rating", "title", "body"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Summarise your experience"}),
            "body": forms.Textarea(
                attrs={"rows": 5, "placeholder": "What did you like or dislike? How does it perform in daily use?"}
            ),
        }
        labels = {"body": "Your review"}

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 15:
            raise forms.ValidationError("Please write at least 15 characters so other shoppers can benefit.")
        return body

    def clean_title(self):
        return self.cleaned_data["title"].strip()
