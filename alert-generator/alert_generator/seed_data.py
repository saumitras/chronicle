import random
import uuid
from datetime import datetime, timezone, timedelta

# ── Customers ─────────────────────────────────────────────────────────────────
CUSTOMERS = [
    {"customer_id": str(uuid.uuid4()), "name": f"Customer_{i:03d}",
     "account_age_days": random.randint(30, 3000),
     "transaction_avg": round(random.uniform(20, 500), 2),
     "prior_alerts": random.randint(0, 3),
     "risk_profile": random.choice(["low", "low", "low", "medium", "high"])}
    for i in range(50)
]

# ── Devices ───────────────────────────────────────────────────────────────────
DEVICES = [
    {"device_id": str(uuid.uuid4()),
     "customer_id": CUSTOMERS[i % len(CUSTOMERS)]["customer_id"],
     "device_type": random.choice(["mobile", "desktop", "tablet"]),
     "known": random.random() > 0.2,
     "fraud_flags": random.randint(0, 2)}
    for i in range(100)
]

# ── Merchants ─────────────────────────────────────────────────────────────────
MERCHANTS = [
    {"name": name, "category": category, "country": country, "risk_level": risk}
    for name, category, country, risk in [
        ("Amazon", "ecommerce", "US", "low"),
        ("Netflix", "streaming", "US", "low"),
        ("Uber", "transport", "US", "low"),
        ("Steam", "gaming", "US", "low"),
        ("Spotify", "streaming", "SE", "low"),
        ("AliExpress", "ecommerce", "CN", "medium"),
        ("Binance", "crypto", "MT", "high"),
        ("LocalMart", "retail", "IN", "low"),
        ("CryptoExchange", "crypto", "RU", "high"),
        ("TravelBooking", "travel", "AE", "medium"),
        ("QuickLoans", "finance", "NG", "high"),
        ("OnlinePharmacy", "health", "PH", "medium"),
        ("GameTokens", "gaming", "KP", "high"),
        ("FXTrader", "finance", "PA", "high"),
        ("ShopExpress", "ecommerce", "BR", "medium"),
    ]
]

# ── Countries ─────────────────────────────────────────────────────────────────
COUNTRY_RISK = {
    "US": "low", "GB": "low", "DE": "low", "AU": "low", "CA": "low",
    "FR": "low", "JP": "low", "SE": "low", "IN": "low", "SG": "low",
    "CN": "medium", "BR": "medium", "MX": "medium", "AE": "medium", "PH": "medium",
    "RU": "high", "NG": "high", "KP": "high", "PA": "high", "MT": "high",
}

HOME_COUNTRIES = ["US", "GB", "DE", "AU", "CA", "FR", "JP", "IN"]

VPN_IP_RANGES = [
    "185.220.x.x", "104.244.x.x", "199.87.x.x",
    "198.98.x.x", "23.129.x.x",
]


def get_random_customer():
    return random.choice(CUSTOMERS)


def get_device_for_customer(customer_id: str, force_unknown: bool = False):
    owned = [d for d in DEVICES if d["customer_id"] == customer_id]
    if owned and not force_unknown:
        return random.choice(owned)
    # Return an unknown device
    return {
        "device_id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "device_type": random.choice(["mobile", "desktop"]),
        "known": False,
        "fraud_flags": random.randint(0, 1),
    }


def get_random_merchant(risk_level: str | None = None):
    if risk_level:
        pool = [m for m in MERCHANTS if m["risk_level"] == risk_level]
        return random.choice(pool) if pool else random.choice(MERCHANTS)
    return random.choice(MERCHANTS)


def build_alert(risk_profile: str = "random") -> dict:
    """
    Build a realistic alert payload.
    risk_profile: "low" | "medium" | "high" | "random"
    """
    if risk_profile == "random":
        risk_profile = random.choices(
            ["low", "medium", "high"], weights=[60, 25, 15]
        )[0]

    customer = get_random_customer()
    customer_id = customer["customer_id"]

    if risk_profile == "low":
        device = get_device_for_customer(customer_id)
        merchant = get_random_merchant("low")
        country = random.choice(HOME_COUNTRIES)
        amount = round(random.uniform(10, customer["transaction_avg"] * 1.2), 2)
        vpn = False

    elif risk_profile == "medium":
        device = get_device_for_customer(customer_id, force_unknown=random.random() > 0.5)
        merchant = get_random_merchant("medium")
        country = random.choice(list(COUNTRY_RISK.keys()))
        amount = round(random.uniform(
            customer["transaction_avg"] * 1.5,
            customer["transaction_avg"] * 3
        ), 2)
        vpn = random.random() > 0.7

    else:  # high
        device = get_device_for_customer(customer_id, force_unknown=True)
        merchant = get_random_merchant("high")
        country = random.choice([c for c, r in COUNTRY_RISK.items() if r == "high"])
        amount = round(random.uniform(
            customer["transaction_avg"] * 3,
            customer["transaction_avg"] * 10
        ), 2)
        vpn = random.random() > 0.3

    return {
        "alert_id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "account_id": str(uuid.uuid4()),
        "device_id": device["device_id"],
        "merchant": merchant["name"],
        "merchant_country": merchant["country"],
        "merchant_risk_level": merchant["risk_level"],
        "amount": amount,
        "currency": "USD",
        "country": country,
        "vpn_detected": vpn,
        "risk_profile": risk_profile,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
