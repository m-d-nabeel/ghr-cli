#!/usr/bin/env python3

"""
GHR CLI - A Python utility for managing command-line tools from GitHub releases
Features:
- Automatic download URL detection from GitHub releases
- Versioned installations with symbolic links
- Simple YAML configuration
- Clean old versions while keeping N most recent

Usage:
  ghr-cli [options]

Options:
  --config FILE    Configuration file (default: toolset.yaml)
  --clean          Clean old versions according to keep_versions setting
  --install        Install all tools (don't prompt)
  --install REPO   Install specific tool by repo name (e.g. jesseduffield/lazygit)
  --list           List all configured tools and their versions
  --rollback REPO  Rollback to previous version of a tool
  --init           Initialize a default config file in ~/.config/ghr-cli/
  --help           Show this help message

Configuration file is searched in the following locations:
1. Specified path via --config
2. Current directory (toolset.yaml)
3. Same directory as the executable
4. User config directory (~/.config/ghr-cli/toolset.yaml)
5. System-wide location (/etc/ghr-cli/toolset.yaml)
"""

from ghrcli import run_cli

if __name__ == "__main__":
    run_cli()
