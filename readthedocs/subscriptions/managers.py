"""Subscriptions managers."""

import structlog
from django.conf import settings
from django.db import models

from readthedocs.core.history import set_change_reason
from readthedocs.subscriptions.utils import get_or_create_stripe_subscription

log = structlog.get_logger(__name__)


class SubscriptionManager(models.Manager):

    """Model manager for Subscriptions."""

    def get_or_create_default_subscription(self, organization):
        """
        Get or create a trialing subscription for `organization`.

        If the organization doesn't have a subscription attached,
        the following steps are executed.

        - If the organization doesn't have a stripe customer, one is created.
        - A new stripe subscription is created using the default plan.
        - A new subscription object is created in our database
          with the information from the stripe subscription.
        """
        if hasattr(organization, 'subscription'):
            return organization.subscription

        from readthedocs.subscriptions.models import Plan

        plan = Plan.objects.filter(
            stripe_id=settings.RTD_ORG_DEFAULT_STRIPE_SUBSCRIPTION_PRICE
        ).first()
        # This should happen only on development.
        if not plan:
            log.warning(
                'No default plan found, not creating a subscription.',
                organization_slug=organization.slug,
            )
            return None

        stripe_subscription = get_or_create_stripe_subscription(organization)

        return self.create(
            plan=plan,
            organization=organization,
            stripe_id=stripe_subscription.id,
            status=stripe_subscription.status,
            start_date=stripe_subscription.start_date,
            end_date=stripe_subscription.current_period_end,
            trial_end_date=stripe_subscription.trial_end,
        )

    def update_from_stripe(self, *, rtd_subscription, stripe_subscription):
        """
        Update the RTD subscription object with the information of the stripe subscription.

        :param subscription: Subscription object to update.
        :param stripe_subscription: Stripe subscription object from API
        :type stripe_subscription: stripe.Subscription
        """
        # Documentation doesn't say what will be this value once the
        # subscription is ``canceled``. I'm assuming that ``current_period_end``
        # will have the same value than ``ended_at``
        # https://stripe.com/docs/api/subscriptions/object?lang=python#subscription_object-current_period_end
        start_date = stripe_subscription.current_period_start
        end_date = stripe_subscription.current_period_end
        log.bind(stripe_subscription=stripe_subscription.id)

        rtd_subscription.status = stripe_subscription.status

        # This should only happen if an existing user creates a new subscription,
        # after their previous subscription was cancelled.
        if stripe_subscription.id != rtd_subscription.stripe_id:
            log.info(
                'Replacing stripe subscription.',
                old_stripe_subscription=rtd_subscription.stripe_id,
                new_stripe_subscription=stripe_subscription.id,
            )
            rtd_subscription.stripe_id = stripe_subscription.id

        # Update trial end date if it's present
        trial_end_date = stripe_subscription.trial_end
        if trial_end_date:
            rtd_subscription.trial_end_date = trial_end_date

        # Update the plan in case it was changed from the Portal.
        # This mostly just updates the UI now that we're using the Stripe Portal.
        # A miss here just won't update the UI, but this shouldn't happen for most users.
        # NOTE: Previously we were using stripe_subscription.plan,
        # but that attribute is deprecated, and it's null if the subscription has more than
        # one item, we have a couple of subscriptions that have more than
        # one item, so we use the first that is found in our DB.
        for stripe_item in stripe_subscription.items.prefetch_related("price").all():
            plan = self._get_plan(stripe_item.price)
            if plan:
                rtd_subscription.plan = plan
                break
        else:
            log.error("Plan not found, skipping plan update.")

        if stripe_subscription.status == "active" and end_date:
            # Save latest active date (end_date) to notify owners about their subscription
            # is ending and disable this organization after N days of unpaid. We check for
            # ``active`` here because Stripe will continue sending updates for the
            # subscription, with a new ``end_date``, even after the subscription enters
            # an unpaid state.
            rtd_subscription.end_date = end_date

        elif stripe_subscription.status == 'past_due' and start_date:
            # When Stripe marks the subscription as ``past_due``,
            # it means the usage of RTD service for the current period/month was not paid at all.
            # At this point, we need to update our ``end_date`` to the last period the customer paid
            # (which is the start date of the current ``past_due`` period --it could be the end date
            # of the trial or the end date of the last paid period).
            rtd_subscription.end_date = start_date

        klass = self.__class__.__name__
        change_reason = f'origin=stripe-subscription class={klass}'

        # Ensure that the organization is in the correct state.
        # We want to always ensure the organization is never disabled
        # if the subscription is valid.
        organization = rtd_subscription.organization
        if stripe_subscription.status == 'active' and organization.disabled:
            log.warning(
                'Re-enabling organization with valid subscription.',
                organization_slug=organization.slug,
                stripe_subscription=rtd_subscription.id,
            )
            organization.disabled = False
            set_change_reason(organization, change_reason)
            organization.save()

        set_change_reason(rtd_subscription, change_reason)
        rtd_subscription.save()
        return rtd_subscription

    def _get_plan(self, stripe_price):
        from readthedocs.subscriptions.models import Plan

        try:
            plan = (
                Plan.objects
                # Exclude "custom" here, as we historically reused Stripe plan
                # id for custom plans. We don't have a better attribute to
                # filter on here.
                .exclude(slug__contains="custom")
                .exclude(name__icontains="Custom")
                .get(stripe_id=stripe_price.id)
            )
            return plan
        except (Plan.DoesNotExist, Plan.MultipleObjectsReturned):
            log.info(
                "Plan lookup failed.",
                stripe_price=stripe_price.id,
            )
        return None
