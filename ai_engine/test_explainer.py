"""Quick verification script for Person 2 to test latency and output quality."""

import json
from explainer import generate_explanation, chat_with_agent

# Sample test transaction
sample_txn = {
    "transaction_id": "TXN_10928",
    "account_id": "ACC_9921",
    "amount": 75000.00,
    "currency": "INR",
    "timestamp": "2026-10-28T02:45:00",
    "merchant": "Apex Crypto Global",
    "merchant_category": "Cryptocurrency Exchange",
    "location": "Lagos, Nigeria",
    "cardholder_city": "Bengaluru, India",
    "anomaly_flag": "ERR_GEO_VELOCITY",
    "risk_score": 94,
    "flag_rationale": "Transaction initiated from Lagos 45 minutes after physical card swipe in Bengaluru."
}

print("====================================================")
print("1. Testing Customer View Explanation...")
customer_res = generate_explanation(sample_txn, persona="customer")
print(f"Latency: {customer_res['latency_seconds']}s (Meets <10s requirement: {customer_res['under_10s_sla']})")
print("\nOutput:\n", customer_res['explanation'])

print("\n====================================================")
print("2. Testing Investigator View Explanation...")
investigator_res = generate_explanation(sample_txn, persona="investigator")
print(f"Latency: {investigator_res['latency_seconds']}s")
print("\nOutput:\n", investigator_res['explanation'])

print("\n====================================================")
print("3. Testing Conversational Follow-up...")
history = [{"role": "assistant", "content": customer_res['explanation']}]
user_query = "I am currently traveling in Nigeria, how do I approve this charge?"
chat_reply = chat_with_agent(history, user_query, sample_txn)
print(f"User: {user_query}")
print(f"AI Agent: {chat_reply}")
print("====================================================")