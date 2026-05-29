#!/bin/bash
# start_api.sh - Active the workspace venv and run the headless LEGEND FastAPI server

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Target Python interpreter from the verified workspace virtual environment
VENV_PYTHON="/home/zean/.gemini/antigravity/brain/7befb322-761a-4f1a-9b53-75eee7896ad7/scratch/venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "⚠️ Target virtual environment not found at: $VENV_PYTHON"
    echo "Attempting to use system 'python3' as a fallback..."
    VENV_PYTHON="python3"
fi

echo "🪐 Starting Headless LEGEND Neuro-Symbolic Arabic Reasoning Engine API..."
echo "📂 Working directory: $DIR"
echo "🐍 Python Interpreter: $VENV_PYTHON"
echo "🌐 API Endpoint: http://127.0.0.1:8000"
echo "--------------------------------------------------------"

# Run Uvicorn pointing to the app module in the cli directory
cd "$DIR"
"$VENV_PYTHON" -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
