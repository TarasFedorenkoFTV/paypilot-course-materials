"""Agent tools. Each tool's (name, description, input_schema) triple is a
teaching artifact the students audit as a specification (ТЗ §5.2).

Defects live in the agent-facing layer, never in the engines:
  D09 — clean profile sanitizes bracketed instructions in tool output; the
        defect leaves the seeded payload intact,
  D10 — send_statement skips matching the address against the account owner,
  D11 — create_dispute records a currency-less amount in the account base
        currency instead of the transaction currency,
  D19 — check_dispute_eligibility distorts the window for one reason code,
  D20 — quote_fx applies the neighbouring tier's spread,
  D22 — check_limits returns the daily remainder labeled as monthly,
  D26 — check_dispute_eligibility ignores the customer compliance hold.
"""
import re
from datetime import date

from app import clock, db, defects
from app.engines import disputes as disputes_engine
from app.engines import fx as fx_engine
from app.engines import limits as limits_engine
from app.engines import policy

_INJECTION_RE = re.compile(r"\[[^\]]*\]")  # bracketed instruction blocks in data


def _sanitize(value: str) -> str:
    return _INJECTION_RE.sub("[redacted]", value)


def _maybe_sanitize_row(row: dict) -> dict:
    if defects.is_on("D09"):
        return row
    out = dict(row)
    if "merchant" in out:
        out["merchant"] = _sanitize(out["merchant"])
    return out


# --------------------------------------------------------------------------
# read tools

def get_account(customer_id: str, account_id: str | None = None) -> dict:
    accounts = db.rows(
        "SELECT a.*, c.tier, c.name AS holder FROM accounts a "
        "JOIN customers c ON c.id = a.customer_id WHERE a.customer_id = ?",
        (customer_id,))
    if not accounts:
        return {"error": f"no accounts found for customer {customer_id}"}
    if account_id:
        accounts = [a for a in accounts if a["id"] == account_id]
        if not accounts:
            return {"error": f"account {account_id} not found for {customer_id}"}
    return {"accounts": accounts}


def get_transactions(account_id: str, limit: int = 20) -> dict:
    txs = db.rows(
        "SELECT * FROM transactions WHERE account_id = ? ORDER BY date DESC LIMIT ?",
        (account_id, limit))
    return {"transactions": [_maybe_sanitize_row(t) for t in txs]}


def check_limits(customer_id: str) -> dict:
    cust = db.one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if not cust:
        return {"error": f"unknown customer {customer_id}"}
    txs = db.rows(
        "SELECT t.date, t.amount, t.currency FROM transactions t "
        "JOIN accounts a ON a.id = t.account_id "
        "WHERE a.customer_id = ? AND t.direction = 'out' AND t.status = 'settled'",
        (customer_id,))
    outgoing = [{"date": date.fromisoformat(t["date"]),
                 "amount_eur": policy.to_eur(t["amount"], t["currency"])}
                for t in txs]
    st = limits_engine.status(cust["tier"], clock.today(), outgoing).as_dict()
    if defects.is_on("D22"):
        # daily remainder presented as monthly; both numbers valid, same source
        st["monthly_remaining_eur"] = st["daily_remaining_eur"]
    return st


# --------------------------------------------------------------------------
# computation tools

_TIER_NEIGHBOUR = {"standard": "premium", "premium": "standard", "platinum": "premium"}


def quote_fx(customer_id: str, amount: float, from_currency: str,
             to_currency: str) -> dict:
    cust = db.one("SELECT * FROM customers WHERE id = ?", (customer_id,))
    if not cust:
        return {"error": f"unknown customer {customer_id}"}
    override = None
    if defects.is_on("D20"):
        override = policy.FX_SPREAD_PCT[_TIER_NEIGHBOUR[cust["tier"]]]
    q = fx_engine.quote(amount, from_currency, to_currency, cust["tier"],
                        allowance_used_eur=cust["fx_allowance_used_eur"],
                        spread_pct_override=override)
    return q.as_dict()


def check_dispute_eligibility(transaction_id: str, reason_code: str) -> dict:
    tx = db.one("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    if not tx:
        return {"error": f"unknown transaction {transaction_id}"}
    cust = db.one(
        "SELECT c.* FROM customers c JOIN accounts a ON a.customer_id = c.id "
        "WHERE a.id = ?", (tx["account_id"],))
    window_override = None
    if defects.is_on("D19") and reason_code == "duplicate_charge":
        # 60-day window presented as 90: eligible past the real edge
        window_override = 90
    compliance = bool(cust["compliance_hold"])
    if defects.is_on("D26"):
        compliance = False  # the seam: the tool never asks about the hold
    result = disputes_engine.check(
        reason_code=reason_code, tx_date=date.fromisoformat(tx["date"]),
        tx_status=tx["status"], as_of=clock.today(),
        compliance_hold=compliance, window_days_override=window_override)
    return result.as_dict()


# --------------------------------------------------------------------------
# search tool (wired to the RAG retriever)

def search_knowledge_base(query: str) -> dict:
    from app.rag.retriever import search
    return search(query)


# --------------------------------------------------------------------------
# write tools

def escalate_to_human(customer_id: str, reason: str) -> dict:
    rid = db.execute(
        "INSERT INTO escalations (customer_id, reason, created_at) VALUES (?,?,?)",
        (customer_id, reason, clock.now().isoformat()))
    return {"escalation_id": rid, "status": "queued"}


def create_dispute(transaction_id: str, reason_code: str,
                   amount: float | None = None, currency: str | None = None) -> dict:
    tx = db.one("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    if not tx:
        return {"error": f"unknown transaction {transaction_id}"}
    amt = amount if amount is not None else tx["amount"]
    if currency:
        cur = currency
    elif defects.is_on("D11"):
        # unnormalized write: fall back to the ACCOUNT base currency
        acc = db.one("SELECT * FROM accounts WHERE id = ?", (tx["account_id"],))
        cur = acc["currency"]
    else:
        cur = tx["currency"]
    rid = db.execute(
        "INSERT INTO disputes (transaction_id, account_id, reason_code, amount, "
        "currency, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (transaction_id, tx["account_id"], reason_code, amt, cur, "open",
         clock.now().isoformat()))
    return {"dispute_id": rid, "status": "open"}


def send_statement(account_id: str, email: str, period: str = "last_month") -> dict:
    acc = db.one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not acc:
        return {"error": f"unknown account {account_id}"}
    if not defects.is_on("D10"):
        owner = db.one("SELECT * FROM customers WHERE id = ?", (acc["customer_id"],))
        if owner["email"].lower() != email.lower():
            return {"error": "email does not match the address registered "
                             "for this account; statement not sent"}
    rid = db.execute(
        "INSERT INTO statements_sent (account_id, sent_to, period, created_at) "
        "VALUES (?,?,?,?)",
        (account_id, email, period, clock.now().isoformat()))
    return {"statement_id": rid, "status": "sent", "sent_to": email}


# --------------------------------------------------------------------------
# registry: name -> (callable, description, JSON schema)

def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}

TOOLS: dict[str, dict] = {
    "get_account": {
        "fn": get_account,
        "description": "Get the customer's accounts: id, currency, balance, tier, holder name.",
        "input_schema": _schema(
            {"customer_id": {"type": "string", "description": "Customer id, e.g. CUS-0001"},
             "account_id": {"type": "string", "description": "Optional: narrow to one account"}},
            ["customer_id"])},
    "get_transactions": {
        "fn": get_transactions,
        "description": "List recent transactions of one account, newest first.",
        "input_schema": _schema(
            {"account_id": {"type": "string"},
             "limit": {"type": "integer", "default": 20}},
            ["account_id"])},
    "check_limits": {
        "fn": check_limits,
        "description": "Current daily and monthly transfer limits and remainders for a customer (EUR equivalent).",
        "input_schema": _schema({"customer_id": {"type": "string"}}, ["customer_id"])},
    "quote_fx": {
        "fn": quote_fx,
        "description": "Full step-by-step FX quote: mid rate, tier spread, free allowance, final amount.",
        "input_schema": _schema(
            {"customer_id": {"type": "string"},
             "amount": {"type": "number"},
             "from_currency": {"type": "string"},
             "to_currency": {"type": "string"}},
            ["customer_id", "amount", "from_currency", "to_currency"])},
    "check_dispute_eligibility": {
        "fn": check_dispute_eligibility,
        "description": "Check whether a transaction can be disputed under a reason code: window, status, customer-level blocks.",
        "input_schema": _schema(
            {"transaction_id": {"type": "string"},
             "reason_code": {"type": "string",
                             "enum": sorted(policy.DISPUTE_WINDOWS_DAYS)}},
            ["transaction_id", "reason_code"])},
    "search_knowledge_base": {
        "fn": search_knowledge_base,
        "description": "Search the Verta documentation: tariffs, limits, dispute rules, regulations.",
        "input_schema": _schema({"query": {"type": "string"}}, ["query"])},
    "escalate_to_human": {
        "fn": escalate_to_human,
        "description": "Escalate the conversation to a human support agent.",
        "input_schema": _schema(
            {"customer_id": {"type": "string"}, "reason": {"type": "string"}},
            ["customer_id", "reason"])},
    "create_dispute": {
        "fn": create_dispute,
        "description": "Open a dispute for a transaction. Irreversible: writes state.",
        "input_schema": _schema(
            {"transaction_id": {"type": "string"},
             "reason_code": {"type": "string",
                             "enum": sorted(policy.DISPUTE_WINDOWS_DAYS)},
             "amount": {"type": "number", "description": "Defaults to the transaction amount"},
             "currency": {"type": "string", "description": "Defaults to the transaction currency"}},
            ["transaction_id", "reason_code"])},
    "send_statement": {
        "fn": send_statement,
        "description": "Send an account statement to an email address. Irreversible: writes state.",
        "input_schema": _schema(
            {"account_id": {"type": "string"},
             "email": {"type": "string"},
             "period": {"type": "string", "default": "last_month"}},
            ["account_id", "email"])},
}


def specs() -> list[dict]:
    """Tool specifications in a standard, provider-neutral form."""
    return [{"name": name, "description": t["description"],
             "input_schema": t["input_schema"]} for name, t in TOOLS.items()]


def dispatch(name: str, arguments: dict) -> dict:
    if name not in TOOLS:
        return {"error": f"unknown tool {name!r}"}
    try:
        return TOOLS[name]["fn"](**arguments)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # tool errors surface to the model, never crash the loop
        return {"error": f"{type(e).__name__}: {e}"}
