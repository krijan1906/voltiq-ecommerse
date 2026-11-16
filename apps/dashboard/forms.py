from django import forms
from django.core.exceptions import ValidationError

from apps.categories.models import Brand, Category
from apps.core.forms import StyledForm, StyledModelForm
from apps.core.models import SiteSetting
from apps.inventory.models import StockHistory
from apps.orders.models import Coupon, Order, ShippingMethod
from apps.products.models import Product, SpecificationField


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            return files.getlist(name)
        return files.get(name)


class MultipleImageField(forms.FileField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data if item]
        if data:
            return [single_clean(data, initial)]
        return []


class ProductForm(StyledModelForm):
    images = MultipleImageField(
        required=False,
        label="Add product images",
        help_text="Upload one or more JPG/PNG/WEBP images (max 5 MB each).",
        widget=MultipleImageInput(attrs={"accept": "image/*", "multiple": True}),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "brand",
            "category",
            "short_description",
            "description",
            "highlights",
            "price",
            "discount_price",
            "cost_price",
            "stock_quantity",
            "low_stock_threshold",
            "warranty_info",
            "condition",
            "color",
            "processor",
            "ram",
            "storage",
            "gpu",
            "display_size",
            "operating_system",
            "is_active",
            "is_featured",
            "free_shipping",
            "allow_backorder",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "highlights": forms.Textarea(attrs={"rows": 4}),
            "short_description": forms.TextInput(attrs={"maxlength": 300}),
        }

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip().upper()
        qs = Product.objects.filter(sku__iexact=sku)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A product with this SKU already exists.")
        return sku

    def clean(self):
        cleaned = super().clean()
        price, discount = cleaned.get("price"), cleaned.get("discount_price")
        if discount and price and discount >= price:
            self.add_error("discount_price", "Sale price must be lower than the regular price.")
        if cleaned.get("stock_quantity", 0) > 100000:
            self.add_error("stock_quantity", "Stock quantity looks too high.")
        return cleaned


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ["name", "parent", "description", "image", "icon", "is_active", "is_featured", "sort_order"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if parent and self.instance.pk and parent.pk == self.instance.pk:
            raise ValidationError("A category cannot be its own parent.")
        if parent and parent.parent_id:
            raise ValidationError("Only two levels of categories are supported. Choose a top-level parent.")
        return parent


class BrandForm(StyledModelForm):
    class Meta:
        model = Brand
        fields = ["name", "logo", "description", "website", "is_active", "is_featured"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class SpecificationFieldForm(StyledModelForm):
    class Meta:
        model = SpecificationField
        fields = ["category", "label", "key", "unit", "input_type", "options", "is_filterable", "sort_order"]
        widgets = {"options": forms.TextInput(attrs={"placeholder": "e.g. 8GB, 16GB, 32GB"})}


class CouponForm(StyledModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "description",
            "discount_type",
            "value",
            "minimum_order_amount",
            "maximum_discount",
            "valid_from",
            "valid_to",
            "usage_limit",
            "per_user_limit",
            "is_active",
        ]
        widgets = {
            "valid_from": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "valid_to": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("valid_from", "valid_to"):
            self.fields[name].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        qs = Coupon.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("This coupon code already exists.")
        return code

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("discount_type") == Coupon.DiscountType.PERCENTAGE:
            value = cleaned.get("value") or 0
            if value > 100:
                self.add_error("value", "A percentage discount cannot exceed 100%.")
        valid_from, valid_to = cleaned.get("valid_from"), cleaned.get("valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            self.add_error("valid_to", "End date must be after the start date.")
        return cleaned


class ShippingMethodForm(StyledModelForm):
    class Meta:
        model = ShippingMethod
        fields = ["name", "code", "description", "charge", "free_over", "min_days", "max_days", "is_active", "sort_order"]


class StockAdjustForm(StyledForm):
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    new_quantity = forms.IntegerField(min_value=0, max_value=100000, label="New stock quantity")
    reason = forms.ChoiceField(choices=StockHistory.Reason.choices)
    reference = forms.CharField(max_length=120, required=False, label="Reference / note")


class OrderStatusForm(StyledForm):
    status = forms.ChoiceField(label="Update status", choices=Order.Status.choices)
    note = forms.CharField(max_length=300, required=False)
    tracking_number = forms.CharField(max_length=100, required=False)
    courier = forms.CharField(max_length=80, required=False)


class SiteSettingForm(StyledModelForm):
    class Meta:
        model = SiteSetting
        fields = [
            "store_name",
            "tagline",
            "announcement",
            "support_phone",
            "support_email",
            "address",
            "facebook_url",
            "instagram_url",
            "youtube_url",
            "tiktok_url",
        ]


class ProductImageUploadForm(StyledForm):
    images = MultipleImageField(
        required=True,
        widget=MultipleImageInput(attrs={"accept": "image/*", "multiple": True}),
        label="Upload images",
    )
