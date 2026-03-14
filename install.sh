#!/bin/bash
# discli installer for macOS/Linux
# Run: bash install.sh

echo "Installing discli..."

pip install -e ".[dev]"
if [ $? -ne 0 ]; then
    echo "Failed to install package."
    exit 1
fi

# Check if discli is on PATH
if command -v discli &> /dev/null; then
    echo "discli is on PATH."
else
    # Find where it was installed
    SCRIPTS_DIR=$(python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
    if [ -n "$SCRIPTS_DIR" ] && [ -f "$SCRIPTS_DIR/discli" ]; then
        echo "discli installed at: $SCRIPTS_DIR"
        echo ""
        echo "Add to your shell profile:"
        echo "  echo 'export PATH=\"$SCRIPTS_DIR:\$PATH\"' >> ~/.bashrc"
        echo ""
    fi
fi

discli --help 2>/dev/null || echo "Restart your terminal, then run: discli --help"
echo ""
echo "discli installed successfully!"
echo "Run 'discli config set token YOUR_BOT_TOKEN' to get started."
