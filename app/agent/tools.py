"""Tool definitions for the compliance research agent.

Each tool is a callable + a JSON schema describing its interface.
Schemas follow the format both Anthropic and OpenAI accept (with minor adapter logic).
"""
from __future__ import annotations

from typing import Any, Callable

from app.rag import retrieve

# ---------------------------------------------------------------------------
# Tool 1: search the EU AI Act corpus (RAG retrieval, no generation)
# ---------------------------------------------------------------------------
def search_ai_act(query: str, k: int = 5) -> dict[str, Any]:
    """Semantic search over the EU AI Act. Returns chunks, not an answer."""
    chunks = retrieve(query, k=k)
    return {
        "results": [
            {"text": c.text, "source": c.source, "distance": round(c.distance, 4)}
            for c in chunks
        ]
    }


SEARCH_SCHEMA = {
    "name": "search_ai_act",
    "description": (
        "Semantic search over the EU AI Act regulation text. "
        "Use when you need to find passages on a topic. Returns raw chunks, not an answer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query."},
            "k": {"type": "integer", "description": "Number of chunks to return.", "default": 5},
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Tool 2: look up a specific Article number
# ---------------------------------------------------------------------------
def lookup_article(article_number: int) -> dict[str, Any]:
    """Fetch chunks that mention a specific Article number."""
    if article_number < 1 or article_number > 113:
        return {"error": f"Article {article_number} does not exist. Valid range: 1-113."}
    chunks = retrieve(f"Article {article_number}", k=3)
    return {
        "article": article_number,
        "passages": [{"text": c.text, "source": c.source} for c in chunks],
    }


LOOKUP_SCHEMA = {
    "name": "lookup_article",
    "description": (
        "Look up a specific Article by number (1-113). "
        "Returns passages that reference that Article."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "article_number": {"type": "integer", "description": "Article number, 1-113."},
        },
        "required": ["article_number"],
    },
}


# ---------------------------------------------------------------------------
# Tool 3: classify a use case into a risk tier
# ---------------------------------------------------------------------------
RISK_TIERS = {
    "unacceptable": [
        "social scoring",
        "subliminal manipulation",
        "real-time biometric identification",
        "emotion recognition in workplace",
        "emotion recognition in school",
        "predictive policing based on profiling",
        "untargeted facial scraping",
        "biometric categorisation of sensitive attributes",
    ],
    "high": [
        "biometric identification",
        "critical infrastructure",
        "education access",
        "employment screening",
        "hiring",
        "credit scoring",
        "law enforcement",
        "migration",
        "judicial",
        "medical device",
        "safety component",
    ],
    "limited": ["chatbot", "deepfake", "generative", "ai-generated content"],
    "minimal": ["spam filter", "video game", "inventory", "search ranking"],
}


def check_risk_tier(use_case: str) -> dict[str, Any]:
    """Heuristically classify a use case into a risk tier under the EU AI Act."""
    text = use_case.lower()
    matches = {tier: [k for k in keywords if k in text] for tier, keywords in RISK_TIERS.items()}
    matches = {t: m for t, m in matches.items() if m}
    if not matches:
        return {
            "tier": "unknown",
            "rationale": "No keyword match. Consult Annex III and Article 6 manually.",
            "use_case": use_case,
        }
    # Pick most-restrictive tier that matched
    order = ["unacceptable", "high", "limited", "minimal"]
    tier = next(t for t in order if t in matches)
    return {
        "tier": tier,
        "matched_keywords": matches[tier],
        "use_case": use_case,
        "note": "Heuristic classification. Verify against Annex III for high-risk cases.",
    }


RISK_TIER_SCHEMA = {
    "name": "check_risk_tier",
    "description": (
        "Classify an AI use case into one of four EU AI Act risk tiers: "
        "unacceptable, high, limited, minimal. Heuristic, requires verification."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "use_case": {"type": "string", "description": "Description of the AI use case."},
        },
        "required": ["use_case"],
    },
}


# ---------------------------------------------------------------------------
# Tool 4: compute max fine for a violation
# ---------------------------------------------------------------------------
FINE_TABLE = {
    "prohibited_practices": {"amount_eur": 35_000_000, "turnover_pct": 7.0, "article": 99},
    "high_risk_non_compliance": {"amount_eur": 15_000_000, "turnover_pct": 3.0, "article": 99},
    "incorrect_information": {"amount_eur": 7_500_000, "turnover_pct": 1.0, "article": 99},
    "gpai_non_compliance": {"amount_eur": 15_000_000, "turnover_pct": 3.0, "article": 101},
}


def compute_fine(violation_type: str, annual_turnover_eur: float | None = None) -> dict[str, Any]:
    """Compute the maximum fine for a violation type. Uses higher of fixed amount or %."""
    if violation_type not in FINE_TABLE:
        return {
            "error": f"Unknown violation_type. Valid: {list(FINE_TABLE.keys())}",
        }
    row = FINE_TABLE[violation_type]
    fixed = row["amount_eur"]
    pct_amount = (annual_turnover_eur or 0) * row["turnover_pct"] / 100.0
    max_fine = max(fixed, pct_amount)
    return {
        "violation_type": violation_type,
        "fixed_cap_eur": fixed,
        "turnover_pct": row["turnover_pct"],
        "computed_pct_amount_eur": pct_amount,
        "max_fine_eur": max_fine,
        "article": row["article"],
    }


COMPUTE_FINE_SCHEMA = {
    "name": "compute_fine",
    "description": (
        "Compute the maximum administrative fine for an EU AI Act violation. "
        "Valid violation_type values: prohibited_practices, high_risk_non_compliance, "
        "incorrect_information, gpai_non_compliance. annual_turnover_eur is optional."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "violation_type": {
                "type": "string",
                "enum": list(FINE_TABLE.keys()),
            },
            "annual_turnover_eur": {
                "type": "number",
                "description": "Company annual worldwide turnover in EUR (optional).",
            },
        },
        "required": ["violation_type"],
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
TOOLS: dict[str, dict[str, Any]] = {
    "search_ai_act": {"fn": search_ai_act, "schema": SEARCH_SCHEMA},
    "lookup_article": {"fn": lookup_article, "schema": LOOKUP_SCHEMA},
    "check_risk_tier": {"fn": check_risk_tier, "schema": RISK_TIER_SCHEMA},
    "compute_fine": {"fn": compute_fine, "schema": COMPUTE_FINE_SCHEMA},
}


def get_tool_schemas() -> list[dict[str, Any]]:
    return [t["schema"] for t in TOOLS.values()]


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name. Raises KeyError if hallucinated."""
    if name not in TOOLS:
        raise KeyError(f"Hallucinated tool: '{name}'. Available: {list(TOOLS.keys())}")
    fn: Callable = TOOLS[name]["fn"]
    return fn(**arguments)
