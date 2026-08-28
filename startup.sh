#!/usr/bin/env bash
#
# One-command startup for The Lenny Growth Assistant.
#
# Brings up the stack, pulls the local models, ingests transcripts and leaves
# a working, grounded assistant on http://localhost:3000.
#
# Runs unattended: every wait is bounded and nothing prompts for input, so it
# is safe in CI or over SSH.
#
#   ./startup.sh              # ingest INGEST_LIMIT transcripts (default 15)
#   INGEST_LIMIT=0 ./startup.sh   # ingest the full catalogue
#   SKIP_INGEST=1 ./startup.sh    # start services only

set -Eeuo pipefail

readonly OLLAMA_WAIT_SECONDS=180
readonly BACKEND_WAIT_SECONDS=240

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
ok()   { printf '    \033[0;32mok\033[0m %s\n' "$1"; }
warn() { printf '    \033[0;33m!\033[0m  %s\n' "$1"; }
die()  { printf '\n\033[0;31mERROR\033[0m %s\n\n' "$1" >&2; exit 1; }

trap 'die "Startup failed on line $LINENO. Inspect logs with: $DC logs"' ERR

# --- Prerequisites ----------------------------------------------------------

command -v docker >/dev/null 2>&1 \
  || die "Docker is not installed. Get Docker Desktop: https://www.docker.com/products/docker-desktop"

docker info >/dev/null 2>&1 \
  || die "Docker is installed but not running. Start Docker Desktop and retry."

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  die "Docker Compose is not available. Install Docker Desktop, which bundles it."
fi
readonly DC

cd "$(dirname "$0")"

# --- Configuration ----------------------------------------------------------

if [ ! -f .env ]; then
  [ -f .env.example ] || die ".env.example is missing; cannot create .env."
  cp .env.example .env
  log "Created .env from .env.example"
  ok "Local defaults applied. Ollama works with no further setup."
  ok "To use Claude instead, add ANTHROPIC_API_KEY to .env and rerun."
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a

INGEST_LIMIT="${INGEST_LIMIT:-15}"
SKIP_INGEST="${SKIP_INGEST:-0}"
CHAT_MODEL="${OLLAMA_CHAT_MODEL:-llama3.2:3b}"
EMBED_MODEL="${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}"

# --- Services ---------------------------------------------------------------

log "Starting Docker services"
$DC up -d --build
ok "postgres, chromadb, ollama, backend, frontend"

wait_for() {
  local label="$1" deadline="$2" probe="$3" elapsed=0
  printf '    waiting for %s' "$label"
  until eval "$probe" >/dev/null 2>&1; do
    if [ "$elapsed" -ge "$deadline" ]; then
      printf '\n'
      die "$label did not become ready within ${deadline}s. Check: $DC logs ${label}"
    fi
    printf '.'
    sleep 3
    elapsed=$((elapsed + 3))
  done
  printf '\n'
  ok "$label ready (${elapsed}s)"
}

log "Waiting for services"
wait_for ollama "$OLLAMA_WAIT_SECONDS" "$DC exec -T ollama ollama list"
wait_for backend "$BACKEND_WAIT_SECONDS" "curl -fsS http://localhost:8080/health"

# --- Models -----------------------------------------------------------------

pull_model() {
  local model="$1"
  if $DC exec -T ollama ollama list 2>/dev/null | grep -q "^${model%%:*}"; then
    ok "$model already present"
  else
    printf '    pulling %s (several GB on first run, this takes a while)\n' "$model"
    $DC exec -T ollama ollama pull "$model" >/dev/null \
      || die "Failed to pull $model. Check connectivity and retry."
    ok "$model pulled"
  fi
}

log "Preparing local models"
pull_model "$CHAT_MODEL"
pull_model "$EMBED_MODEL"

# --- Knowledge base ---------------------------------------------------------
#
# Transcripts are fetched over HTTP from the public Lenny's Podcast repository
# by the ingestion pipeline. Nothing needs to be cloned or copied by hand.

if [ "$SKIP_INGEST" = "1" ]; then
  log "Skipping ingestion (SKIP_INGEST=1)"
  warn "The assistant cannot ground answers until transcripts are ingested."
else
  indexed=$(curl -fsS http://localhost:8080/health/retrieval 2>/dev/null \
    | sed -n 's/.*"indexed_chunks":[[:space:]]*\([0-9]*\).*/\1/p')
  indexed="${indexed:-0}"

  if [ "$indexed" -gt 0 ]; then
    log "Knowledge base already populated"
    ok "$indexed chunks indexed. Re-run ingestion any time with:"
    ok "  $DC exec backend python -m app.scripts.ingest_transcripts --all"
  else
    if [ "$INGEST_LIMIT" = "0" ]; then
      log "Ingesting the full transcript catalogue (this takes a while)"
      ingest_args="--all"
    else
      log "Ingesting $INGEST_LIMIT transcripts"
      ingest_args="--limit $INGEST_LIMIT"
    fi

    # shellcheck disable=SC2086
    $DC exec -T backend python -m app.scripts.ingest_transcripts $ingest_args \
      || die "Ingestion failed. Inspect with: $DC logs backend"

    indexed=$(curl -fsS http://localhost:8080/health/retrieval 2>/dev/null \
      | sed -n 's/.*"indexed_chunks":[[:space:]]*\([0-9]*\).*/\1/p')
    ok "${indexed:-0} chunks indexed"
  fi
fi

# --- Done -------------------------------------------------------------------

cat <<BANNER

  The Lenny Growth Assistant is running.

  ────────────────────────────────────────────
   App        http://localhost:3000
   API        http://localhost:8080
   API docs   http://localhost:8080/docs
   Health     http://localhost:8080/health/retrieval
  ────────────────────────────────────────────

  Try asking:
    "What does Jen Abel say about closing enterprise deals?"
    "Write a Ship 30 essay about talent density"
    "Create a markdown checklist for a first sales call"

  Useful commands:
    Stop            $DC down
    Reset all data  $DC down -v
    Backend logs    $DC logs -f backend
    Run tests       $DC exec backend python -m pytest
    Ingest all      $DC exec backend python -m app.scripts.ingest_transcripts --all

BANNER
