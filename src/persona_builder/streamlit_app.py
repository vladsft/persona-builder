import os
import time
from pathlib import Path

import streamlit as st

from . import llm_client
from .paths import DEFAULT_OUTPUT_DIR, REPO_ROOT
from .persona_prompt import SYSTEM_PROMPT
from .retrieval import build_bm25_index, format_context_block, load_corpus, retrieve

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}
DEFAULT_TOP_K = 5
DEFAULT_MAX_TOKENS = 600
MAX_VERBATIM_MESSAGES = 6  # 3 user+assistant exchanges kept verbatim
RATE_LIMIT_MESSAGES = 8
RATE_LIMIT_WINDOW = 5 * 60 * 60  # 5 hours in seconds
DOTENV_PATH = REPO_ROOT / ".env"


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
    provider = (_get_secret_or_env("LLM_PROVIDER", "anthropic") or "anthropic").lower()
    default_model = DEFAULT_MODELS.get(provider, DEFAULT_MODELS["anthropic"])
    return {
        "provider": provider,
        "model": _get_secret_or_env("MODEL", default_model),
        "top_k": _get_int_setting("TOP_K", DEFAULT_TOP_K),
        "max_tokens": _get_int_setting("MAX_TOKENS", DEFAULT_MAX_TOKENS),
        "output_dir": str(DEFAULT_OUTPUT_DIR),
    }


def validate_startup(config: dict[str, object]) -> list[str]:
    errors = []
    output_dir = Path(str(config["output_dir"]))

    try:
        llm_client.get_api_key(str(config["provider"]))
    except RuntimeError as exc:
        errors.append(str(exc))

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
# Rate limiting
# ---------------------------------------------------------------------------

def _is_web_deployment() -> bool:
    """True when running on Streamlit Cloud (rate limits + no sources)."""
    return _get_secret_or_env("DEPLOYMENT", "local") == "web"


def _init_rate_limit() -> None:
    """Initialize rate-limit state if missing."""
    if "rate_limit_start" not in st.session_state:
        st.session_state.rate_limit_start = time.time()
        st.session_state.rate_limit_count = 0


def _check_rate_limit() -> bool:
    """Return True if the user can send a message."""
    if not _is_web_deployment():
        return True
    _init_rate_limit()
    now = time.time()

    # Reset window if expired
    if now - st.session_state.rate_limit_start > RATE_LIMIT_WINDOW:
        st.session_state.rate_limit_start = now
        st.session_state.rate_limit_count = 0

    return st.session_state.rate_limit_count < RATE_LIMIT_MESSAGES


def _increment_rate_limit() -> None:
    if not _is_web_deployment():
        return
    st.session_state.rate_limit_count = st.session_state.get("rate_limit_count", 0) + 1


def _remaining_messages() -> int | None:
    """Return remaining messages, or None if rate limiting is off."""
    if not _is_web_deployment():
        return None
    _init_rate_limit()
    return max(0, RATE_LIMIT_MESSAGES - st.session_state.rate_limit_count)


def _reset_time_str() -> str:
    """Human-readable time until the rate limit resets."""
    _init_rate_limit()
    elapsed = time.time() - st.session_state.rate_limit_start
    remaining_seconds = max(0, RATE_LIMIT_WINDOW - elapsed)
    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


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
# Main app
# ---------------------------------------------------------------------------

def run() -> None:
    _load_dotenv()

    st.set_page_config(
        page_title="Prea Mult Banciu",
        page_icon="📺",
        layout="centered",
    )

    st.title("Prea Mult Banciu")
    st.caption("AI replica experimentală bazată pe emisiunile lui Radu Banciu. Proiect neoficial de fan, fără scop comercial.")

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

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Show remaining messages in sidebar (web only)
    remaining = _remaining_messages()
    if remaining is not None:
        st.sidebar.markdown(f"**Mesaje rămase:** {remaining}/{RATE_LIMIT_MESSAGES}")
        if remaining == 0:
            st.sidebar.warning(f"Limită atinsă. Se resetează în {_reset_time_str()}.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant":
                _render_sources(msg.get("sources", []))

    user_input = st.chat_input("Spune ceva...", disabled=remaining == 0 if remaining is not None else False)

    if user_input:
        if not _check_rate_limit():
            st.error(f"Ai atins limita de {RATE_LIMIT_MESSAGES} mesaje. Revino în {_reset_time_str()}.")
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
                model=str(config["model"]),
                system=SYSTEM_PROMPT,
                messages=api_messages,
                max_tokens=int(config["max_tokens"]),
            ):
                response_text += text
                response_container.write(response_text)

            _render_sources(hits)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response_text,
                "sources": hits,
            }
        )
        _increment_rate_limit()
        _maybe_compress_history()
        st.rerun()
