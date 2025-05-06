#!/usr/bin/env python3

"""
GHR CLI - A Python utility for managing command-line tools from GitHub releases
Features:
- Automatic download URL detection from GitHub releases
- Versioned installations with symbolic links
- Simple YAML configuration
- Clean old versions while keeping N most recent
"""

try:
    from version import __version__
except ImportError:
    __version__ = "0.0.0-unknown"

from .core.manager import ToolManager
from .core.operations import list_tools, install_tool, rollback_tool, clean_old_versions
from .utils.cache import clear_cache, get_cache_info
from .cli.cli import run_cli
