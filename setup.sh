#!/usr/bin/env bash

set -e

# Function to install bash completions
install_bash_completions() {
    echo "Installing Bash completions..."
    
    # Bash completions
    BASH_COMPLETION_DIR="$HOME/.local/share/bash-completion/completions"
    if [ ! -d "$BASH_COMPLETION_DIR" ]; then
        mkdir -p "$BASH_COMPLETION_DIR"
    fi
    cp ghr-cli-completion.bash "$BASH_COMPLETION_DIR/ghr-cli"
    echo "Installed Bash completions to $BASH_COMPLETION_DIR/ghr-cli"
    echo "You may need to restart your shell or run 'source ~/.bashrc' for completions to take effect."
}

# Function to install zsh completions
install_zsh_completions() {
    echo "Installing Zsh completions..."
    
    # Zsh completions
    ZSH_COMPLETION_DIR="$HOME/.zsh/completions"
    if [ ! -d "$ZSH_COMPLETION_DIR" ]; then
        mkdir -p "$ZSH_COMPLETION_DIR"
        echo "Created $ZSH_COMPLETION_DIR"
        # Add to .zshrc if not already there
        if ! grep -q "$ZSH_COMPLETION_DIR" "$HOME/.zshrc" 2>/dev/null; then
            echo "Adding completion directory to .zshrc"
            echo "# GHR CLI Completions" >> "$HOME/.zshrc"
            echo "fpath=($ZSH_COMPLETION_DIR \$fpath)" >> "$HOME/.zshrc"
            echo "autoload -Uz compinit && compinit" >> "$HOME/.zshrc"
        fi
    fi
    cp ghr-cli-completion.zsh "$ZSH_COMPLETION_DIR/_ghr-cli"
    echo "Installed Zsh completions to $ZSH_COMPLETION_DIR/_ghr-cli"
    echo "You may need to restart your shell or run 'source ~/.zshrc' for completions to take effect."
}

# Parse command line arguments
install_bash_completions_flag=false
install_zsh_completions_flag=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bash-completions)
            install_bash_completions_flag=true
            shift
            ;;
        --zsh-completions)
            install_zsh_completions_flag=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Available options: --bash-completions, --zsh-completions"
            shift
            ;;
    esac
done

# If we're only installing completions, skip the rest
if $install_bash_completions_flag || $install_zsh_completions_flag; then
    if $install_bash_completions_flag; then
        install_bash_completions
    fi
    
    if $install_zsh_completions_flag; then
        install_zsh_completions
    fi
    
    exit 0
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "Installing development dependencies..."
pip install pyinstaller

# Build the executable
echo "Building standalone executable..."
pyinstaller --onefile --name ghr-cli \
  --add-data "ghrcli:ghrcli" \
  --hidden-import ghrcli.core.manager \
  --hidden-import ghrcli.core.operations \
  --hidden-import ghrcli.utils.cache \
  --hidden-import ghrcli.utils.config \
  --hidden-import ghrcli.utils.system \
  --hidden-import ghrcli.cli.cli \
  main.py

# Create bin directory if it doesn't exist
echo "Creating bin directory..."
mkdir -p bin

# Add execution permission to the executable
chmod +x dist/ghr-cli

# Move the executable to the bin directory
mv dist/ghr-cli bin/

# Create a symlink in the current directory for convenience
ln -sf bin/ghr-cli .

# Clean up build files
rm -rf build dist *.spec

echo "Setup complete! You can run ghr-cli with:"
echo "./ghr-cli --help"
echo ""
echo "The standalone executable is located in the bin/ directory."
echo "You can copy bin/ghr-cli along with your toolset.yaml to any location."
echo ""
echo "For shell completions, you can run:"
echo "  ./setup.sh --bash-completions   # For Bash completions"
echo "  ./setup.sh --zsh-completions    # For Zsh completions"