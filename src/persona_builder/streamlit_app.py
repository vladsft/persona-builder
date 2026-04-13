import hashlib
import json
import os
import random
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from . import llm_client
from .paths import DEFAULT_OUTPUT_DIR, REPO_ROOT
from .persona_prompt import SYSTEM_PROMPT
from .retrieval import build_bm25_index, format_context_block, load_corpus, retrieve

# ---------------------------------------------------------------------------
# A/B model variants — each entry is (provider, model_id)
# ---------------------------------------------------------------------------

_ALL_AB_VARIANTS: list[tuple[str, str]] = [
    ("anthropic", "claude-sonnet-4-6"),
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("deepseek", "deepseek-chat"),
    ("gemini", "gemini-2.5-flash"),
]

DEFAULT_TOP_K = 5
DEFAULT_MAX_TOKENS = 600
MAX_VERBATIM_MESSAGES = 6  # 3 user+assistant exchanges kept verbatim
RATE_LIMIT_MESSAGES = 8
DOTENV_PATH = REPO_ROOT / ".env"
LOGS_DIR = REPO_ROOT / "data" / "logs"


def _load_dotenv() -> None:
    if not DOTENV_PATH.exists():
        return

    for line in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _get_secret_or_env(name: str, default: str | None = None) -> str | None:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)


def _get_int_setting(name: str, default: int) -> int:
    raw_value = _get_secret_or_env(name, str(default))
    try:
        return int(raw_value) if raw_value is not None else default
    except (TypeError, ValueError):
        return default


def get_runtime_config() -> dict[str, object]:
    return {
        "top_k": _get_int_setting("TOP_K", DEFAULT_TOP_K),
        "max_tokens": _get_int_setting("MAX_TOKENS", DEFAULT_MAX_TOKENS),
        "output_dir": str(DEFAULT_OUTPUT_DIR),
    }


def validate_startup(config: dict[str, object]) -> list[str]:
    errors = []
    output_dir = Path(str(config["output_dir"]))

    if not output_dir.exists():
        errors.append(f"Directorul de corpus nu există: `{output_dir}`.")
    elif not list(output_dir.glob("*.json")):
        errors.append(f"Directorul `{output_dir}` nu conține fișiere JSON procesate.")

    return errors


@st.cache_resource
def get_index(output_dir: str):
    corpus = load_corpus(output_dir)
    bm25 = build_bm25_index(corpus)
    return bm25, corpus


def build_augmented_user_message(user_input: str, hits: list[dict]) -> str:
    context_block = format_context_block(hits)
    return (
        "[CONTEXT DIN EMISIUNILE LUI BANCIU]\n"
        f"{context_block}\n\n"
        "[INSTRUCȚIUNE]\n"
        "Răspunde doar dacă ai o poziție coerentă din personaj sau din context. "
        "Nu cita textual fragmentele; integrează-le natural în voce.\n\n"
        f"ÎNTREBAREA / SUBIECTUL:\n{user_input}"
    )


def _summarize_exchange(user_msg: str, assistant_msg: str) -> str:
    """Compress one user/assistant exchange into a compact line."""
    user_words = user_msg.split()
    user_short = " ".join(user_words[:30])
    if len(user_words) > 30:
        user_short += "…"
    # First paragraph of assistant, capped
    assistant_short = assistant_msg.split("\n")[0][:200]
    return f"- Utilizator: {user_short}\n  Banciu: {assistant_short}"


def _maybe_compress_history() -> None:
    """Move oldest exchanges into a rolling summary when history grows too long."""
    messages = st.session_state.messages
    if len(messages) <= MAX_VERBATIM_MESSAGES:
        return

    if "conversation_summary" not in st.session_state:
        st.session_state.conversation_summary = ""

    while len(messages) > MAX_VERBATIM_MESSAGES:
        if len(messages) < 2:
            break
        oldest = messages[0]
        second = messages[1]
        if oldest["role"] == "user" and second["role"] == "assistant":
            summary_line = _summarize_exchange(oldest["content"], second["content"])
            st.session_state.conversation_summary += summary_line + "\n"
            messages.pop(0)
            messages.pop(0)
        else:
            break


def build_api_messages(
    history: list[dict],
    augmented_user_message: str,
    conversation_summary: str = "",
) -> list[dict[str, str]]:
    api_messages = []
    if conversation_summary.strip():
        api_messages.append({
            "role": "user",
            "content": (
                "[CONTEXT DIN CONVERSAȚIA ANTERIOARĂ]\n"
                + conversation_summary.strip()
            ),
        })
        api_messages.append({
            "role": "assistant",
            "content": "Da, am în vedere ce am discutat.",
        })
    for msg in history:
        if msg["role"] in {"user", "assistant"}:
            api_messages.append({"role": msg["role"], "content": msg["content"]})
    api_messages.append({"role": "user", "content": augmented_user_message})
    return api_messages


# ---------------------------------------------------------------------------
# A/B model assignment
# ---------------------------------------------------------------------------

def _try_start_session() -> tuple[bool, str]:
    """Gate new sessions through IP + global rate limits.

    Returns (allowed, block_reason).  Already-registered sessions always pass.
    Only active in web deployments.
    """
    if "session_registered" in st.session_state:
        return True, "ok"

    if not _is_web_deployment():
        # Local dev: skip rate checks, just register
        st.session_state.session_registered = True
        return True, "ok"

    ip_hash = _get_client_ip_hash()
    max_per_ip = _get_int_setting("MAX_SESSIONS_PER_IP", 3)
    daily_cap = _get_int_setting("DAILY_SESSION_CAP", 300)

    store = _get_rate_store()
    allowed, reason = store.check_and_register(ip_hash, max_per_ip, daily_cap)

    if allowed:
        st.session_state.session_registered = True
        st.session_state.ip_hash = ip_hash
        st.session_state.fingerprint = _get_header_fingerprint()

    return allowed, reason


def _get_available_variants() -> list[tuple[str, str]]:
    """Filter A/B variants to only those with a configured API key."""
    available = []
    for provider, model in _ALL_AB_VARIANTS:
        key_var = llm_client._PROVIDER_KEY_MAP.get(provider)
        if key_var and _get_secret_or_env(key_var):
            available.append((provider, model))
    return available


def _assign_ab_variant() -> tuple[str, str]:
    """Randomly assign a (provider, model) pair for this session.

    Only picks from providers with configured API keys.  The assignment is
    stored in session_state so it persists for the entire session.
    Returns (provider, model).
    """
    if "ab_provider" not in st.session_state:
        variants = _get_available_variants()
        if not variants:
            st.error(
                "Nicio cheie API configurată. Setează cel puțin una din: "
                "ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY."
            )
            st.stop()
        provider, model = random.choice(variants)
        st.session_state.ab_provider = provider
        st.session_state.ab_model = model
        st.session_state.session_id = str(uuid.uuid4())
        _log_session_start(provider, model)
    return st.session_state.ab_provider, st.session_state.ab_model


def _log_session_start(provider: str, model: str) -> None:
    """Append a session-start event to the A/B log file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": "session_start",
        "session_id": st.session_state.session_id,
        "provider": provider,
        "model": model,
        "ip_hash": st.session_state.get("ip_hash", ""),
        "fingerprint": st.session_state.get("fingerprint", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(LOGS_DIR / "ab_sessions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def _is_web_deployment() -> bool:
    """True when running on Streamlit Cloud (rate limits + no sources)."""
    return _get_secret_or_env("DEPLOYMENT", "local") == "web"


# --- Shared rate-limit store (singleton across all Streamlit sessions) ---

class RateLimitStore:
    """Thread-safe in-memory store for IP and global session rate limits.

    Survives across Streamlit sessions within the same process.  Resets on
    deploy/restart, which is acceptable for a short demo.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # ip_hash -> list of session-start timestamps
        self._ip_sessions: dict[str, list[float]] = {}
        # all session-start timestamps (for global daily cap)
        self._global_sessions: list[float] = []

    def _prune(self, timestamps: list[float], window: float = 86400) -> list[float]:
        cutoff = time.time() - window
        return [t for t in timestamps if t > cutoff]

    def check_and_register(
        self,
        ip_hash: str,
        max_per_ip: int,
        daily_cap: int,
    ) -> tuple[bool, str]:
        """Try to register a new session.  Returns (allowed, reason)."""
        with self._lock:
            now = time.time()

            # Prune old entries
            self._global_sessions = self._prune(self._global_sessions)

            # Global daily cap
            if len(self._global_sessions) >= daily_cap:
                return False, "daily_cap"

            # Per-IP limit
            ip_list = self._prune(self._ip_sessions.get(ip_hash, []))
            self._ip_sessions[ip_hash] = ip_list
            if len(ip_list) >= max_per_ip:
                return False, "ip_limit"

            # Register
            ip_list.append(now)
            self._ip_sessions[ip_hash] = ip_list
            self._global_sessions.append(now)
            return True, "ok"

    @property
    def active_today(self) -> int:
        with self._lock:
            self._global_sessions = self._prune(self._global_sessions)
            return len(self._global_sessions)


@st.cache_resource
def _get_rate_store() -> RateLimitStore:
    return RateLimitStore()


# --- Client identification helpers ---

def _get_client_ip_hash() -> str:
    """Hash the client IP for rate limiting (privacy-preserving)."""
    try:
        headers = st.context.headers
        forwarded = headers.get("X-Forwarded-For", "")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = headers.get("Remote-Addr", "unknown")
    except Exception:
        ip = "unknown"
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _get_header_fingerprint() -> str:
    """Simple browser fingerprint from HTTP headers (secondary signal)."""
    try:
        headers = st.context.headers
        parts = [
            headers.get("User-Agent", ""),
            headers.get("Accept-Language", ""),
            headers.get("Sec-Ch-Ua-Platform", ""),
        ]
    except Exception:
        parts = ["unknown"]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# --- Per-session message limit (8 messages hard cap) ---

def _init_rate_limit() -> None:
    if "rate_limit_count" not in st.session_state:
        st.session_state.rate_limit_count = 0


def _check_message_limit() -> bool:
    """Return True if the user can still send messages in this session."""
    if not _is_web_deployment():
        return True
    _init_rate_limit()
    return st.session_state.rate_limit_count < RATE_LIMIT_MESSAGES


def _increment_message_count() -> None:
    if not _is_web_deployment():
        return
    _init_rate_limit()
    st.session_state.rate_limit_count += 1


def _remaining_messages() -> int | None:
    if not _is_web_deployment():
        return None
    _init_rate_limit()
    return max(0, RATE_LIMIT_MESSAGES - st.session_state.rate_limit_count)


def _render_sources(hits: list[dict]) -> None:
    """Show retrieval sources — only in local mode."""
    if _is_web_deployment() or not hits:
        return

    with st.expander("Surse folosite", expanded=False):
        for hit in hits:
            excerpt = hit["text"][:280].strip()
            if len(hit["text"]) > 280:
                excerpt += "..."
            st.markdown(
                f"**{hit['title']}**  \n"
                f"{hit['date']} | [YouTube]({hit['youtube_url']}) | fragment #{hit['chunk_index']} | scor {hit['score']:.2f}"
            )
            st.write(excerpt)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "fotbal": [
        "fotbal", "meci", "echip", "gol", "jucator", "jucător", "antrenor",
        "liga", "campionat", "national", "național", "hagi", "lucescu",
        "steaua", "dinamo", "rapid", "fcsb", "cfr", "champions", "europa",
        "transfer", "arbitr", "penalty", "corner", "offside", "var",
        "mondial", "euro 20", "premier league", "ligue", "serie a",
        "marseille", "om ", "psg", "barcelona", "real madrid", "becali",
    ],
    "politica": [
        "politic", "guvern", "parlament", "președint", "presedint",
        "ministr", "partid", "aleger", "vot", "psd", "pnl", "usr",
        "aur", "iohannis", "ciolacu", "lasconi", "georgescu", "corupt",
        "democrat", "senat", "deputat", "primari", "primar", "lege",
    ],
    "personal": [
        "viata", "viață", "copil", "familie", "scoal", "școal",
        "universitat", "facultat", "banciu", "emisiune", "cariera",
        "carieră", "eurosport", "b1", "naum", "tolontan",
    ],
}


def _detect_topics(text: str) -> list[str]:
    """Simple keyword-based topic tagging."""
    lower = text.lower()
    found = [
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(kw in lower for kw in keywords)
    ]
    return found or ["altele"]


def _log_message_event(
    user_input: str, response_text: str, message_number: int
) -> None:
    """Append a message-level analytics event."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": "message",
        "session_id": st.session_state.get("session_id", ""),
        "ip_hash": st.session_state.get("ip_hash", ""),
        "fingerprint": st.session_state.get("fingerprint", ""),
        "provider": st.session_state.get("ab_provider", ""),
        "model": st.session_state.get("ab_model", ""),
        "message_number": message_number,
        "topics": _detect_topics(user_input),
        "user_input_length": len(user_input),
        "response_length": len(response_text),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(LOGS_DIR / "analytics.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

def _is_killed() -> bool:
    """Return True if the KILL_SWITCH env var is set to disable the app."""
    return (_get_secret_or_env("KILL_SWITCH", "0") or "0").strip().lower() in (
        "1", "true", "yes",
    )


# ---------------------------------------------------------------------------
# Content filter
# ---------------------------------------------------------------------------

import re as _re

# Hard-block patterns: slurs, explicit violence calls, graphic content.
# Banciu is provocative, so we only block the truly harmful stuff.
_BLOCK_PATTERNS: list[_re.Pattern[str]] = [
    # Ethnic/racial slurs (Romanian)
    _re.compile(
        r"\b(țigan[ei]? .*(?:trebuie|merita|ar trebui).*(?:omorâ|batu|distru|elimina))",
        _re.IGNORECASE,
    ),
    # Explicit calls to violence against named individuals
    _re.compile(
        r"(?:trebuie|ar trebui|merită)\s+(?:să\s+)?(?:fie\s+)?(?:omorât|ucis|împușcat|spânzurat|bătut)",
        _re.IGNORECASE,
    ),
    # Fabricated criminal accusations with certainty
    _re.compile(
        r"(?:a\s+(?:violat|ucis|omorât|abuzat sexual))\s+(?:pe|un|o)\b",
        _re.IGNORECASE,
    ),
    # Doxxing patterns (phone, address)
    _re.compile(r"\b(?:adresa|domiciliul|telefonul|numarul)\s+(?:lui|ei|lor)\b.*\d", _re.IGNORECASE),
]


def _check_content(text: str) -> tuple[bool, str]:
    """Check if response text should be blocked.

    Returns (is_safe, matched_pattern_description).
    Tolerant of strong opinions and criticism of public figures.
    Only blocks genuinely harmful content.
    """
    for pattern in _BLOCK_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, match.group(0)[:100]
    return True, ""


def _log_flagged_output(response_text: str, reason: str) -> None:
    """Log a blocked/flagged response for manual review."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": "flagged_output",
        "session_id": st.session_state.get("session_id", ""),
        "provider": st.session_state.get("ab_provider", ""),
        "model": st.session_state.get("ab_model", ""),
        "reason": reason,
        "response_preview": response_text[:500],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(LOGS_DIR / "flagged_outputs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


_BLOCKED_RESPONSE = (
    "Hmm, am vrut să spun ceva, dar mai bine nu. "
    "Hai să trecem la alt subiect."
)


# ---------------------------------------------------------------------------
# Post-session poll
# ---------------------------------------------------------------------------

_POLL_OPTIONS = [
    "Mircea Badea",
    "CTP",
    "Mircea Lucescu",
    "Nu, mulțumesc",
]


def _show_post_session_poll() -> None:
    """Show Persona Museum validation poll after the session ends."""
    st.divider()
    st.markdown("**Ai vrea să vorbești și cu alte personaje AI?**")
    choice = st.radio(
        "Alege un personaj:",
        _POLL_OPTIONS,
        index=None,
        key="poll_choice",
        label_visibility="collapsed",
    )
    if choice is not None:
        if st.button("Trimite", key="poll_submit"):
            st.session_state.poll_submitted = True
            _log_poll_result(choice)
            st.success("Mulțumim pentru feedback!")
            st.rerun()


def _log_poll_result(choice: str) -> None:
    """Log poll response to a separate file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": "poll",
        "session_id": st.session_state.get("session_id", ""),
        "ip_hash": st.session_state.get("ip_hash", ""),
        "fingerprint": st.session_state.get("fingerprint", ""),
        "provider": st.session_state.get("ab_provider", ""),
        "model": st.session_state.get("ab_model", ""),
        "choice": choice,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(LOGS_DIR / "poll_results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def run() -> None:
    _load_dotenv()

    st.set_page_config(
        page_title="Prea Mult Banciu",
        page_icon="📺",
        layout="centered",
    )

    # Kill switch — instant disable
    if _is_killed():
        st.warning("Serviciul este temporar indisponibil. Reveniți mai târziu.")
        st.stop()

    # Mobile-first CSS
    st.markdown(
        """<style>
        /* Wider chat area on mobile */
        .block-container { max-width: 100% !important; padding: 1rem !important; }
        @media (min-width: 768px) {
            .block-container { max-width: 700px !important; padding: 2rem 1rem !important; }
        }
        /* Readable chat text on small screens */
        .stChatMessage { font-size: 1rem; line-height: 1.5; }
        /* Disclaimer styling */
        .disclaimer-box {
            background: #fff3cd; color: #856404; border: 1px solid #ffc107;
            border-radius: 6px; padding: 0.5rem 0.75rem; margin-bottom: 0.75rem;
            font-size: 0.85rem; text-align: center;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    st.title("Prea Mult Banciu")
    # Disclaimer
    st.markdown(
        '<div class="disclaimer-box">'
        "Aceasta este o simulare AI. Nu este Radu Banciu."
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("AI replica experimentală bazată pe emisiunile lui Radu Banciu. Proiect neoficial de fan, fără scop comercial.")

    # --- Session-level rate limit (IP + global daily cap) ---
    session_allowed, block_reason = _try_start_session()
    if not session_allowed:
        if block_reason == "daily_cap":
            st.warning("Banciu s-a dus la culcare, revino mâine.")
        else:
            st.warning("Ai deschis prea multe conversații azi. Revino mâine.")
        st.stop()

    config = get_runtime_config()
    startup_errors = validate_startup(config)

    if startup_errors:
        for error in startup_errors:
            st.error(error)
        st.stop()

    bm25, corpus = get_index(str(config["output_dir"]))

    if not corpus:
        st.error("Corpusul este gol după încărcare. Regenerază fișierele din `data/output/`.")
        st.stop()

    # Assign A/B model variant for this session
    provider, model = _assign_ab_variant()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Show remaining messages in sidebar (web only)
    remaining = _remaining_messages()
    if remaining is not None:
        st.sidebar.markdown(f"**Mesaje rămase:** {remaining}/{RATE_LIMIT_MESSAGES}")
        if remaining == 0:
            st.sidebar.warning("Ai folosit toate cele 8 mesaje din această sesiune.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant":
                _render_sources(msg.get("sources", []))

    # --- Post-session poll (after all messages used) ---
    if remaining == 0 and not st.session_state.get("poll_submitted"):
        _show_post_session_poll()

    user_input = st.chat_input(
        "Spune ceva...",
        disabled=remaining == 0 if remaining is not None else False,
    )

    if user_input:
        if not _check_message_limit():
            st.error(f"Ai atins limita de {RATE_LIMIT_MESSAGES} mesaje pe sesiune.")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        hits = retrieve(user_input, bm25, corpus, top_k=int(config["top_k"]))
        augmented_user_message = build_augmented_user_message(user_input, hits)
        summary = st.session_state.get("conversation_summary", "")
        api_messages = build_api_messages(st.session_state.messages[:-1], augmented_user_message, summary)

        with st.chat_message("assistant"):
            response_text = ""
            response_container = st.empty()
            for text in llm_client.stream(
                model=model,
                system=SYSTEM_PROMPT,
                messages=api_messages,
                max_tokens=int(config["max_tokens"]),
                provider=provider,
            ):
                response_text += text
                response_container.write(response_text)

            # Content filter check
            is_safe, matched = _check_content(response_text)
            if not is_safe:
                _log_flagged_output(response_text, matched)
                response_text = _BLOCKED_RESPONSE
                response_container.write(response_text)

            _render_sources(hits)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response_text,
                "sources": hits,
            }
        )
        _increment_message_count()

        # Analytics: log this exchange
        msg_num = sum(1 for m in st.session_state.messages if m["role"] == "user")
        _log_message_event(user_input, response_text, msg_num)

        _maybe_compress_history()
        st.rerun()
