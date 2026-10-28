"""
Backend Orchestrator for Banking Transaction Anomaly Explanation Generator
Connects synthetic transaction data with GenAI explainer and exposes REST API.
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root is in sys.path so we can import Person 2's ai_engine
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

# Import Person 2's functions
try:
    from ai_engine.explainer import generate_explanation, chat_with_agent
    print("[SUCCESS] Loaded ai_engine.explainer successfully.")
except Exception as e:
    print(f"[WARNING] Could not load ai_engine: {e}. Fallback enabled.")
    def generate_explanation(data, persona="customer"):
        return {
            "transaction_id": data.get("transaction_id", "N/A"),
            "persona": persona,
            "latency_seconds": 0.05,
            "under_10s_sla": True,
            "explanation": f"### Flagged Alert\nTransaction of {data.get('currency', 'INR')} {data.get('amount')} flagged due to {data.get('anomaly_flag')}."
        }
    def chat_with_agent(history, msg, ctx):
        return f"Support received: '{msg}'. For security, card actions are currently paused."

app = FastAPI(
    title="Banking Anomaly Explanation API",
    description="REST backend connecting transaction data, SLM generation, and customer chat.",
    version="1.0.0"
)

# Enable CORS so Person 4's Frontend can communicate without browser blocking
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fallback seed transactions in case Person 1 has not pushed yet
DEFAULT_TRANSACTIONS = [
    {
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
        "flag_rationale": "Transaction initiated from Lagos 45 minutes after physical card swipe in Bengaluru.",
        "status": "FLAGGED_SUSPICIOUS"
    },
    {
        "transaction_id": "TXN_10929",
        "account_id": "ACC_3301",
        "amount": 185000.00,
        "currency": "INR",
        "timestamp": "2026-10-28T03:15:00",
        "merchant": "Imperial Luxury Diamonds",
        "merchant_category": "Luxury Jewelry",
        "location": "Dubai, UAE",
        "cardholder_city": "Bengaluru, India",
        "anomaly_flag": "ERR_AMOUNT_SPIKE",
        "risk_score": 88,
        "flag_rationale": "Transaction amount is 8.5x higher than cardholder's 90-day average spending pattern.",
        "status": "FLAGGED_SUSPICIOUS"
    },
    {
        "transaction_id": "TXN_10930",
        "account_id": "ACC_5542",
        "amount": 49.00,
        "currency": "INR",
        "timestamp": "2026-10-28T04:02:11",
        "merchant": "MicroPlay Digital",
        "merchant_category": "Online Gaming",
        "location": "Bengaluru, India",
        "cardholder_city": "Bengaluru, India",
        "anomaly_flag": "ERR_CARD_TESTING",
        "risk_score": 82,
        "flag_rationale": "5 rapid micro-transactions executed within 40 seconds indicating automated card testing.",
        "status": "FLAGGED_SUSPICIOUS"
    }
]

# Pydantic Schemas
class ExplainRequest(BaseModel):
    transaction: dict
    persona: Optional[str] = "customer"

class ChatRequest(BaseModel):
    transaction: dict
    message: str
    history: Optional[List[Dict[str, str]]] = []

# API Endpoints
@app.get("/")
def health_check():
    return {"status": "online", "message": "Banking Anomaly Explainer API active"}

@app.get("/api/transactions")
def get_transactions():
    """Returns transactions list from data/transactions.json or default seed data."""
    data_file = ROOT_DIR / "data" / "transactions.json"
    if data_file.exists():
        try:
            with open(data_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_TRANSACTIONS

@app.post("/api/explain")
def explain_endpoint(req: ExplainRequest):
    """Generates human-readable, grounded explanation for customer or investigator."""
    try:
        res = generate_explanation(req.transaction, persona=req.persona)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """Handles multi-turn conversational follow-up questions."""
    try:
        reply = chat_with_agent(
            conversation_history=req.history,
            user_message=req.message,
            transaction_context=req.transaction
        )
        return {"response": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")