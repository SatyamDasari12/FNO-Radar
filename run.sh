#!/bin/bash

# ────────────────────────────────────────────────────────────
#  FNO-Radar — Launch Script
# ────────────────────────────────────────────────────────────
#
#  Usage:
#    ./run.sh              Full setup + launch (skips pip if unchanged)
#    ./run.sh --quick      Skip pip install & data refresh (fastest)
#    ./run.sh --refresh    Force data refresh even if recently done
#    ./run.sh --help       Show this help
#
# ────────────────────────────────────────────────────────────

set -e

# ── Graceful interrupt handler ────────────────────────────
cleanup() {
    echo ""
    echo "👋 Shutting down FNO-Radar..."
    exit 0
}
trap cleanup INT TERM

# ── Parse flags ───────────────────────────────────────────
QUICK_MODE=false
FORCE_REFRESH=false

for arg in "$@"; do
    case "$arg" in
        --quick|-q)   QUICK_MODE=true ;;
        --refresh|-r) FORCE_REFRESH=true ;;
        --help|-h)
            head -13 "$0" | tail -10
            exit 0
            ;;
    esac
done

# ── Constants ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MARKER_FILE=".pip_installed"
REFRESH_MARKER=".last_data_refresh"
REFRESH_INTERVAL_SECS=1800  # Refresh data if older than 30 minutes

echo "===================================================="
echo "    FNO-Radar Setup & Execution Script"
echo "===================================================="

# ── 1. Virtual Environment ───────────────────────────────
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✔ Virtual environment '.venv' activated."
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "✔ Virtual environment 'venv' activated."
else
    echo "❓ No virtual environment detected."
    read -p "Create a new virtual environment? (y/n): " create_env
    if [[ "$create_env" =~ ^[Yy]$ ]]; then
        echo "Creating virtual environment '.venv'..."
        python3 -m venv .venv
        source .venv/bin/activate
        echo "✔ Created and activated '.venv'."
        # Force pip install on fresh env
        rm -f "$MARKER_FILE"
    else
        echo "⚠ Proceeding with system python."
    fi
fi

# ── 2. Install Dependencies (smart skip) ─────────────────
if [ "$QUICK_MODE" = true ]; then
    echo "⏩ Quick mode — skipping pip install."
elif [ -f "$MARKER_FILE" ] && [ "$MARKER_FILE" -nt "requirements.txt" ]; then
    echo "✔ Dependencies are up to date (requirements.txt unchanged)."
else
    echo "⬇ Installing dependencies..."
    pip install --upgrade pip --quiet 2>&1 | tail -1
    pip install -r requirements.txt --quiet 2>&1 | grep -v "already satisfied" || true
    touch "$MARKER_FILE"
    echo "✔ Dependencies installed."
fi

# ── 3. Environment Keys ──────────────────────────────────
if [ ! -f ".env" ]; then
    echo "❓ No .env file found."
    read -p "Configure GROQ_API_KEY now? (y/n): " config_env
    if [[ "$config_env" =~ ^[Yy]$ ]]; then
        read -sp "Enter your GROQ_API_KEY: " groq_key
        echo ""
        echo "GROQ_API_KEY=$groq_key" > .env
        echo "✔ .env file created."
    else
        echo "⚠ Proceeding without API key (AI summaries fall back to rule-based text)."
    fi
else
    echo "✔ .env configuration loaded."
fi

# ── 4. Refresh Cache Databases (smart skip) ───────────────
should_refresh=false

if [ "$FORCE_REFRESH" = true ]; then
    should_refresh=true
elif [ "$QUICK_MODE" = true ]; then
    should_refresh=false
    echo "⏩ Quick mode — skipping data refresh."
elif [ ! -f "$REFRESH_MARKER" ]; then
    should_refresh=true
elif [ ! -f "data/stock_master.json" ] || [ ! -f "data/fno_master.json" ]; then
    should_refresh=true
else
    # Check if the last refresh was more than REFRESH_INTERVAL_SECS ago
    if [[ "$(uname)" == "Darwin" ]]; then
        last_refresh=$(stat -f "%m" "$REFRESH_MARKER" 2>/dev/null || echo 0)
    else
        last_refresh=$(stat -c "%Y" "$REFRESH_MARKER" 2>/dev/null || echo 0)
    fi
    now=$(date +%s)
    elapsed=$((now - last_refresh))
    if [ "$elapsed" -ge "$REFRESH_INTERVAL_SECS" ]; then
        should_refresh=true
    else
        remaining=$(( (REFRESH_INTERVAL_SECS - elapsed) / 60 ))
        echo "✔ Stock data is fresh (next refresh in ~${remaining}min). Use --refresh to force."
    fi
fi

if [ "$should_refresh" = true ]; then
    echo "📡 Refreshing stock databases (NSE/BSE & F&O lot sizes)..."
    python scripts/refresh_stock_master.py
    python scripts/refresh_fno_master.py
    touch "$REFRESH_MARKER"
    echo "✔ Cache database refresh complete."
fi

# ── 5. Launch Streamlit ───────────────────────────────────
echo ""
echo "🚀 Launching FNO-Radar..."
echo "   Local:   http://localhost:8501"
echo ""
python -m streamlit run app.py
