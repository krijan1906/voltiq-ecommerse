from django import forms

from apps.core.forms import StyledForm, StyledFormMixin
from apps.orders.models import ShippingMethod


class CheckoutContactForm(StyledForm):
    full_name = forms.CharField(max_length=120, label="Full name")
    email = forms.EmailField(label="Email address")
    phone = forms.CharField(max_length=20, label="Phone number")

    def clean_phone(self):
        import re

        phone = self.cleaned_data["phone"].strip()
        if not re.match(r"^\+?[0-9\s\-()]{7,20}$", phone):
            raise forms.ValidationError("Enter a valid phone number.")
        return phone


class ShippingMethodForm(StyledForm):
    shipping_method = forms.ModelChoiceField(
        queryset=ShippingMethod.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        label="Delivery speed",
    )


class PaymentMethodForm(StyledForm):
    payment_method = forms.ChoiceField(widget=forms.RadioSelect, label="Payment method")
    customer_notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Delivery instructions (optional)"}),
        label="Order notes",
    )

    def __init__(self, *args, methods=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].choices = [(m.code, m.display_name) for m in methods or []]


class CouponCodeForm(StyledForm):
    code = forms.CharField(max_length=40, label="Coupon code", widget=forms.TextInput(attrs={"placeholder": "Enter code"}))


class OrderLookupForm(StyledForm):
    order_number = forms.CharField(max_length=30)
    email = forms.EmailField()
