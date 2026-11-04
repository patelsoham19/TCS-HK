"""Verification script for testing latency, output quality, and fallback behavior."""

from explainer import generate_explanation, chat_with_agent

sample_txn = {
    "transaction_id": "TXN_10928",
    "account_id": "ACC_9921",
    "amount": 75000.00,
    "currency": "INR",
    "timestamp": "2026-10-28T02:45:00",
    "merchant": "Apex Crypto Global",
    "merchant_category": "Cryptocurrency Exchange",
    "location": "Tokyo, Japan",
    "cardholder_city": "Bengaluru, India",
    "anomaly_flag": True,
    "anomaly_codes": ["ERR_GEO_VELOCITY"],
    "risk_score": 94,
    "rule_rationales": ["Transaction initiated from Tokyo 45 minutes after physical card swipe in Bengaluru."]
}

if __name__ == "__main__":
    print("=" * 60)
    print("1. Testing Customer View Explanation...")
    cust_res = generate_explanation(sample_txn, persona="customer")
    print(f"Latency: {cust_res['latency_seconds']}s (SLA Met: {cust_res['under_10s_sla']})")
    print(cust_res['explanation'])

    print("\n" + "=" * 60)
    print("2. Testing Investigator View Explanation...")
    inv_res = generate_explanation(sample_txn, persona="investigator")
    print(f"Latency: {inv_res['latency_seconds']}s")
    print(inv_res['explanation'])

    print("\n" + "=" * 60)
    print("3. Testing Conversational Follow-up...")
    history = [{"role": "assistant", "content": cust_res['explanation']}]
    user_msg = "I am currently traveling in Japan. How do I unfreeze this charge?"
    reply = chat_with_agent(history, user_msg, sample_txn)
    print(f"Customer: {user_msg}")
    print(f"Agent: {reply}")
    print("=" * 60)