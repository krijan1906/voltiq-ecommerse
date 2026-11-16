"""Role-based access decorators."""
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse


def _safe_next(request):
    return request.get_full_path()


def login_required_customer(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please sign in to continue.")
            return redirect(f"{reverse('accounts:login')}?next={_safe_next(request)}")
        if request.user.is_suspended:
            raise PermissionDenied("Account suspended")
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Staff sign-in required.")
            return redirect(f"{reverse('accounts:login')}?next={_safe_next(request)}")
        if not request.user.is_staff or not request.user.is_active:
            raise PermissionDenied("You do not have access to the staff dashboard.")
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Administrator sign-in required.")
            return redirect(f"{reverse('accounts:login')}?next={_safe_next(request)}")
        if not (request.user.is_administrator or request.user.is_superuser):
            raise PermissionDenied("Administrator access only.")
        return view_func(request, *args, **kwargs)

    return wrapper
