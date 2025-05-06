#!/usr/bin/env python3

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..utils.system import get_real_home

# Type definitions
ConfigDict = Dict[str, Union[List[Dict[str, str]], Dict[str, Union[int, bool]]]]

# Default paths
DEFAULT_CONFIG_PATH = "toolset.yaml"
DEFAULT_KEEP_VERSIONS = 2
DEFAULT_AUTO_CLEANUP = False
DEFAULT_CACHE_ENABLED = True
DEFAULT_CACHE_EXPIRY = 3600  # Cache expiry in seconds (1 hour)


def ensure_user_config_dir() -> str:
    """Ensure the user's config directory exists"""
    user_config_dir = os.path.join(get_real_home(), ".config/ghr-cli")
    os.makedirs(user_config_dir, exist_ok=True)
    return user_config_dir


def find_config_file(config_path: str = DEFAULT_CONFIG_PATH) -> str:
    """
    Find the configuration file by checking multiple locations:
    1. Specified path from command line
    2. Current directory
    3. Same directory as the executable
    4. User config directory (~/.config/ghr-cli/)
    5. System-wide location (/etc/ghr-cli)
    """
    # Check if specified path exists
    if os.path.isfile(config_path):
        return config_path

    # Check in the current directory
    if os.path.isfile(os.path.join(os.getcwd(), DEFAULT_CONFIG_PATH)):
        return os.path.join(os.getcwd(), DEFAULT_CONFIG_PATH)

    # Check in the same directory as the executable
    exec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.isfile(os.path.join(exec_dir, DEFAULT_CONFIG_PATH)):
        return os.path.join(exec_dir, DEFAULT_CONFIG_PATH)

    # Check in user config directory
    user_config_dir = os.path.join(get_real_home(), ".config/ghr-cli")
    user_config = os.path.join(user_config_dir, DEFAULT_CONFIG_PATH)
    if os.path.isfile(user_config):
        return user_config

    # Check in system-wide location
    system_config = "/etc/ghr-cli/toolset.yaml"
    if os.path.isfile(system_config):
        return system_config

    # Return the original path (will likely fail when used)
    return config_path


def create_default_config(config_path: str) -> ConfigDict:
    """Create a default configuration file"""
    default_config = {
        "tools": [],
        "options": {
            "keep_versions": DEFAULT_KEEP_VERSIONS,
            "auto_cleanup": DEFAULT_AUTO_CLEANUP,
            "cache_enabled": DEFAULT_CACHE_ENABLED,
            "cache_expiry": DEFAULT_CACHE_EXPIRY,
        },
    }

    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)

    # Write the default config
    try:
        with open(config_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)
        return default_config
    except Exception as e:
        raise IOError(f"Failed to create config file: {e}")


def load_config(config_path: str) -> ConfigDict:
    """Load the configuration from the specified path"""
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        # Set default options if they don't exist
        if "options" not in config:
            config["options"] = {}

        if "keep_versions" not in config["options"]:
            config["options"]["keep_versions"] = DEFAULT_KEEP_VERSIONS

        if "auto_cleanup" not in config["options"]:
            config["options"]["auto_cleanup"] = DEFAULT_AUTO_CLEANUP

        if "cache_enabled" not in config["options"]:
            config["options"]["cache_enabled"] = DEFAULT_CACHE_ENABLED

        if "cache_expiry" not in config["options"]:
            config["options"]["cache_expiry"] = DEFAULT_CACHE_EXPIRY

        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found at: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML: {e}")


def save_config(config: ConfigDict, config_path: str) -> None:
    """Save the configuration to the specified path"""
    try:
        with open(config_path, "w") as file:
            yaml.dump(config, file, default_flow_style=False)
    except Exception as e:
        raise IOError(f"Failed to save config file: {e}")
