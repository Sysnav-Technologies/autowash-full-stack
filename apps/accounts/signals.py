# apps/accounts/signals.py

from django.dispatch import receiver
from allauth.account.signals import user_logged_in
from threading import Thread
from .views import send_login_notification_email


@receiver(user_logged_in)
def send_login_notification_on_allauth_login(sender, request, user, **kwargs):
    """Send login notification email when user logs in via allauth (Google OAuth, etc.)"""
    try:
        # Send login notification email (async to not slow down login)
        email_thread = Thread(
            target=send_login_notification_email,
            args=(request, user)
        )
        email_thread.daemon = True
        email_thread.start()
    except Exception as e:
        print(f"Failed to start login notification email thread for allauth login: {e}")
