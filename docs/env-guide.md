# Environment Variables Guide

How API keys and config are loaded locally and on Streamlit Cloud.

## How the app reads config

The app checks two sources, in order:

1. **Streamlit secrets** (`st.secrets`) — used on Streamlit Cloud
2. **OS environment / `.env` file** — used locally

The first match wins. This is handled by `_get_secret_or_env()` in `streamlit_app.py`.

## Local development

### 1. Create `.env` from the example

```bash
cp .env.example .env
```

### 2. Fill in your keys

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...
```

### 3. Run the app

```bash
make app
```

The app loads `.env` at startup via `_load_dotenv()` in `streamlit_app.py`. This is a simple parser (not python-dotenv) — it reads `KEY=VALUE` lines, strips quotes, and calls `os.environ.setdefault()` so real env vars take precedence.

### Local-only behavior

When `DEPLOYMENT` is unset or set to `local` (the default):

- Rate limiting is **off** (no IP checks, no session caps, no message limit)
- Retrieval sources are shown in expandable panels
- A/B model assignment still happens (for testing), but you can override by setting `LLM_PROVIDER` and `MODEL` for `extract_worldview.py` and other CLI tools

## Streamlit Cloud deployment

### 1. Add secrets in the dashboard

Go to your app's settings on Streamlit Cloud and add secrets in TOML format:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
OPENAI_API_KEY = "sk-..."
DEEPSEEK_API_KEY = "sk-..."
GEMINI_API_KEY = "..."
DEPLOYMENT = "web"
```

### 2. Optional config

```toml
KILL_SWITCH = "0"            # Set to "1" to disable the app instantly
MAX_SESSIONS_PER_IP = "3"    # Sessions per IP per 24h
DAILY_SESSION_CAP = "300"    # Global daily session cap
TOP_K = "5"
MAX_TOKENS = "600"
```

### Cloud-only behavior

When `DEPLOYMENT=web`:

- IP-based rate limiting is **on** (3 sessions/IP/24h)
- Global daily cap is **on** (300 sessions/day)
- Per-session 8-message limit is **on**
- Retrieval sources are **hidden**
- Post-session poll appears after the 8th message

### Secrets vs `.env`

On Streamlit Cloud, `.env` files are not deployed (gitignored). Use the Streamlit secrets manager instead. The app checks `st.secrets` first, so secrets always override any `.env` that might exist.

Locally, `.streamlit/secrets.toml` also works but `.env` is simpler. The `.streamlit/secrets.toml` file is gitignored.

## Variable reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes (A/B) | — | Anthropic API key |
| `OPENAI_API_KEY` | Yes | — | OpenAI key (embeddings + reranker) |
| `DEEPSEEK_API_KEY` | Yes (A/B) | — | DeepSeek API key |
| `GEMINI_API_KEY` | Yes (A/B) | — | Google AI API key |
| `DEPLOYMENT` | No | `local` | `web` enables rate limiting |
| `KILL_SWITCH` | No | `0` | `1` disables the app |
| `MAX_SESSIONS_PER_IP` | No | `3` | IP session limit (24h) |
| `DAILY_SESSION_CAP` | No | `300` | Global daily session limit |
| `TOP_K` | No | `5` | Retrieval chunk count |
| `MAX_TOKENS` | No | `600` | Max LLM output tokens |
| `LLM_PROVIDER` | No | `anthropic` | Fallback provider for CLI tools |
| `MODEL` | No | per-provider | Fallback model for CLI tools |
| `RERANK_MODEL` | No | — | Reranker model override |

The `LLM_PROVIDER` and `MODEL` variables are only used by CLI tools (`extract_worldview.py`, etc.). The chat app ignores them — it uses the A/B router instead.

## Kill switch

Set `KILL_SWITCH=1` in Streamlit secrets to immediately disable the app. Users see: "Serviciul este temporar indisponibil." No API calls are made. Set back to `0` (or remove) to re-enable.
