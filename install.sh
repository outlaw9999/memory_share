#!/usr/bin/env bash
set -e

# .kit Install Script for Linux/macOS
echo "🧠 Installing .kit - Cognitive OS Layer"

if ! command -v git &> /dev/null || ! command -v python3 &> /dev/null; then
    echo "❌ Error: 'git' and 'python3' are required to install .kit."
    exit 1
fi

INSTALL_DIR="${HOME}/.kit-engine"
mkdir -p "$INSTALL_DIR"

# Copy the core python files or clone from github if downloading remotely
# Since we are inside the source directory:
cp -r kit "$INSTALL_DIR/"
cp kit.py "$INSTALL_DIR/"

# Create a shell wrapper
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
WRAPPER_SCRIPT="$BIN_DIR/kit"

cat << 'EOF' > "$WRAPPER_SCRIPT"
#!/usr/bin/env bash
python3 "$HOME/.kit-engine/kit.py" "$@"
EOF

chmod +x "$WRAPPER_SCRIPT"

echo "✅ .kit installed successfully!"
echo ""
echo "Please ensure ${BIN_DIR} is in your PATH."
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Next steps:"
echo "  cd your-project"
echo "  kit init"
