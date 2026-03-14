#!/bin/bash
# discli installer
# curl -fsSL https://raw.githubusercontent.com/DevRohit06/discli/main/installers/install.sh | bash

set -e

echo "Installing discli..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python 3.10+ is required. Install it from https://python.org"
    exit 1
fi

PY=$(command -v python3 || command -v python)
PY_VERSION=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PY -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "Error: Python 3.10+ is required (found $PY_VERSION)"
    exit 1
fi

echo "Using Python $PY_VERSION"

# Install from GitHub
$PY -m pip install git+https://github.com/DevRohit06/discli.git 2>&1
if [ $? -ne 0 ]; then
    echo "Error: pip install failed."
    exit 1
fi

echo ""

# Check PATH
if command -v discli &> /dev/null; then
    echo "discli is ready!"
    discli --help
else
    SCRIPTS_DIR=$($PY -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
    if [ -n "$SCRIPTS_DIR" ] && [ -f "$SCRIPTS_DIR/discli" ]; then
        echo "discli installed to: $SCRIPTS_DIR"
        echo ""

        # Detect shell and suggest profile
        SHELL_NAME=$(basename "$SHELL")
        case "$SHELL_NAME" in
            zsh)  PROFILE="$HOME/.zshrc" ;;
            bash) PROFILE="$HOME/.bashrc" ;;
            fish) PROFILE="$HOME/.config/fish/config.fish" ;;
            *)    PROFILE="$HOME/.profile" ;;
        esac

        echo "Add to PATH by running:"
        echo ""
        if [ "$SHELL_NAME" = "fish" ]; then
            echo "  fish_add_path $SCRIPTS_DIR"
        else
            echo "  echo 'export PATH=\"$SCRIPTS_DIR:\$PATH\"' >> $PROFILE"
            echo "  source $PROFILE"
        fi
    fi
fi

echo ""
echo "Done! Get started:"
echo "  discli config set token YOUR_BOT_TOKEN"
echo "  discli server list"
