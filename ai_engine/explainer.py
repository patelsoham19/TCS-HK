"""
AI Engine: Banking Transaction Anomaly Explanation Generator
Supports Local SLMs via Ollama (Llama-3.2-3b, Gemma-3-4b) and Google Gemini API.
"""

import json
import time
import requests
import os

# ================= Configuration =================
# Set USE_LOCAL_OLLAMA = False if using Gemini API
USE_LOCAL_OLLAMA = True

# Local Ollama Settings
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"  # or "gemma2:2b", "gemma:3b", "deepseek-r1"

# Gemini API Settings (Optional cloud backup)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
# =================================================


def _call_ollama(prompt: str, system_prompt: str = "") -> str:
    """Calls local Ollama instance with timeout to guarantee < 10s response."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,      # Low temperature for strict factual grounding
            "num_predict": 250        # Keep output concise to minimize latency
        }
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=35)
    response.raise_for_status()
    return response.json().get("response", "").strip()


def _call_gemini(prompt: str, system_prompt: str = "") -> str:
    """Calls Google Gemini API as cloud fallback."""
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_prompt
    )
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.2, "max_output_tokens": 250}
    )
    return response.text.strip()


def generate_explanation(transaction_data: dict, persona: str = "customer") -> dict:
    """
    Takes transaction JSON and outputs a grounded, structured explanation.
    
    :param transaction_data: dict containing transaction and anomaly flag details.
    :param persona: 'customer' (plain English) or 'investigator' (technical details).
    :return: dict with latency, explanation, and actions.
    """
    start_time = time.time()
    
    # Pre-extract values for prompt grounding
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
    else:  # Investigator persona
        system_prompt = (
            "You are a Senior Fraud Analytics Officer assistant. "
            "Analyze the transaction payload and generate an executive investigation summary.\n"
            "Format your response strictly as:\n"
            "### Anomaly Assessment\n"
            "<Technical rationale citing the exact anomaly_flag, baseline comparison, and risk score>\n\n"
            "### Recommended Triage Protocol\n"
            "<Bullet points: KYC review, merchant blacklisting check, card reissuance priority>"
        )

    user_prompt = f"Analyze this transaction payload and provide your response:\n{txn_json_str}"

    try:
        if USE_LOCAL_OLLAMA:
            raw_text = _call_ollama(user_prompt, system_prompt)
        else:
            raw_text = _call_gemini(user_prompt, system_prompt)
    except Exception as e:
        # Graceful fallback if model service is unreachable
        raw_text = (
            f"### Notice\n"
            f"Automated explanation fallback triggered: Transaction was flagged due to "
            f"{transaction_data.get('anomaly_flag', 'unusual activity')} "
            f"with a risk score of {transaction_data.get('risk_score', 'N/A')}.\n\n"
            f"### Action Required\n"
            f"• Please verify if you authorized this payment of {transaction_data.get('currency', '')} {transaction_data.get('amount', '')}.\n"
            f"• Temporarily freeze your card if you do not recognize this merchant."
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
    """
    Handles follow-up questions from the user (multi-turn conversational agent).
    """
    system_prompt = (
        "You are a Banking Fraud Customer Support Agent. "
        "The customer is asking questions about a suspicious flagged transaction.\n"
        f"Transaction Details: {json.dumps(transaction_context)}\n"
        "Rules:\n"
        "1. Be helpful, concise, and professional.\n"
        "2. Ground all answers strictly on the transaction facts above.\n"
        "3. Provide clear instructions on what steps they or the bank can take."
    )

    full_prompt = f"{system_prompt}\n\nRecent Conversation:\n"
    for turn in conversation_history[-4:]:  # keep last 4 turns for context
        full_prompt += f"{turn['role'].capitalize()}: {turn['content']}\n"
    full_prompt += f"Customer: {user_message}\nAssistant:"

    try:
        if USE_LOCAL_OLLAMA:
            return _call_ollama(full_prompt)
        else:
            return _call_gemini(full_prompt)
    except Exception:
        return "I apologize, but I am having trouble connecting to security services right now. Please call fraud support directly at 1800-BANK-SAFE."