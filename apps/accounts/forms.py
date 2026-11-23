import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.accounts.models import Address, CustomerProfile, User
from apps.core.forms import StyledForm, StyledFormMixin, StyledModelForm


class RegisterForm(StyledForm):
    first_name = forms.CharField(max_length=80, label="First name")
    last_name = forms.CharField(max_length=80, label="Last name", required=False)
    email = forms.EmailField(label="Email address")
    phone = forms.CharField(max_length=20, required=False, label="Phone (optional)")
    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), min_length=8
    )
    password2 = forms.CharField(
        label="Confirm password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    newsletter = forms.BooleanField(required=False, label="Email me exclusive deals and launches")
    terms = forms.BooleanField(
        required=True, label="I agree to the Terms of Service and Privacy Policy"
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        validate_email(email)
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists. Try signing in.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not re.match(r"^\+?[0-9\s\-()]{7,20}$", phone):
            raise ValidationError("Enter a valid phone number.")
        return phone

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            user = User(
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(p1, user=user)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = User(
            email=self.cleaned_data["email"],
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=(self.cleaned_data.get("last_name") or "").strip(),
            phone=self.cleaned_data.get("phone", ""),
            newsletter_opt_in=self.cleaned_data.get("newsletter", False),
        )
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            CustomerProfile.objects.filter(user=user).update(
                marketing_opt_in=self.cleaned_data.get("newsletter", False)
            )
        return user


class OTPForm(StyledForm):
    code = forms.CharField(
        label="Verification code",
        max_length=4,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "pattern": "[0-9]{4}",
                "maxlength": "4",
                "autocomplete": "one-time-code",
                "autofocus": True,
                "placeholder": "----",
                "class": "otp-input",
                "aria-label": "Four digit verification code",
            }
        ),
    )

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not code.isdigit() or len(code) != 4:
            raise ValidationError("Enter the four-digit code from the email.")
        return code


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True})
    )
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )
    remember_me = forms.BooleanField(required=False, label="Keep me signed in", initial=True)

    error_messages = {
        "invalid_login": "Email or password is incorrect. Please try again.",
        "inactive": "This account is inactive. Please contact support.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_suspended:
            raise ValidationError(
                "This account is suspended. Contact support@voltiq.com.np for assistance.",
                code="suspended",
            )


class ProfileForm(StyledModelForm):
    remove_avatar = forms.BooleanField(required=False, label="Remove current photo")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "avatar", "newsletter_opt_in"]
        labels = {"newsletter_opt_in": "Receive deals and product updates"}

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("remove_avatar") and user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
        if commit:
            user.save()
        return user


class AddressForm(StyledModelForm):
    class Meta:
        model = Address
        fields = [
            "label",
            "full_name",
            "phone",
            "alternate_phone",
            "street_address",
            "landmark",
            "city",
            "district",
            "province",
            "postal_code",
            "country",
            "address_type",
            "is_default",
        ]
        widgets = {
            "street_address": forms.TextInput(attrs={"placeholder": "House no., street, apartment"}),
            "district": forms.TextInput(attrs={"placeholder": "e.g. Kathmandu"}),
            "city": forms.TextInput(attrs={"placeholder": "e.g. Kathmandu"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        address = super().save(commit=False)
        address.user = self.user
        if commit:
            address.save()
        return address


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass


class AccountSettingsForm(StyledModelForm):
    class Meta:
        model = CustomerProfile
        fields = ["date_of_birth", "preferred_payment", "marketing_opt_in"]
