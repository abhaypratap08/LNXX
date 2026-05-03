#!/usr/bin/env bash
set -e

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
DIM="\033[2m"
RESET="\033[0m"

echo ""
echo "  capto@linux-lab:~\$ come learn linux"
echo "  installing lnxx..."
echo ""

# ── Check Python ──
if ! command -v python3 &>/dev/null; then
  echo "  error: python3 is required but not installed."
  echo "  install it with: sudo apt install python3  (or brew install python)"
  exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_VERSION" -lt 8 ]; then
  echo "  error: python3.8+ required. you have python3.$PYTHON_VERSION"
  exit 1
fi

# ── Download ──
DEST="$HOME/.lnxx"
RAW="https://raw.githubusercontent.com/abhaypratap08/LNXX/main/linuxx.py"

if [ -d "$DEST" ]; then
  echo "  updating existing install at $DEST..."
  curl -fsSL "$RAW" -o "$DEST/linuxx.py"
else
  echo "  installing to $DEST..."
  mkdir -p "$DEST"
  curl -fsSL "$RAW" -o "$DEST/linuxx.py"
fi

# ── Create launcher ──
LAUNCHER="$HOME/.local/bin/lnxx"
mkdir -p "$HOME/.local/bin"

cat > "$LAUNCHER" << 'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/.lnxx/linuxx.py" "$@"
EOF

chmod +x "$LAUNCHER"

# ── PATH hint ──
echo ""
echo "  ✓ installed to $DEST"
echo "  ✓ launcher at $LAUNCHER"
echo ""

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo "  add this to your ~/.bashrc or ~/.zshrc:"
  echo ""
  echo '    export PATH="$HOME/.local/bin:$PATH"'
  echo ""
  echo "  then run:  source ~/.bashrc  (or open a new terminal)"
  echo "  then run:  lnxx"
else
  echo -e "  ${BOLD}${CYAN}┌─────────────────────────────────────┐${RESET}"
  echo -e "  ${BOLD}${CYAN}│                                     │${RESET}"
  echo -e "  ${BOLD}${CYAN}│   run it now:  ${GREEN}lnxx${CYAN}                │${RESET}"
  echo -e "  ${BOLD}${CYAN}│                                     │${RESET}"
  echo -e "  ${BOLD}${CYAN}└─────────────────────────────────────┘${RESET}"
fi

echo ""
