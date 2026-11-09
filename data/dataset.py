"""
Synthetic Transaction & Fraud Rule Generator
Outputs: data/transactions.json
"""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2

random.seed(42)

LOCATIONS = {
    "Bengaluru": (12.9716, 77.5946),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639)
}

HIGH_RISK_MCCS = {5944, 7995}  # Jewelry, Gambling

def make_transaction(cardholder, timestamp, amount, location, mcc, device):
    return {
        "transaction_id": f"TXN{random.randint(100000, 999999)}",
        "cardholder_id": cardholder,
        "account_id": f"ACC_{cardholder}",
        "timestamp": timestamp.isoformat(),
        "amount": round(amount, 2),
        "currency": "INR",
        "location": location,
        "mcc": mcc,
        "merchant_category": "Luxury Jewelry" if mcc == 5944 else "Gambling/Crypto" if mcc == 7995 else "Retail/Food",
        "device_id": device,
        "anomaly_flag": False,
        "anomaly_codes": [],
        "rule_rationales": [],
        "risk_score": 20
    }

def distance_km(city1, city2):
    lat1, lon1 = LOCATIONS[city1]
    lat2, lon2 = LOCATIONS[city2]
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))

def generate_transactions():
    transactions = []
    base_time = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)

    for person in range(1, 6):
        cardholder = f"CH{person:03d}"
        normal_avg = random.choice([500, 800, 1200, 1500])
        for i in range(5):
            ts = base_time + timedelta(days=i, hours=random.randint(0, 10))
            tx = make_transaction(
                cardholder,
                ts,
                random.uniform(normal_avg * 0.5, normal_avg * 1.4),
                random.choice(list(LOCATIONS)),
                random.choice([5411, 5812, 5541]),
                f"DEV{person}A"
            )
            tx["historical_avg_amount"] = normal_avg
            transactions.append(tx)

    # Anomaly 1: Impossible Travel (Bengaluru -> Delhi in 20 mins)
    transactions.append(make_transaction("CH001", base_time + timedelta(days=6, hours=10), 900, "Bengaluru", 5411, "DEV1A"))
    transactions.append(make_transaction("CH001", base_time + timedelta(days=6, hours=10, minutes=20), 1100, "Delhi", 5812, "DEV9X"))

    # Anomaly 2: Extreme Spending Spike
    transactions.append(make_transaction("CH002", base_time + timedelta(days=6, hours=5), 185000, "Mumbai", 5411, "DEV2A"))

    # Anomaly 3: High-Risk MCC at 3 AM
    transactions.append(make_transaction("CH003", base_time + timedelta(days=6, hours=3), 45000, "Chennai", 5944, "DEV3A"))

    # Anomaly 4: Micro-charge card testing
    for sec in [0, 10, 20, 30, 40]:
        transactions.append(make_transaction("CH004", base_time + timedelta(days=6, hours=12, seconds=sec), 25.0 + sec, "Bengaluru", 5411, "DEV4A"))

    return transactions

def detect_anomalies(transactions):
    by_user = {}
    for tx in transactions:
        by_user.setdefault(tx["cardholder_id"], []).append(tx)

    for cardholder, items in by_user.items():
        items.sort(key=lambda x: x["timestamp"])
        history_avg = next((tx["historical_avg_amount"] for tx in items if "historical_avg_amount" in tx), 1000)

        # Baseline & MCC checks
        for tx in items:
            if tx["amount"] >= 5 * history_avg:
                tx["anomaly_codes"].append("ERR_AMOUNT_SPIKE")
                tx["rule_rationales"].append(f"Amount of INR {tx['amount']} exceeds 5x cardholder reference spend (INR {history_avg}).")
                tx["risk_score"] = max(tx["risk_score"], 92)

            hour = datetime.fromisoformat(tx["timestamp"]).hour
            if tx["mcc"] in HIGH_RISK_MCCS and (0 <= hour < 5):
                tx["anomaly_codes"].append("ERR_OFF_HOURS_HIGH_RISK")
                tx["rule_rationales"].append("High-risk merchant code executed during off-hours (00:00 - 05:00 UTC).")
                tx["risk_score"] = max(tx["risk_score"], 88)

        # Velocity / Geo-speed check
        for prev, curr in zip(items, items[1:]):
            t1 = datetime.fromisoformat(prev["timestamp"])
            t2 = datetime.fromisoformat(curr["timestamp"])
            mins = (t2 - t1).total_seconds() / 60
            km = distance_km(prev["location"], curr["location"])
            if 0 < mins <= 60 and km >= 500:
                for target in [prev, curr]:
                    target["anomaly_codes"].append("ERR_GEO_VELOCITY")
                    target["rule_rationales"].append(f"Speed anomaly: Card swiped in {prev['location']} and {curr['location']} ({int(km)} km) within {int(mins)} minutes.")
                    target["risk_score"] = max(target["risk_score"], 96)

        # Micro-charge card testing check (>= 3 micro charges under 100 within 2 minutes)
        for i in range(len(items)):
            recent_burst = [
                items[j] for j in range(len(items))
                if 0 <= (datetime.fromisoformat(items[j]["timestamp"]) - datetime.fromisoformat(items[i]["timestamp"])).total_seconds() <= 120
                and items[j]["amount"] < 100.0
            ]
            if len(recent_burst) >= 3:
                for target in recent_burst:
                    target["anomaly_codes"].append("ERR_CARD_TESTING")
                    target["rule_rationales"].append("Rapid micro-transactions executed within 2 minutes indicating automated card testing.")
                    target["risk_score"] = max(target["risk_score"], 84)

    for tx in transactions:
        tx["anomaly_codes"] = list(dict.fromkeys(tx["anomaly_codes"]))
        tx["rule_rationales"] = list(dict.fromkeys(tx["rule_rationales"]))
        tx["anomaly_flag"] = bool(tx["anomaly_codes"])
        if not tx["anomaly_flag"]:
            tx["risk_score"] = 15

    return transactions

if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    txs = detect_anomalies(generate_transactions())
    out_file = out_dir / "transactions.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(txs, f, indent=2)
    print(f"Generated {len(txs)} transactions successfully at {out_file}")