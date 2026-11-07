"""
Automated Evaluation Suite for Hackathon Demo
Validates SLA latency (<10s) and clarity metrics (>=85%).
"""

import time
import requests

BACKEND_URL = "http://127.0.0.1:8000"

def evaluate_clarity(text: str) -> float:
    score = 0
    words = text.split()
    total_words = len(words)

    # Word count scoring for optimal length
    if 30 <= total_words <= 120:
        score += 35
    elif total_words < 180:
        score += 20
    else:
        score += 10

    # Structure scoring: Markdown headers
    if "###" in text or "Why" in text:
        score += 25

    # Bullet point formatting
    if any(bullet in text for bullet in ["•", "<li>", "-", "*"]):
        score += 20

    # Actionable guidance scoring
    action_words = ["verify", "lock", "freeze", "dispute", "call", "review", "confirm", "action"]
    if any(w in text.lower() for w in action_words):
        score += 20

    return min(score, 100)

def main():
    print("=" * 60)
    print("EVALUATING SYSTEM FOR HACKATHON BENCHMARKS")
    print("=" * 60)

    # 1. Fetch transactions from the backend
    try:
        res = requests.get(f"{BACKEND_URL}/api/transactions", timeout=5)
        res.raise_for_status()
        txs = res.json()
    except Exception as e:
        print(f"[ERROR] Could not connect to backend at {BACKEND_URL}: {e}")
        print("Make sure the backend is running via: uvicorn backend.main:app --port 8000")
        return

    # 2. Filter flagged anomalies
    flagged = [
        t for t in txs 
        if t.get("anomaly_flag") is True 
        or str(t.get("anomaly_flag")).lower() == "true"
        or len(t.get("anomaly_codes", [])) > 0
    ]

    if not flagged:
        print("[WARNING] No flagged transactions found to benchmark.")
        return

    latencies = []
    clarities = []

    print(f"Running evaluation against {min(5, len(flagged))} flagged transaction samples...\n")

    for i, tx in enumerate(flagged[:5], 1):
        t0 = time.time()
        try:
            res = requests.post(
                f"{BACKEND_URL}/api/explain",
                json={"transaction": tx, "persona": "customer"},
                timeout=25
            )
            res.raise_for_status()
            data = res.json()
            
            lat = round(time.time() - t0, 2)
            latencies.append(lat)
            
            clarity = evaluate_clarity(data.get("explanation", ""))
            clarities.append(clarity)

            print(f"Sample {i} [{tx.get('transaction_id')}]: Latency={lat}s | Clarity={clarity}%")
        except Exception as err:
            print(f"Sample {i} [{tx.get('transaction_id')}] Failed: {err}")

    if latencies:
        avg_lat = round(sum(latencies) / len(latencies), 2)
        avg_clarity = round(sum(clarities) / len(clarities), 1)

        print("\n" + "=" * 60)
        print(f"AVERAGE LATENCY: {avg_lat}s (Requirement: < 10.0s) -> {'PASSED' if avg_lat < 10 else 'FAILED'}")
        print(f"AVERAGE CLARITY: {avg_clarity}% (Requirement: >= 85%) -> {'PASSED' if avg_clarity >= 85 else 'FAILED'}")
        print("=" * 60)

if __name__ == "__main__":
    main()