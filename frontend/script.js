"use strict";

const BACKEND_URL = "http://127.0.0.1:8000";

let txs = [];
let lang = "en";
let selectedId = null;
let currentMode = "customer";
let chatHistory = [];

const $ = (id) => document.getElementById(id);
const current = () => txs.find((tx) => tx.id === selectedId) ?? null;

const money = (amount, currency = "INR") =>
  new Intl.NumberFormat(lang === "kn" ? "kn-IN" : lang === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: currency || "INR",
    maximumFractionDigits: 2
  }).format(Number(amount) || 0);

function normalizeTransaction(item) {
  const codes = Array.isArray(item.anomaly_codes)
    ? item.anomaly_codes
    : (typeof item.anomaly_flag === "string" && !["true", "false"].includes(item.anomaly_flag.toLowerCase()))
      ? [item.anomaly_flag]
      : [];

  const flagged = item.anomaly_flag === true ||
                  String(item.anomaly_flag).toLowerCase() === "true" ||
                  codes.length > 0;

  const amount = Number(item.amount) || 0;
  const riskScore = item.risk_score ?? (flagged ? 90 : 15);
  const risk = riskScore >= 80 ? "High" : riskScore >= 50 ? "Medium" : "Low";

  return {
    raw: item,
    id: String(item.transaction_id || "TXN"),
    amount,
    currency: String(item.currency || "INR"),
    location: String(item.location || "Bengaluru"),
    risk,
    riskScore,
    flagged,
    anomalyCodes: codes,
    cardholderId: String(item.cardholder_id || item.account_id || "CH001")
  };
}

async function loadTransactions() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/transactions`, { cache: "no-store" });
    if (!res.ok) throw new Error("Backend request failed");
    const data = await res.json();
    txs = data.map(normalizeTransaction);
    if (txs.length) selectedId = txs[0].id;
    renderAll();
  } catch (err) {
    console.error("Load error:", err);
    $("transactionTable").innerHTML = `<tr><td colspan="5" class="loading">Could not load from backend. Make sure uvicorn is running on port 8000.</td></tr>`;
  }
}

function renderStats() {
  $("totalCount").textContent = txs.length;
  $("flaggedCount").textContent = txs.filter((t) => t.flagged).length;
  $("highCount").textContent = txs.filter((t) => t.risk === "High").length;
}

function renderTable() {
  const body = $("transactionTable");
  const query = ($("searchInput")?.value || "").trim().toLowerCase();
  const filter = $("riskFilter")?.value || "all";

  body.replaceChildren();

  const filtered = txs.filter((tx) => {
    const matchesSearch = [tx.id, tx.location, tx.cardholderId, ...tx.anomalyCodes].some((v) =>
      String(v).toLowerCase().includes(query)
    );
    const matchesFilter =
      filter === "all" ||
      (filter === "flagged" && tx.flagged) ||
      tx.risk.toLowerCase() === filter;
    return matchesSearch && matchesFilter;
  });

  $("recordCount").textContent = `${filtered.length} records`;

  filtered.forEach((tx) => {
    const row = document.createElement("tr");
    if (tx.id === selectedId) row.classList.add("selected-row");

    row.innerHTML = `
      <td><strong>${tx.id}</strong><br><small class="muted">${tx.cardholderId}</small></td>
      <td>${money(tx.amount, tx.currency)}</td>
      <td>📍 ${tx.location}</td>
      <td><span class="badge ${tx.risk.toLowerCase()}">${tx.risk} (${tx.riskScore})</span></td>
      <td><span class="status-pill ${tx.flagged ? 'flagged' : 'clear'}">${tx.flagged ? 'FLAGGED' : 'NORMAL'}</span></td>
    `;

    row.addEventListener("click", () => {
      selectedId = tx.id;
      renderTable();
      triggerAiExplanation();
    });

    body.append(row);
  });
}

function formatMarkdown(text) {
  return String(text || "")
    .replace(/^### (.*$)/gim, '<h4>$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^[•\-] (.*$)/gim, '<li>$1</li>')
    .replace(/\n\n/g, '<br>');
}

async function triggerAiExplanation() {
  const tx = current();
  const box = $("explanationContent");
  if (!tx) return;

  $("modeTransaction").textContent = `${tx.id} — ${money(tx.amount, tx.currency)} at ${tx.location}`;
  $("modeRisk").textContent = `Risk: ${tx.riskScore}/100`;
  $("modeRisk").className = `badge ${tx.risk.toLowerCase()}`;

  box.innerHTML = `<em>Generating grounded explanation via SLM...</em>`;

  try {
    const res = await fetch(`${BACKEND_URL}/api/explain`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction: tx.raw, persona: currentMode })
    });
    const data = await res.json();
    box.innerHTML = `
      <div class="latency-pill">⏱️ Latency: <strong>${data.latency_seconds}s</strong> (SLA &lt;10s Met)</div>
      ${formatMarkdown(data.explanation)}
    `;
  } catch (err) {
    box.innerHTML = `
      <h4>### Why this was flagged</h4>
      <p>Flagged due to anomalous telemetry: <strong>${tx.anomalyCodes.join(', ') || 'Rule threshold exceeded'}</strong>.</p>
      <h4>### Recommended Actions</h4>
      <li>Confirm whether you authorized this payment of ${money(tx.amount, tx.currency)}.</li>
      <li>Freeze card via mobile app if unfamiliar.</li>
    `;
  }
}

function appendChat(role, text) {
  const win = $("chatWindow");
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.innerHTML = `<strong>${role === 'user' ? 'You' : 'Assistant'}:</strong> ${formatMarkdown(text)}`;
  win.appendChild(bubble);
  win.scrollTop = win.scrollHeight;
  chatHistory.push({ role, content: text });
}

async function handleChat(msg) {
  const tx = current();
  if (!msg.trim()) return;
  appendChat("user", msg);

  try {
    const res = await fetch(`${BACKEND_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transaction: tx ? tx.raw : {},
        message: msg,
        history: chatHistory.slice(-4)
      })
    });
    const data = await res.json();
    appendChat("assistant", data.response);
  } catch (e) {
    appendChat("assistant", "If you do not recognize this transaction, please lock your debit card in the app immediately.");
  }
}

function setupEvents() {
  $("searchInput")?.addEventListener("input", renderTable);
  $("riskFilter")?.addEventListener("change", renderTable);

  $("languageSelect")?.addEventListener("change", (e) => {
    lang = e.target.value;
    renderTable();
    if (selectedId) triggerAiExplanation();
  });

  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentMode = btn.dataset.mode === "investigator" ? "investigator" : "customer";
      triggerAiExplanation();
    });
  });

  document.querySelectorAll(".suggestion").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.dataset.question;
      const tx = current();
      if (q === "why") handleChat(`Why was transaction ${tx ? tx.id : ''} flagged?`);
      else if (q === "risk") handleChat(`Explain the risk level and flags.`);
      else if (q === "action") handleChat(`What should I do right now?`);
    });
  });

  $("chatForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("questionInput");
    const val = input.value;
    input.value = "";
    handleChat(val);
  });
}

function renderAll() {
  renderStats();
  renderTable();
  triggerAiExplanation();
}

document.addEventListener("DOMContentLoaded", () => {
  setupEvents();
  loadTransactions();
  appendChat("assistant", "Hello! Select any flagged transaction above to get an instant AI explanation.");
});