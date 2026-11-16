from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.accounts.models import CustomerProfile, User


@receiver(post_save, sender=User)
def ensure_customer_profile(sender, instance, created, **kwargs):
    if created:
        CustomerProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def record_login_ip(sender, request, user, **kwargs):
    ip = request.META.get("REMOTE_ADDR")
    if ip:
        User.objects.filter(pk=user.pk).update(last_login_ip=ip)


@receiver(post_delete, sender=User)
def delete_user_avatar_file(sender, instance, **kwargs):
    if instance.avatar:
        try:
            instance.avatar.delete(save=False)
        except Exception:
            pass
