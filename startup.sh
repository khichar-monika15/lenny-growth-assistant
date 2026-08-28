#!/bin/bash
# startup.sh - One-command initialization for The Lenny Growth Assistant

set -e  # Exit on error

echo "🚀 Starting The Lenny Growth Assistant..."
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop first."
    echo "   Download from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

# Determine docker-compose command
if command -v docker-compose &> /dev/null; then
    DC="docker-compose"
else
    DC="docker compose"
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cat > .env << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://lenny:lenny_dev_password@postgres:5432/lenny
POSTGRES_DB=lenny
POSTGRES_USER=lenny
POSTGRES_PASSWORD=lenny_dev_password

# LLM Configuration
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=llama3.1:8b
DEFAULT_MODEL=ollama

# Application
ENVIRONMENT=development
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
AUTO_INGEST=false
TRANSCRIPTS_PATH=/app/data/transcripts

# Frontend
VITE_API_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8080

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8000
CHROMA_COLLECTION_NAME=lenny_transcripts
EOF

    echo "✅ .env created"
    echo ""
    echo "⚠️  To use Anthropic Claude (optional), edit .env and add ANTHROPIC_API_KEY"
    echo "   For demo purposes, Ollama (local) works out of the box."
    echo ""
    read -p "Press Enter to continue with local-only setup, or Ctrl+C to exit and configure..."
fi

# Create data directory for transcripts
mkdir -p data/transcripts

echo "🐳 Starting Docker services..."
$DC up -d

echo ""
echo "⏳ Waiting for services to be ready..."

# Wait for Ollama to be healthy
echo "   Waiting for Ollama..."
until $DC exec -T ollama curl -f http://localhost:11434/api/tags &> /dev/null; do
    echo "   Still waiting for Ollama..."
    sleep 5
done

echo "✅ Ollama is ready!"
echo ""

# Pull Ollama models
echo "📦 Pulling Ollama models (this may take a few minutes)..."
echo "   Pulling llama3.1:8b..."
$DC exec -T ollama ollama pull llama3.1:8b || echo "⚠️  Model pull may continue in background"

echo "   Pulling nomic-embed-text..."
$DC exec -T ollama ollama pull nomic-embed-text || echo "⚠️  Model pull may continue in background"

echo "✅ Models pulled!"
echo ""

# Wait for backend to be healthy
echo "⏳ Waiting for backend to be ready..."
max_attempts=30
attempt=0

until curl -f http://localhost:8080/health &> /dev/null; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "❌ Backend failed to start. Check logs with: $DC logs backend"
        exit 1
    fi
    echo "   Still waiting... (attempt $attempt/$max_attempts)"
    sleep 5
done

echo "✅ Backend is ready!"
echo ""

# Check if transcripts need ingestion
transcript_count=$(ls -1 data/transcripts/*.md 2>/dev/null | wc -l | tr -d ' ')

if [ "$transcript_count" -eq "0" ]; then
    echo "⚠️  No transcripts found in data/transcripts/"
    echo "   To ingest transcripts:"
    echo "   1. Clone https://github.com/LennysNewsletter/lennys-newsletterpodcastdata"
    echo "   2. Copy .md files to data/transcripts/"
    echo "   3. Run: $DC exec backend python -m app.scripts.ingest_transcripts"
    echo ""
else
    echo "📚 Found $transcript_count transcript files"
    echo "   Starting ingestion (this will take 10-15 minutes)..."
    $DC exec -T backend python -m app.scripts.ingest_transcripts || echo "⚠️  Ingestion failed, check logs"
    echo "✅ Ingestion complete!"
    echo ""
fi

echo ""
echo "✨ The Lenny Growth Assistant is running!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Frontend:     http://localhost:3000"
echo "🔧 Backend API:  http://localhost:8080"
echo "📊 API Docs:     http://localhost:8080/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 Next Steps:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Ask a question: 'What did Lenny say about product-market fit?'"
echo "   3. Generate a Ship 30 essay: Click 'Generate Ship 30' button"
echo ""
echo "📋 Useful Commands:"
echo "   🛑 Stop:         $DC down"
echo "   🗑️  Reset data:   $DC down -v"
echo "   📜 View logs:    $DC logs -f backend"
echo "   🔄 Restart:      $DC restart backend"
echo ""
