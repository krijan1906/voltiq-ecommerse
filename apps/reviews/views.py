from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from apps.reviews.forms import ReviewForm
from apps.reviews.models import Review


def _has_purchased(user, product):
    return (
        OrderItem.objects.filter(
            order__user=user,
            product=product,
        )
        .exclude(order__status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED])
        .exists()
    )


@login_required
def add_review(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.info(request, "You have already reviewed this product. You can edit your review instead.")
        return redirect("products:detail", slug=product.slug)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.is_verified_purchase = _has_purchased(request.user, product)
        review.is_approved = True
        review.save()
        messages.success(request, "Thanks! Your review has been published.")
        return redirect(f"{product.get_absolute_url()}#reviews")
    return render(
        request,
        "reviews/form.html",
        {"form": form, "product": product, "title": "Write a review", "verified": _has_purchased(request.user, product)},
    )


@login_required
def edit_review(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your review has been updated.")
        return redirect(f"{review.product.get_absolute_url()}#reviews")
    return render(
        request,
        "reviews/form.html",
        {
            "form": form,
            "product": review.product,
            "review": review,
            "title": "Edit your review",
            "verified": review.is_verified_purchase,
        },
    )


@login_required
@require_POST
def delete_review(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    product = review.product
    review.delete()
    messages.success(request, "Your review has been deleted.")
    return redirect(f"{product.get_absolute_url()}#reviews")
