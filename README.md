# TCS-HK
# FraudLens AI — Transaction Anomaly Intelligence

FraudLens AI connects real-time banking telemetry with lightweight Generative AI and SLMs (Small Language Models) to deliver grounded, human-readable explanations and multi-turn support for suspicious financial transactions.

## Architecture
- **AI Engine (`ai_engine/`):** Generates structured explanations using local SLMs (via Ollama) or Google Gemini API.
- **Backend (`backend/`):** FastAPI REST server serving transaction feeds, explanations, and conversation sessions.
- **Data Generator (`data/`):** Synthetic banking telemetry generator modeling geo-velocity, spending spikes, and card testing.
- **Frontend (`frontend/`):** Responsive dashboard with customer/investigator mode toggles and an AI inquiry chatbot.

## Quickstart

### 1. Generate Transactions
```bash
python data/dataset.py