import uuid
from datetime import datetime, timedelta

import requests
from flask import Blueprint, request, jsonify, g

import models
from geolocation import currency_for_country
from currency import convert_currency

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")

FLUTTERWAVE_SECRET_KEY = "FLWSECK-f6f678b69327963dcdfb5015deff9492-1a090c32ca1vt-X"
FLUTTERWAVE_PUBLIC_KEY = "FLWPUBK-78c8e65ab6798f6027915f1982550d71-X"
FLUTTERWAVE_VERIFY_URL = "https://api.flutterwave.com/v3/transactions/verify_by_reference"

# Currencies Flutterwave currently accepts for card transactions.
# Source: Flutterwave help center, "What are the currencies accepted on Flutterwave".
FLUTTERWAVE_SUPPORTED_CURRENCIES = {
    "GBP", "CAD", "XAF", "COP", "EGP", "EUR", "GHS", "KES", "INR",
    "NGN", "RWF", "SLL", "ZAR", "TZS", "UGX", "USD", "XOF", "ZMW",
}

PLAN_AMOUNTS_NGN = {
    "monthly": 2000,
    "three_months": 5500,
    "yearly": 20000,
}
PLAN_DAYS = {
    "monthly": 30,
    "three_months": 90,
    "yearly": 365,
}


def _determine_charge_currency(user):
    local_currency = currency_for_country(user.country) if user.country else "NGN"
    if local_currency in FLUTTERWAVE_SUPPORTED_CURRENCIES:
        return local_currency
    return "USD"


def _determine_charge_amount(charge_currency):
    base_amount_ngn = PLAN_AMOUNTS_NGN
    return base_amount_ngn


@payments_bp.post("/premium/initiate")
def initiate_premium():
    from auth import require_auth  # local import to avoid circulars, matches project style

    @require_auth
    def _inner():
        data = request.get_json(force=True) or {}
        plan = data.get("plan")
        if plan not in PLAN_AMOUNTS_NGN:
            return jsonify({"detail": "Invalid plan"}), 422

        user = g.current_user
        db = g.db
        tx_ref = f"CREET-{user.id}-{uuid.uuid4().hex[:10]}"

        amount_ngn = PLAN_AMOUNTS_NGN[plan]
        charge_currency = _determine_charge_currency(user)

        if charge_currency == "NGN":
            amount = amount_ngn
        else:
            converted = convert_currency(amount_ngn, "NGN", charge_currency)
            if converted is None:
                # Conversion service unreachable — fall back to NGN, which is
                # always guaranteed to work, rather than fail the checkout.
                charge_currency = "NGN"
                amount = amount_ngn
            else:
                amount = converted

        payment = models.PremiumPayment(
            user_id=user.id,
            plan=plan,
            tx_ref=tx_ref,
            amount=amount,
            currency=charge_currency,
            status="pending",
        )
        db.add(payment)
        db.commit()

        return jsonify({
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": charge_currency,
            "public_key": FLUTTERWAVE_PUBLIC_KEY,
            "customer": {"email": user.email, "name": user.full_name},
        })

    return _inner()


@payments_bp.post("/premium/verify")
def verify_premium():
    from auth import require_auth

    @require_auth
    def _inner():
        data = request.get_json(force=True) or {}
        tx_ref = data.get("tx_ref")
        if not tx_ref:
            return jsonify({"detail": "Missing tx_ref"}), 422

        db = g.db
        user = g.current_user
        payment = (
            db.query(models.PremiumPayment)
            .filter(models.PremiumPayment.tx_ref == tx_ref, models.PremiumPayment.user_id == user.id)
            .first()
        )
        if not payment:
            return jsonify({"detail": "Payment record not found"}), 404

        if payment.status == "successful":
            return jsonify({
                "is_premium": bool(user.is_premium),
                "premium_expires": user.premium_expires.isoformat() if user.premium_expires else None,
            })

        resp = requests.get(
            FLUTTERWAVE_VERIFY_URL,
            params={"tx_ref": tx_ref},
            headers={"Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}"},
            timeout=15,
        )
        result = resp.json()
        tx_data = result.get("data") or {}

        if result.get("status") != "success" or tx_data.get("status") != "successful":
            payment.status = "failed"
            db.commit()
            return jsonify({"detail": "Payment could not be verified"}), 400

        if tx_data.get("currency") != payment.currency or float(tx_data.get("amount", 0)) < float(payment.amount):
            payment.status = "failed"
            db.commit()
            return jsonify({"detail": "Payment amount or currency mismatch"}), 400

        payment.status = "successful"
        payment.flutterwave_id = str(tx_data.get("id"))
        payment.verified_at = datetime.utcnow()

        days = PLAN_DAYS[payment.plan]
        base = user.premium_expires if (user.premium_expires and user.premium_expires > datetime.utcnow()) else datetime.utcnow()
        user.premium_expires = base + timedelta(days=days)
        user.is_premium = True

        db.commit()

        return jsonify({
            "is_premium": True,
            "premium_expires": user.premium_expires.isoformat(),
        })

    return _inner()
