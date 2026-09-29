#!/usr/bin/env bash
set -e

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
RESET="\033[0m"

echo ""
echo "  capto@linux-lab:\$ come learn linux"
echo "  installing lnxx..."
echo ""

if ! command -v python3 &>/dev/null; then
  echo "  error: python3 is required but not installed."
  echo "  install Python 3 with your OS package manager and run this installer again."
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,8) else 1)'; then
  echo "  error: Python 3.8+ required."
  exit 1
fi

DEST="$HOME/.lnxx"
VENV="$DEST/.venv"
RAW="https://raw.githubusercontent.com/abhaypratap08/LNXX/main/linuxx.py"

mkdir -p "$DEST"
curl -fsSL "$RAW" -o "$DEST/linuxx.py"

if [ ! -x "$VENV/bin/python" ]; then
  echo "  creating private Python environment..."
  python3 -m venv "$VENV"
fi

echo "  preparing LNXX dependencies..."
if ! "$VENV/bin/python" -m pip install --disable-pip-version-check --quiet textual >/dev/null 2>&1; then
  echo "  error: could not install LNXX dependencies."
  echo "  check your internet connection and Python installation, then run the installer again."
  exit 1
fi

LAUNCHER="$HOME/.local/bin/lnxx"
mkdir -p "$HOME/.local/bin"

cat > "$LAUNCHER" << 'EOF'
#!/usr/bin/env bash
exec "$HOME/.lnxx/.venv/bin/python" "$HOME/.lnxx/linuxx.py" "$@"
EOF
chmod +x "$LAUNCHER"

add_path_bash() {
  local file="$1"
  [ -f "$file" ] || touch "$file"
  if ! grep -Fqx 'export PATH="$HOME/.local/bin:$PATH"' "$file" 2>/dev/null; then
    printf '\n# LNXX\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$file"
  fi
}

add_path_fish() {
  local file="$1"
  mkdir -p "$(dirname "$file")"
  [ -f "$file" ] || touch "$file"
  if ! grep -Fqx 'fish_add_path $HOME/.local/bin' "$file" 2>/dev/null; then
    printf '\n# LNXX\nfish_add_path $HOME/.local/bin\n' >> "$file"
  fi
}

add_path_bash "$HOME/.bashrc"
add_path_bash "$HOME/.bash_profile"
add_path_bash "$HOME/.zshrc"
add_path_fish "$HOME/.config/fish/config.fish"

echo ""
echo -e "  ${BOLD}${CYAN}✓ LNXX installed${RESET}"
echo "  private environment: $VENV"
echo "  launcher: $LAUNCHER"
echo ""
echo "  Open a new terminal, then run: lnxx"
echo ""
