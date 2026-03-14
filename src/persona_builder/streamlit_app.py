import os
from pathlib import Path

import anthropic
import streamlit as st

from .paths import DEFAULT_OUTPUT_DIR, REPO_ROOT
from .persona_prompt import SYSTEM_PROMPT
from .retrieval import build_bm25_index, format_context_block, load_corpus, retrieve

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TOP_K = 5
DEFAULT_MAX_TOKENS = 600
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
    return {
        "anthropic_api_key": _get_secret_or_env("ANTHROPIC_API_KEY"),
        "model": _get_secret_or_env("MODEL", DEFAULT_MODEL),
        "top_k": _get_int_setting("TOP_K", DEFAULT_TOP_K),
        "max_tokens": _get_int_setting("MAX_TOKENS", DEFAULT_MAX_TOKENS),
        "output_dir": str(DEFAULT_OUTPUT_DIR),
    }


def validate_startup(config: dict[str, object]) -> list[str]:
    errors = []
    output_dir = Path(str(config["output_dir"]))

    if not config.get("anthropic_api_key"):
        errors.append("Lipsește `ANTHROPIC_API_KEY` din Streamlit secrets sau variabilele de mediu.")

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


def build_api_messages(history: list[dict], augmented_user_message: str) -> list[dict[str, str]]:
    api_messages = []
    for msg in history:
        if msg["role"] in {"user", "assistant"}:
            api_messages.append({"role": msg["role"], "content": msg["content"]})
    api_messages.append({"role": "user", "content": augmented_user_message})
    return api_messages


def render_sources(hits: list[dict]) -> None:
    if not hits:
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

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant":
                render_sources(msg.get("sources", []))

    user_input = st.chat_input("Spune ceva...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        hits = retrieve(user_input, bm25, corpus, top_k=int(config["top_k"]))
        augmented_user_message = build_augmented_user_message(user_input, hits)
        api_messages = build_api_messages(st.session_state.messages[:-1], augmented_user_message)

        client = anthropic.Anthropic(api_key=str(config["anthropic_api_key"]))

        with st.chat_message("assistant"):
            response_text = ""
            with st.spinner("Caut fragmente relevante și compun răspunsul..."):
                with client.messages.stream(
                    model=str(config["model"]),
                    max_tokens=int(config["max_tokens"]),
                    system=SYSTEM_PROMPT,
                    messages=api_messages,
                ) as stream:
                    response_container = st.empty()
                    for text in stream.text_stream:
                        response_text += text
                        response_container.write(response_text)

            render_sources(hits)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response_text,
                "sources": hits,
            }
        )
