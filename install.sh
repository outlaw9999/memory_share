#!/usr/bin/env bash
set -e

echo "Installing .kit - Cognitive OS Layer"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: 'python3' is required to install .kit."
    exit 1
fi

INSTALL_DIR="${HOME}/.kit-engine"
BIN_DIR="${HOME}/.local/bin"
WRAPPER_SCRIPT="${BIN_DIR}/kit"

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

for dir in kit kit_agent runtime scripts; do
    rm -rf "${INSTALL_DIR:?}/${dir}"
    cp -R "$dir" "$INSTALL_DIR/"
done
cp "kit.py" "$INSTALL_DIR/"

cat <<'EOF' > "$WRAPPER_SCRIPT"
#!/usr/bin/env bash
KIT_ENGINE="${HOME}/.kit-engine"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONPATH="${KIT_ENGINE}:${PYTHONPATH}"
exec python3 -m kit.cli.main "$@"
EOF

chmod +x "$WRAPPER_SCRIPT"

echo ".kit installed successfully."
echo ""
echo "Wrapper:"
echo "  ${WRAPPER_SCRIPT}"
echo ""
echo "If 'kit' still resolves to a pip launcher, remove the stale editable install:"
echo "  python3 -m pip uninstall memory-share-kit"
echo "Then ensure ${BIN_DIR} appears before your Python scripts directory in PATH."
echo ""
echo "Next steps:"
echo "  cd your-project"
echo "  kit init"
