#!/usr/bin/env python3

import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from .system import get_real_home

# Define history file location
HISTORY_DIR = os.path.join(get_real_home(), ".config/ghr-cli/history")
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.json")

# Define operation types
OP_ADD = "add"
OP_REMOVE = "remove"
OP_UPDATE = "update"
OP_INSTALL = "install"
OP_ROLLBACK = "rollback"
OP_CLEAN = "clean"


def ensure_history_dir() -> None:
    """Ensure the history directory exists"""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def load_history() -> List[Dict[str, Any]]:
    """Load history from the history file"""
    ensure_history_dir()
    
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        else:
            return []
    except Exception as e:
        print(f"Warning: Failed to load history: {e}")
        return []


def save_history(history: List[Dict[str, Any]]) -> None:
    """Save history to the history file"""
    ensure_history_dir()
    
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save history: {e}")


def add_history_entry(
    operation: str,
    repos: Union[str, List[str]],
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> Dict[str, Any]:
    """
    Add a new entry to the history log
    
    Args:
        operation: The type of operation (add, remove, update, etc.)
        repos: The repository or list of repositories affected
        details: Additional details about the operation
        success: Whether the operation was successful
    
    Returns:
        The created history entry
    """
    history = load_history()
    
    # Convert string to list if needed
    if isinstance(repos, str):
        repos = [repos]
    
    # Create new entry
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation,
        "repos": repos,
        "success": success,
        "details": details or {}
    }
    
    # Add to history
    history.append(entry)
    
    # Save updated history
    save_history(history)
    
    return entry


def get_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get history entries, sorted by most recent first
    
    Args:
        limit: Maximum number of entries to return (None for all)
    
    Returns:
        List of history entries
    """
    history = load_history()
    
    # Sort by timestamp (most recent first)
    sorted_history = sorted(history, key=lambda x: x["timestamp"], reverse=True)
    
    if limit is not None:
        return sorted_history[:limit]
    return sorted_history


def clear_history() -> bool:
    """Clear all history entries"""
    ensure_history_dir()
    
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        return True
    except Exception as e:
        print(f"Warning: Failed to clear history: {e}")
        return False


def format_history_entry(entry: Dict[str, Any]) -> str:
    """Format a history entry for display"""
    date_str = entry["date"]
    operation = entry["operation"].upper()
    repos = ", ".join(entry["repos"])
    
    if operation == OP_ADD.upper():
        action = f"Added repo(s) to configuration"
    elif operation == OP_REMOVE.upper():
        action = f"Removed repo(s) from configuration"
    elif operation == OP_UPDATE.upper():
        action = f"Updated repo(s)"
        if "from_version" in entry["details"] and "to_version" in entry["details"]:
            from_ver = entry["details"]["from_version"]
            to_ver = entry["details"]["to_version"]
            action = f"Updated from {from_ver} to {to_ver}"
    elif operation == OP_INSTALL.upper():
        action = f"Installed version"
        if "version" in entry["details"]:
            action = f"Installed version {entry['details']['version']}"
    elif operation == OP_ROLLBACK.upper():
        action = f"Rolled back"
        if "from_version" in entry["details"] and "to_version" in entry["details"]:
            from_ver = entry["details"]["from_version"]
            to_ver = entry["details"]["to_version"]
            action = f"Rolled back from {from_ver} to {to_ver}"
    elif operation == OP_CLEAN.upper():
        action = f"Cleaned old versions"
        if "removed_versions" in entry["details"]:
            removed = entry["details"]["removed_versions"]
            removed_str = ", ".join(removed) if removed else "none"
            action = f"Cleaned old versions: removed {removed_str}"
    
    status = "SUCCESS" if entry["success"] else "FAILED"
    
    return f"{date_str} | {status} | {operation} | {repos} | {action}"