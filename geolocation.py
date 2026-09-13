import requests
from flask import request

_ip_country_cache = {}

COUNTRY_CURRENCY = {
    "Nigeria": "NGN",
    "United States": "USD",
    "United Kingdom": "GBP",
    "Ghana": "GHS",
    "Kenya": "KES",
    "South Africa": "ZAR",
    "Canada": "CAD",
    "Germany": "EUR",
    "France": "EUR",
    "India": "INR",
}


def get_client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr


def get_country_for_ip(ip):
    if not ip or ip.startswith("127.") or ip == "::1":
        return None
    if ip in _ip_country_cache:
        return _ip_country_cache[ip]
    try:
        resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=3)
        data = resp.json()
        country = data.get("country_name")
        if country:
            _ip_country_cache[ip] = country
        return country
    except Exception:
        return None


def get_client_country():
    try:
        return get_country_for_ip(get_client_ip())
    except Exception:
        return None


def currency_for_country(country):
    return COUNTRY_CURRENCY.get(country, "USD")
