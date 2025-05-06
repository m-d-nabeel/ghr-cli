#!/usr/bin/env python3

import argparse
import sys
import os
from colorama import Fore, Style

from ..utils.cache import clear_cache, get_cache_info
from ..utils.config import (
    DEFAULT_CONFIG_PATH,
    ensure_user_config_dir,
    create_default_config,
)
from ..core.manager import ToolManager
from ..core.operations import (
    list_tools,
    install_tool,
    rollback_tool,
    clean_old_versions,
    add_tool,
    remove_tool,
    show_history,
    clear_history,
)
from ..utils.system import check_sudo_access

try:
    from version import __version__
except ImportError:
    __version__ = "0.0.0-unknown"


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description=f"GHR CLI v{__version__} - A utility for managing command-line tools from GitHub releases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean old versions according to keep_versions setting",
    )
    parser.add_argument(
        "--install",
        nargs="?",
        const="all",
        help="Install all tools or specify a repository (must already be in config)",
    )
    parser.add_argument(
        "--add",
        help="Add a new repository to the toolset configuration (format: owner/repo)",
    )
    parser.add_argument(
        "--install-after-add",
        action="store_true",
        help="Automatically install a tool after adding it with --add",
    )
    parser.add_argument(
        "--remove",
        help="Remove a repository from the toolset configuration (format: owner/repo)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all configured tools and their versions",
    )
    parser.add_argument(
        "--rollback", help="Rollback to previous version of a tool (specify repo)"
    )
    parser.add_argument(
        "--check-sudo", action="store_true", help="Check if sudo access is available"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the download and API response cache",
    )
    parser.add_argument(
        "--cache-info", "--cache-dir",
        action="store_true",
        help="Show cache information and statistics",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Disable caching for this run"
    )
    parser.add_argument(
        "--force-cache",
        action="store_true",
        help="Force caching for this run, ignoring config setting",
    )
    parser.add_argument(
        "--version", action="store_true", help="Show the version and exit"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize a default config file in the user's config directory",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show the history of tool operations",
    )
    parser.add_argument(
        "--history-limit",
        type=int,
        metavar="N",
        help="Limit history to N entries (used with --history)",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear the operation history logs",
    )

    return parser.parse_args()


def handle_init_command():
    """Handle the --init command to create a default config file"""
    user_config_dir = ensure_user_config_dir()
    user_config_path = os.path.join(user_config_dir, DEFAULT_CONFIG_PATH)

    if os.path.isfile(user_config_path):
        print(
            f"{Fore.YELLOW}Config file already exists at {user_config_path}{Style.RESET_ALL}"
        )
        return

    # Create a default config file
    try:
        create_default_config(user_config_path)
        print(
            f"{Fore.GREEN}✅ Created default config file at {user_config_path}{Style.RESET_ALL}"
        )
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to create config file: {e}{Style.RESET_ALL}")
        sys.exit(1)


def handle_cache_info():
    """Handle the --cache-info command"""
    cache_info = get_cache_info()
    print(f"Cache directory: {cache_info['path']}")

    if cache_info["exists"]:
        print(f"Cache size: {cache_info['size_bytes'] / (1024*1024):.2f} MB")
        print(f"API cache entries: {cache_info['api_entries']}")
        print(f"Download cache entries: {cache_info['download_entries']}")
    else:
        print("Cache directory does not exist yet")


def run_cli():
    """Run the command-line interface"""
    args = parse_args()

    # Show version and exit if requested
    if args.version:
        print(f"GHR CLI v{__version__}")
        return

    # Initialize config file if requested
    if args.init:
        handle_init_command()
        return

    # Handle cache operations
    if args.clear_cache:
        if clear_cache():
            print(f"{Fore.GREEN}✅ Cache successfully cleared{Style.RESET_ALL}")
        else:
            print(
                f"{Fore.YELLOW}ℹ️ No cache directory found or failed to clear cache{Style.RESET_ALL}"
            )
        return

    if args.cache_info:
        handle_cache_info()
        return

    # Find the config file and initialize the CLI
    try:
        # Handle history operations if requested (don't need config for these)
        if args.history:
            show_history(args.history_limit)
            return
            
        if args.clear_history:
            clear_history()
            return
            
        manager = ToolManager(args.config)
        print(f"Using configuration file: {manager.config_path}")

        # Override cache settings if specified on command line
        if args.no_cache:
            manager.cache_enabled = False
            print(f"{Fore.YELLOW}ℹ️ Caching disabled for this run{Style.RESET_ALL}")
        elif args.force_cache:
            manager.cache_enabled = True
            print(f"{Fore.GREEN}ℹ️ Caching enabled for this run{Style.RESET_ALL}")

        # If --check-sudo is specified, just check and report
        if args.check_sudo:
            if check_sudo_access():
                print(f"{Fore.GREEN}✓ Sudo access is available{Style.RESET_ALL}")
            else:
                print(
                    f"{Fore.YELLOW}⚠️ Sudo access is not available. Some operations may require sudo privileges.{Style.RESET_ALL}"
                )
            return

        # Process the commands
        if args.list:
            list_tools(manager)
        elif args.rollback:
            rollback_tool(manager, args.rollback)
        elif args.add:
            add_tool(manager, args.add, install_after=args.install_after_add)
        elif args.remove:
            remove_tool(manager, args.remove)
        elif args.install:
            if args.install == "all":
                install_tool(manager, prompt=False)
            else:
                install_tool(manager, args.install, prompt=False)
        elif args.clean:
            clean_old_versions(manager)
        else:
            # Default behavior: check for updates and prompt to install
            install_tool(manager)

            # Reminder about cleaning if not auto-cleaning
            auto_cleanup = manager.config.get("options", {}).get("auto_cleanup", False)
            if not auto_cleanup:
                print(
                    f"\n{Fore.CYAN}ℹ️  Tip: Run with --clean to remove old versions{Style.RESET_ALL}"
                )

    except FileNotFoundError as e:
        print(f"{Fore.RED}❌ {e}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}Use --init to create a default configuration file{Style.RESET_ALL}"
        )
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
        sys.exit(1)


if __name__ == "__main__":
    run_cli()
