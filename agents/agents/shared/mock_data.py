import logging
import random

from agents.shared.db import get_pool

logger = logging.getLogger(__name__)

HIGH_RISK_COUNTRIES = {"RU", "NG", "KP", "PA", "MT", "BY", "IR", "SY"}
MEDIUM_RISK_COUNTRIES = {"CN", "BR", "MX", "AE", "PH", "UA", "VN"}


async def get_customer_profile(customer_id: str) -> dict:
    """Query seed_customers table, fall back to deterministic hash if not found."""
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT account_age_days, transaction_avg, prior_alerts, risk_profile "
            "FROM seed_customers WHERE customer_id = $1", customer_id
        )
        if row:
            return {
                "customer_id": customer_id,
                "account_age_days": row["account_age_days"],
                "transaction_avg": float(row["transaction_avg"]),
                "prior_alerts": row["prior_alerts"],
                "prior_fraud": row["risk_profile"] == "high",
            }
    except Exception as e:
        logger.warning("DB customer lookup failed, using hash: %s", e)

    # Fallback: deterministic hash
    seed = int(customer_id.replace("-", "")[:8], 16)
    rng = random.Random(seed)
    return {
        "customer_id": customer_id,
        "account_age_days": rng.randint(30, 3000),
        "transaction_avg": round(rng.uniform(20, 500), 2),
        "prior_alerts": rng.randint(0, 4),
        "prior_fraud": rng.random() < 0.1,
    }


async def get_device_profile(device_id: str) -> dict:
    """Query seed_devices table, fall back to deterministic hash if not found."""
    try:
        pool = await get_pool()
        row = await pool.fetchrow(
            "SELECT known, fraud_flags FROM seed_devices WHERE device_id = $1", device_id
        )
        if row:
            return {
                "device_id": device_id,
                "known": row["known"],
                "device_age_days": 365,  # default for seeded devices
                "fraud_flags": row["fraud_flags"],
            }
    except Exception as e:
        logger.warning("DB device lookup failed, using hash: %s", e)

    # Fallback: deterministic hash
    seed = int(device_id.replace("-", "")[:8], 16)
    rng = random.Random(seed)
    return {
        "device_id": device_id,
        "known": rng.random() > 0.25,
        "device_age_days": rng.randint(0, 1000),
        "fraud_flags": rng.randint(0, 2),
    }


def get_country_risk(country: str) -> str:
    if country in HIGH_RISK_COUNTRIES:
        return "high"
    if country in MEDIUM_RISK_COUNTRIES:
        return "medium"
    return "low"
