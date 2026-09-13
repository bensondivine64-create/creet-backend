import time
import requests

_rate_cache = {}
CACHE_TTL_SECONDS = 6 * 60 * 60


def _get_rates(base_currency):
    now = time.time()
    cached = _rate_cache.get(base_currency)
    if cached and now - cached["fetched_at"] < CACHE_TTL_SECONDS:
        return cached["rates"]
    try:
        resp = requests.get(f"https://open.er-api.com/v6/latest/{base_currency}", timeout=5)
        data = resp.json()
        if data.get("result") == "success":
            rates = data.get("rates", {})
            _rate_cache[base_currency] = {"rates": rates, "fetched_at": now}
            return rates
    except Exception:
        pass
    return cached["rates"] if cached else None


def convert_currency(amount, from_currency, to_currency):
    if not from_currency or not to_currency or from_currency == to_currency:
        return amount
    rates = _get_rates(from_currency)
    if not rates or to_currency not in rates:
        return None
    return round(amount * rates[to_currency], 2)
