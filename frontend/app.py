import json
import random
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2

random.seed(42)

# -------------------------------
# 1. SAMPLE LOCATIONS AND MCCS
# -------------------------------

LOCATIONS = {
    "Bengaluru": (12.9716, 77.5946),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639)
}

# Example MCCs: 5944 = jewellery, 7995 = gambling,
# 5411 = grocery, 5812 = restaurants, 5541 = fuel.
HIGH_RISK_MCCS = {5944, 7995}
MCCS = [5411, 5812, 5541, 5944, 7995]


# -------------------------------
# 2. TRANSACTION GENERATOR
# -------------------------------

def make_transaction(cardholder, timestamp, amount,
                     location, mcc, device):
    return {
        "transaction_id": f"TXN{random.randint(100000, 999999)}",
        "cardholder_id": cardholder,
        "timestamp": timestamp.isoformat(),
        "amount": round(amount, 2),
        "currency": "INR",
        "location": location,
        "mcc": mcc,
        "device_id": device,
        "anomaly_flag": False,
        "anomaly_codes": [],
        "rule_rationales": []
    }


def generate_transactions():
    transactions = []
    base_time = datetime(
        2026, 10, 20, 10, 0, tzinfo=timezone.utc
    )

    # Generate normal transactions for 5 cardholders.
    for person in range(1, 6):
        cardholder = f"CH{person:03d}"
        normal_avg = random.choice([500, 800, 1200, 1500])

        for i in range(8):
            timestamp = base_time + timedelta(
                days=i, hours=random.randint(0, 10)
            )
            transaction = make_transaction(
                cardholder,
                timestamp,
                random.uniform(normal_avg * 0.4,
                               normal_avg * 1.5),
                random.choice(list(LOCATIONS)),
                random.choice([5411, 5812, 5541]),
                f"DEV{person}A"
            )
            transaction["historical_avg_amount"] = normal_avg
            transactions.append(transaction)

    # Pattern 1: Geographically impossible travel.
    transactions.append(make_transaction(
        "CH001", base_time + timedelta(days=9, hours=10),
        900, "Bengaluru", 5411, "DEV1A"
    ))
    transactions.append(make_transaction(
        "CH001", base_time + timedelta(days=9, hours=10,
                                       minutes=20),
        1100, "Delhi", 5812, "DEV9X"
    ))

    # Pattern 2: Amount far above normal spending.
    transactions.append(make_transaction(
        "CH002", base_time + timedelta(days=9, hours=5),
        10000, "Mumbai", 5411, "DEV2A"
    ))

    # Pattern 3: High-risk merchant at 3 AM.
    transactions.append(make_transaction(
        "CH003", base_time + timedelta(days=9, hours=3),
        4500, "Chennai", 5944, "DEV3A"
    ))

    # Pattern 4: Rapid, small-value card testing.
    for seconds in [0, 10, 20, 30, 40]:
        transactions.append(make_transaction(
            "CH004",
            base_time + timedelta(days=9, hours=12,
                                  seconds=seconds),
            20 + seconds / 10,
            "Bengaluru", 5411, "DEV4A"
        ))

    # Pattern 5: Previously unseen device.
    transactions.append(make_transaction(
        "CH005", base_time + timedelta(days=9, hours=6),
        700, "Kolkata", 5812, "NEW_DEVICE_X"
    ))

    return transactions


# -------------------------------
# 3. HELPER: DISTANCE BETWEEN CITIES
# -------------------------------

def distance_km(city1, city2):
    lat1, lon1 = LOCATIONS[city1]
    lat2, lon2 = LOCATIONS[city2]

    lat1, lon1, lat2, lon2 = map(
        radians, [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (sin(dlat / 2) ** 2
         + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2)

    return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))


# -------------------------------
# 4. FRAUD RULE ENGINE
# -------------------------------

def detect_anomalies(transactions):
    by_cardholder = {}

    for tx in transactions:
        by_cardholder.setdefault(
            tx["cardholder_id"], []
        ).append(tx)

    for cardholder, items in by_cardholder.items():
        items.sort(key=lambda x: x["timestamp"])

        # Rule: detect large amounts using historical average.
        history_avg = next(
            (tx["historical_avg_amount"] for tx in items
             if "historical_avg_amount" in tx),
            1000
        )

        for tx in items:
            if tx["amount"] >= 5 * history_avg:
                tx["anomaly_codes"].append(
                    "BEHAVIORAL_DEVIATION"
                )
                tx["rule_rationales"].append(
                    "Amount is at least 5 times the "
                    "cardholder's reference spending average."
                )

            # Rule: high-risk MCC during midnight hours.
            hour = datetime.fromisoformat(
                tx["timestamp"]
            ).hour

            if tx["mcc"] in HIGH_RISK_MCCS and (
                hour >= 0 and hour < 5
            ):
                tx["anomaly_codes"].append(
                    "HIGH_RISK_OFF_HOURS"
                )
                tx["rule_rationales"].append(
                    "High-risk merchant category used "
                    "between midnight and 5 AM UTC."
                )

            # Rule: device never seen in earlier transactions.
            earlier = [
                old for old in items
                if old["timestamp"] < tx["timestamp"]
            ]
            known_devices = {
                old["device_id"] for old in earlier
            }

            if (earlier and
                    tx["device_id"] not in known_devices):
                tx["anomaly_codes"].append("NEW_DEVICE")
                tx["rule_rationales"].append(
                    "Transaction used a device not seen "
                    "in earlier recorded transactions."
                )

        # Rule: geographically impossible travel.
        for previous, current in zip(items, items[1:]):
            t1 = datetime.fromisoformat(previous["timestamp"])
            t2 = datetime.fromisoformat(current["timestamp"])
            minutes = (t2 - t1).total_seconds() / 60

            km = distance_km(
                previous["location"], current["location"]
            )

            if 0 < minutes <= 60 and km >= 500:
                for tx in [previous, current]:
                    tx["anomaly_codes"].append(
                        "GEO_VELOCITY_SPIKE"
                    )
                    tx["rule_rationales"].append(
                        "Transactions occurred in locations "
                        "over 500 km apart within 60 minutes."
                    )

        # Rule: multiple small transactions within 60 seconds.
        for i, tx in enumerate(items):
            start = datetime.fromisoformat(tx["timestamp"])
            rapid = []

            for other in items[i:]:
                t = datetime.fromisoformat(other["timestamp"])
                seconds = (t - start).total_seconds()

                if seconds > 60:
                    break

                if 0 <= seconds and other["amount"] <= 100:
                    rapid.append(other)

            if len(rapid) >= 4:
                for item in rapid:
                    item["anomaly_codes"].append(
                        "MICRO_TRANSACTION_TESTING"
                    )
                    item["rule_rationales"].append(
                        "Four or more transactions of "
                        "100 INR or less occurred within "
                        "60 seconds."
                    )

    # Final flags and remove duplicate rule codes.
    for tx in transactions:
        tx["anomaly_codes"] = list(
            dict.fromkeys(tx["anomaly_codes"])
        )
        tx["rule_rationales"] = list(
            dict.fromkeys(tx["rule_rationales"])
        )
        tx["anomaly_flag"] = bool(tx["anomaly_codes"])

    return transactions


# -------------------------------
# 5. EXPORT JSON
# -------------------------------

def main():
    transactions = generate_transactions()
    transactions = detect_anomalies(transactions)

    with open("transactions.json", "w", encoding="utf-8") as file:
        json.dump(transactions, file, indent=4)

    flagged = [
        tx for tx in transactions if tx["anomaly_flag"]
    ]

    print("Synthetic transaction dataset created.")
    print("Total transactions:", len(transactions))
    print("Flagged transactions:", len(flagged))
    print("Normal transactions:",
          len(transactions) - len(flagged))
    print("Output file: transactions.json")

    print("\nFlagged transaction examples:")
    for tx in flagged:
        print(
            tx["transaction_id"],
            tx["cardholder_id"],
            tx["anomaly_codes"]
        )


if __name__ == "__main__":
    main()