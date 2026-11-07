"""
AI Engine: Banking Transaction Anomaly Explanation Generator
Powered exclusively by Local SLMs via Ollama.
"""

import json
import time
import requests
import os

# ================= Ollama Configuration =================
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
# ========================================================


def _extract_flag_summary(tx: dict) -> str:
    """Extracts human-readable anomaly descriptions instead of booleans."""
    if tx.get("rule_rationales"):
        return "; ".join(tx["rule_rationales"])
    if tx.get("anomaly_codes"):
        return ", ".join(tx["anomaly_codes"])
    flag = tx.get("anomaly_flag")
    if isinstance(flag, str) and flag.lower() not in ("true", "false"):
        return flag
    return "Unusual transaction characteristics detected"


def _call_ollama_generate(prompt: str, system_prompt: str = "") -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 250
        }
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=12)
    response.raise_for_status()
    return response.json().get("response", "").strip()


def _call_ollama_chat(messages: list) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 200
        }
    }
    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=12)
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "").strip()


def generate_explanation(transaction_data: dict, persona: str = "customer") -> dict:
    """Takes transaction JSON and outputs a grounded, structured explanation."""
    start_time = time.time()
    flag_summary = _extract_flag_summary(transaction_data)
    txn_json_str = json.dumps(transaction_data, indent=2)

    if persona.lower() == "customer":
        system_prompt = (
            "You are an empathetic, clear Banking Fraud Security Assistant. "
            "Your task is to explain to a customer why their transaction was flagged as suspicious, "
            "grounding your reasoning EXCLUSIVELY on the provided JSON data. Never invent facts.\n"
            "Format your answer strictly with two headings:\n"
            "### Why this was flagged\n"
            "<1-2 clear, plain-English sentences without technical error codes>\n\n"
            "### What you should do next\n"
            "<2-3 bullet points with simple action steps, e.g. confirm activity, lock card, contact support>"
        )
    else:
        system_prompt = (
            "You are a Senior Fraud Analytics Officer assistant. "
            "Analyze the transaction payload and generate an executive investigation summary.\n"
            "Format your response strictly as:\n"
            "### Anomaly Assessment\n"
            "<Technical rationale citing the exact anomaly flags, baseline comparison, and risk score>\n\n"
            "### Recommended Triage Protocol\n"
            "<Bullet points: KYC review, merchant blacklisting check, card reissuance priority>"
        )

    user_prompt = f"Analyze this transaction payload and provide your response:\n{txn_json_str}"

    try:
        raw_text = _call_ollama_generate(user_prompt, system_prompt)
    except Exception:
        # Grounded deterministic fallback in case Ollama service is unreachable
        raw_text = (
            f"### Why this was flagged\n"
            f"This transaction was flagged due to: {flag_summary} "
            f"(Assigned risk score: {transaction_data.get('risk_score', 'N/A')}/100).\n\n"
            f"### What you should do next\n"
            f"• Confirm if you authorized this charge of {transaction_data.get('currency', 'INR')} {transaction_data.get('amount', '0.00')}.\n"
            f"• Freeze your debit or credit card via the mobile banking app if unrecognized.\n"
            f"• Contact bank security immediately to dispute the charge."
        )

    latency = round(time.time() - start_time, 2)

    return {
        "transaction_id": transaction_data.get("transaction_id", "UNKNOWN"),
        "persona": persona,
        "latency_seconds": latency,
        "under_10s_sla": latency < 10.0,
        "explanation": raw_text
    }


def chat_with_agent(conversation_history: list, user_message: str, transaction_context: dict) -> str:
    """Handles multi-turn conversational follow-up questions."""
    system_prompt = (
        "You are a Banking Fraud Customer Support Agent. "
        "The customer is asking questions about a suspicious flagged transaction.\n"
        f"Transaction Details: {json.dumps(transaction_context)}\n"
        "Rules:\n"
        "1. Be helpful, concise, and professional.\n"
        "2. Ground all answers strictly on the transaction facts above.\n"
        "3. Provide clear instructions on what steps they or the bank can take."
    )

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for turn in conversation_history[-4:]:
            role = "assistant" if turn.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": turn.get("content", "")})
        messages.append({"role": "user", "content": user_message})
        
        return _call_ollama_chat(messages)
    except Exception:
        return "If you did not authorize this payment, please lock your card in the banking app immediately and reach out to fraud support at 1800-BANK-SAFE."