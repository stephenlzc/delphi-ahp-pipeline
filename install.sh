#!/bin/bash
#
# Delphi-AHP Pipeline Installer (macOS / Linux)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/stephenlzc/DelphiAHPFlow/main/install.sh | bash
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "=== Delphi-AHP Pipeline Installer (macOS / Linux) ==="
echo ""

# 1. Detect Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "[OK] Python found: $PYTHON_VERSION"
else
    echo "[INFO] Python 3 not found."
    if command -v brew &> /dev/null; then
        echo "[INFO] Installing Python 3 via Homebrew..."
        brew install python
    else
        echo "[INFO] Homebrew not found. Installing Homebrew first..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        echo "[INFO] Homebrew installed. Now installing Python 3..."
        brew install python
    fi
    echo "[OK] Python installed: $(python3 --version)"
fi

# Verify python3 is available
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 still not available after installation. Please restart your terminal and try again."
    exit 1
fi

# 2. Create virtual environment
echo ""
echo "[INFO] Creating virtual environment..."
python3 -m venv "$SCRIPT_DIR/.venv"

# 3. Install dependencies
echo "[INFO] Installing dependencies..."
source "$SCRIPT_DIR/.venv/bin/activate"
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Run the application:"
echo "  cd $SCRIPT_DIR"
echo "  source .venv/bin/activate"
echo "  python3 app.py"
echo ""
echo "Or simply run:"
echo "  bash \"$SCRIPT_DIR/run.sh\""
echo ""
