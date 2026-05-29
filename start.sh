#!/bin/bash
# start.sh - Launch LEGEND Neuro-Symbolic Cognitive Assistant

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="/home/zean/.gemini/antigravity/brain/7befb322-761a-4f1a-9b53-75eee7896ad7/scratch/venv/bin/python3"
CLASSIC_SCRIPT="$SCRIPT_DIR/neuro_symbolic_engine.py"
DESKTOP_DIR="$SCRIPT_DIR/desktop-gui"
CLI_SCRIPT="$SCRIPT_DIR/cli/cli.py"

echo "==========================================================="
echo "🪐 LEGEND Neuro-Symbolic Cognitive System & Logic Engine 🪐"
echo "==========================================================="

if [ "$1" == "--classic" ]; then
    echo "🎨 Launching Classic GUI (Tkinter)..."
    if [ -f "$VENV_PYTHON" ]; then
        "$VENV_PYTHON" "$CLASSIC_SCRIPT"
    else
        python3 "$CLASSIC_SCRIPT"
    fi
elif [ "$1" == "--terminal" ]; then
    # Check if the FastAPI server is already running on port 8000 using a portable python socket check
    PY_EXEC="python3"
    if [ -f "$VENV_PYTHON" ]; then
        PY_EXEC="$VENV_PYTHON"
    fi

    if ! "$PY_EXEC" -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(1); s.connect(('127.0.0.1', 8000))" >/dev/null 2>&1; then
        echo "🔌 Inference server not detected on port 8000."
        echo "🚀 Automatically launching Inference server (FastAPI) in background..."
        
        # Start server in background from the cli directory
            cd "$SCRIPT_DIR/cli" || exit
            "$PY_EXEC" -m uvicorn app:app --host 127.0.0.1 --port 8000 > /dev/null 2>&1 &
        
        # Wait a few seconds for the server to spin up and bind to port
        echo -n "⏳ Bootstrapping the reasoning engine in the background "
        for i in {1..5}; do
            echo -n "."
            sleep 1
        done
        echo " Ready!"
        cd "$SCRIPT_DIR" || exit
    fi

    echo "🪐 Launching premium interactive Terminal interface (CLI Docs Menu)..."
    "$PY_EXEC" "$CLI_SCRIPT"
else
    echo "🚀 Launching beautiful standalone app (Electron + React)..."
    cd "$DESKTOP_DIR" || exit
    ./node_modules/.bin/electron . --no-sandbox
fi
