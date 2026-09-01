"""Stripe subscriptions.

Checkout + billing portal + webhook. Stripe holds the card details; this
service never sees them.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import stripe

from . import store

log = logging.getLogger(__name__)

PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
PRICE_ANNUAL = os.environ.get("STRIPE_PRICE_ANNUAL", "")
TRIAL_DAYS = int(os.environ.get("GAFFER_TRIAL_DAYS", "7"))


def configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _init() -> None:
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set — billing is disabled.")
    stripe.api_key = key


def checkout_url(user: store.User, cadence: str, base_url: str) -> str:
    _init()
    price = PRICE_ANNUAL if cadence == "annual" else PRICE_MONTHLY
    if not price:
        raise RuntimeError(
            f"No Stripe price id for '{cadence}'. Set STRIPE_PRICE_MONTHLY "
            f"and STRIPE_PRICE_ANNUAL."
        )
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        customer=user.stripe_customer or None,
        customer_email=None if user.stripe_customer else user.email,
        client_reference_id=user.id,
        subscription_data={"trial_period_days": TRIAL_DAYS} if TRIAL_DAYS else {},
        allow_promotion_codes=True,
        success_url=f"{base_url}/app?checkout=success",
        cancel_url=f"{base_url}/pricing?checkout=cancelled",
    )
    return session.url


def portal_url(user: store.User, base_url: str) -> str:
    """Stripe's own portal handles cancellation, card changes and invoices, so
    none of that has to be built or supported here."""
    _init()
    if not user.stripe_customer:
        raise RuntimeError("No Stripe customer for this account yet.")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer, return_url=f"{base_url}/app",
    )
    return session.url


def handle_webhook(payload: bytes, signature: str) -> str:
    _init()
    wh_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not wh_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not set.")
    # Verifying the signature is what stops anyone POSTing themselves a
    # subscription. Never parse the body before this succeeds.
    event = stripe.Webhook.construct_event(payload, signature, wh_secret)
    kind = event["type"]
    obj = event["data"]["object"]

    if kind == "checkout.session.completed":
        store.set_subscription(
            customer=obj.get("customer"),
            subscription=obj.get("subscription"),
            plan="pro", status="active", period_end=None,
            email=(obj.get("customer_details") or {}).get("email"),
        )
    elif kind in ("customer.subscription.updated", "customer.subscription.created"):
        status = obj.get("status", "active")
        end = obj.get("current_period_end")
        store.set_subscription(
            customer=obj.get("customer"),
            subscription=obj.get("id"),
            plan="pro" if status in ("active", "trialing") else "free",
            status=status,
            period_end=(datetime.fromtimestamp(end, tz=timezone.utc).isoformat()
                        if end else None),
        )
    elif kind == "customer.subscription.deleted":
        store.set_subscription(
            customer=obj.get("customer"), subscription=obj.get("id"),
            plan="free", status="canceled", period_end=None,
        )
    else:
        log.info("ignoring stripe event %s", kind)
    return kind
