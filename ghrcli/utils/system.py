#!/usr/bin/env python3

import os
import subprocess
from typing import List
from colorama import Fore, Style


def get_real_home() -> str:
    """Get the real user's home directory even when running with sudo"""
    if "SUDO_USER" in os.environ and os.environ.get("HOME") == "/root":
        real_user = os.environ["SUDO_USER"]
        return os.path.expanduser(f"~{real_user}")
    return os.path.expanduser("~")


def check_sudo_access() -> bool:
    """Check if the script has sudo access"""
    try:
        # Try to run a simple sudo command with timeout to avoid hanging
        subprocess.run(
            ["sudo", "-n", "true"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return True
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False


def run_sudo_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command with sudo if available, otherwise show warning"""
    try:
        if os.geteuid() == 0:  # Already running as root
            return subprocess.run(cmd, check=check)
        else:
            sudo_cmd = ["sudo"] + cmd
            return subprocess.run(sudo_cmd, check=check)
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}❌ Command failed: {' '.join(cmd)}{Style.RESET_ALL}")
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        raise
