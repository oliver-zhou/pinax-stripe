from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

from ..hooks import DefaultHookSet


class TestHookSet(DefaultHookSet):

    def adjust_subscription_quantity(self, customer, plan, quantity):
        """
        Given a customer, plan, and quantity, when calling Customer.subscribe
        you have the opportunity to override the quantity that was specified.

        Previously this was handled in the setting `PAYMENTS_PLAN_QUANTITY_CALLBACK`
        and was only passed a customer object.
        """
        return quantity or 4

    def trial_period(self, user, plan):
        """
        Given a user and plan, return an end date for a trial period, or None
        for no trial period.

        Was previously in the setting `TRIAL_PERIOD_FOR_USER_CALLBACK`
        """
        if plan is not None:
            return timezone.now() + timedelta(days=3)

    def send_receipt(self, charge):
        if not charge.receipt_sent:
            from django.contrib.sites.models import Site

            site = Site.objects.get_current()
            protocol = getattr(settings, "DEFAULT_HTTP_PROTOCOL", "http")
            ctx = {
                "charge": charge,
                "site": site,
                "protocol": protocol,
            }
            subject = render_to_string("pinax/stripe/email/subject.txt", ctx)
            subject = subject.strip()
            message = render_to_string("pinax/stripe/email/body.txt", ctx)
            num_sent = EmailMessage(
                subject,
                message,
                to=[charge.customer.user.email],
                from_email=settings.PINAX_STRIPE_INVOICE_FROM_EMAIL
            ).send()
            charge.receipt_sent = num_sent > 0
            charge.save()
