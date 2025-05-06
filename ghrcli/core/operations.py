#!/usr/bin/env python3

import os
import sys
import platform
import requests
from typing import Optional, List
from colorama import Fore, Style

from ..utils.system import check_sudo_access
from ..utils.history import (
    add_history_entry,
    clear_history as clear_history_util,
    get_history,
    format_history_entry,
    OP_ADD,
    OP_REMOVE,
    OP_UPDATE,
    OP_INSTALL,
    OP_ROLLBACK,
    OP_CLEAN,
)
from .manager import ToolManager


def list_tools(manager: ToolManager) -> None:
    """List all tools in the config with their current and latest versions"""
    tools = manager.config.get("tools", [])

    print(
        f"\n{Fore.CYAN}{Style.BRIGHT}Tools in {manager.config_path}:{Style.RESET_ALL}\n"
    )

    if not tools:
        print(f"{Fore.YELLOW}No tools configured.{Style.RESET_ALL}")
        return

    for tool in tools:
        repo = tool.get("repo", "")
        current_version = tool.get("version", "")
        install_path = tool.get("install_path", "/opt/" + repo.split("/")[-1])

        version_dir = os.path.join(install_path, current_version)
        current_link = os.path.join(install_path, "current")
        is_installed = os.path.exists(version_dir)
        is_linked = os.path.exists(current_link) and os.path.islink(current_link)

        if is_installed:
            status = f"{Fore.GREEN}[INSTALLED]{Style.RESET_ALL}"
        else:
            status = f"{Fore.YELLOW}[NOT INSTALLED]{Style.RESET_ALL}"

        print(f"{Fore.WHITE}{Style.BRIGHT}{repo}{Style.RESET_ALL} {status}")
        print(f"  Current version: {current_version}")
        print(f"  Install path: {install_path}")

        if is_installed:
            try:
                real_path = os.path.realpath(current_link) if is_linked else None
                if real_path:
                    linked_version = os.path.basename(real_path)
                    print(f"  Current symlink: → {linked_version}")

                # List all available versions
                versions = []
                for item in os.listdir(install_path):
                    item_path = os.path.join(install_path, item)
                    if (
                        os.path.isdir(item_path)
                        and not os.path.islink(item_path)
                        and item != "current"
                    ):
                        versions.append(item)

                if versions:
                    import re

                    versions.sort(
                        key=lambda s: [
                            int(u) if u.isdigit() else u.lower()
                            for u in re.split(r"(\d+)", s)
                        ],
                        reverse=True,
                    )
                    print(f"  Available versions: {', '.join(versions)}")
            except Exception:
                pass

        # Get the latest version from GitHub
        latest, _ = manager._get_latest_release(repo)
        if latest:
            if latest == current_version:
                print(
                    f"  Latest version: {latest} {Fore.GREEN}(up to date){Style.RESET_ALL}"
                )
            else:
                print(
                    f"  Latest version: {latest} {Fore.YELLOW}(update available){Style.RESET_ALL}"
                )

        print()


def install_tool(
    manager: ToolManager, repo_to_install: Optional[str] = None, prompt: bool = True
) -> None:
    """Install a tool or all tools"""
    tools = manager.config.get("tools", [])

    # Check if we need sudo access for any tool
    sudo_needed = False
    for tool in tools:
        repo = tool.get("repo", "")
        if repo_to_install and repo != repo_to_install:
            continue

        install_path = tool.get("install_path", "/opt/" + repo.split("/")[-1])
        # If install_path starts with /opt, we likely need sudo
        if install_path.startswith("/opt/") or not os.access(
            os.path.dirname(install_path), os.W_OK
        ):
            sudo_needed = True
            break

    # If we need sudo, check if we have it
    if sudo_needed and not check_sudo_access():
        print(
            f"{Fore.YELLOW}⚠️  This operation requires sudo privileges to install tools to system directories.{Style.RESET_ALL}"
        )
        print(f"{Fore.YELLOW}Please run this command with sudo.{Style.RESET_ALL}")
        if not prompt:
            return
        response = input("Do you want to continue anyway? (y/N) ")
        if response.lower() != "y":
            return

    for tool in tools:
        repo = tool.get("repo", "")

        # Skip if we're installing a specific tool and this isn't it
        if repo_to_install and repo != repo_to_install:
            continue

        current_version = tool.get("version", "")

        # Get the latest version from GitHub
        latest, release_data = manager._get_latest_release(repo)
        if not latest:
            # Log failed attempt to fetch release
            add_history_entry(
                OP_INSTALL,
                repo,
                details={"reason": "Failed to fetch release information"},
                success=False,
            )
            continue

        install_path = tool.get("install_path", "/opt/" + repo.split("/")[-1])
        version_dir = os.path.join(install_path, latest)
        version_exists = os.path.exists(version_dir)

        if latest == current_version and version_exists:
            print(
                f"{Fore.GREEN}✔ {repo} is up to date (version {current_version}){Style.RESET_ALL}"
            )
            continue

        if latest == current_version and not version_exists:
            print(
                f"{Fore.YELLOW}⚠️ {repo} version {current_version} listed in config but not installed{Style.RESET_ALL}"
            )
        else:
            print(
                f"{Fore.YELLOW}⬆ {repo} update available: {current_version} → {latest}{Style.RESET_ALL}"
            )

        if prompt:
            response = input(f"Do you want to install {repo} version {latest}? (y/N) ")
            if response.lower() != "y":
                continue

        print(f"📦 Installing {repo} version {latest}...")

        # If no assets in the release data, fetch them
        if not release_data or "assets" not in release_data:
            print(f"{Fore.RED}❌ No assets found for {repo}:{latest}{Style.RESET_ALL}")
            # Log failed attempt to find assets
            add_history_entry(
                OP_INSTALL,
                repo,
                details={"version": latest, "reason": "No assets found in release"},
                success=False,
            )
            continue

        assets = release_data.get("assets", [])

        # Detect current platform and architecture
        current_platform = sys.platform
        if current_platform.startswith("linux"):
            current_platform = "linux"
        elif current_platform.startswith("darwin"):
            current_platform = "darwin"
        elif current_platform.startswith("win"):
            current_platform = "windows"

        current_arch = platform.machine().lower()
        if current_arch in ["x86_64", "amd64"]:
            current_arch = "x86_64"
        elif current_arch in ["aarch64", "arm64"]:
            current_arch = "aarch64"

        asset_url = manager._find_asset_url(
            repo, assets, current_platform, current_arch
        )

        if not asset_url:
            print(
                f"{Fore.RED}❌ Could not find suitable download for {repo}:{latest}{Style.RESET_ALL}"
            )
            # Log failed attempt to find suitable asset
            add_history_entry(
                OP_INSTALL,
                repo,
                details={
                    "version": latest,
                    "reason": f"No suitable asset found for {current_platform}/{current_arch}",
                },
                success=False,
            )
            continue

        # Download the asset
        print(f"⬇️  Downloading from {asset_url}")
        download_path = None

        try:
            # Check if we have a cached download
            if manager.cache_enabled:
                from ..utils.cache import get_cached_download, cache_download

                cached_download = get_cached_download(asset_url)
                if cached_download:
                    print(f"📦 Using cached download for {repo}")
                    download_path = cached_download
            else:
                cached_download = None

            if not cached_download:
                response = requests.get(asset_url, stream=True)
                response.raise_for_status()

                # Determine the filename
                import re

                content_disposition = response.headers.get("content-disposition")
                if content_disposition and "filename=" in content_disposition:
                    filename = re.findall("filename=(.+)", content_disposition)[0]
                else:
                    filename = os.path.basename(asset_url)

                # Remove quotes if present
                filename = filename.strip("'\"")

                # Create temp file
                download_path = os.path.join(os.getcwd(), filename)

                # Download with progress
                total_size = int(response.headers.get("content-length", 0))
                block_size = 1024  # 1 KB
                progress_bar_length = 30

                with open(download_path, "wb") as f:
                    for i, data in enumerate(response.iter_content(block_size)):
                        f.write(data)

                        if total_size > 0:
                            downloaded = min(i * block_size, total_size)
                            progress = int(
                                progress_bar_length * downloaded / total_size
                            )
                            sys.stdout.write(
                                f"\r[{'=' * progress}{' ' * (progress_bar_length - progress)}] {downloaded}/{total_size} bytes "
                            )
                            sys.stdout.flush()

                print()  # Newline after progress bar

                # Cache the download if caching is enabled
                if manager.cache_enabled:
                    from ..utils.cache import cache_download

                    cache_download(asset_url, download_path)

            # Check if we need sudo for this path
            needs_sudo = not os.access(os.path.dirname(version_dir), os.W_OK)

            # Create the version directory
            try:
                if needs_sudo:
                    from ..utils.system import run_sudo_command

                    run_sudo_command(["mkdir", "-p", version_dir])
                else:
                    os.makedirs(version_dir, exist_ok=True)
            except Exception as e:
                print(f"{Fore.RED}❌ Failed to create directory {version_dir}: {e}")
                if needs_sudo:
                    print(
                        f"{Fore.YELLOW}This operation requires sudo privileges. Please run with sudo.{Style.RESET_ALL}"
                    )
                # Log failed attempt to create directory
                add_history_entry(
                    OP_INSTALL,
                    repo,
                    details={
                        "version": latest,
                        "error": f"Failed to create directory: {e}",
                        "needs_sudo": needs_sudo,
                    },
                    success=False,
                )
                continue

            # Detect whether we need to strip components based on repo and archive
            strip_components = manager._detect_strip_components(repo, download_path)

            # Extract the archive
            print(f"📂 Extracting to {version_dir}...")
            if not manager._extract_archive(
                download_path, version_dir, strip_components
            ):
                print(f"{Fore.RED}❌ Failed to extract archive{Style.RESET_ALL}")
                # Log failed attempt to extract archive
                add_history_entry(
                    OP_INSTALL,
                    repo,
                    details={"version": latest, "error": "Failed to extract archive"},
                    success=False,
                )
                continue

            # Create the symbolic link
            current_link = os.path.join(install_path, "current")
            if not manager._create_symlink(version_dir, current_link):
                print(f"{Fore.RED}❌ Failed to create symbolic link{Style.RESET_ALL}")
                # Log failed attempt to create symlink
                add_history_entry(
                    OP_INSTALL,
                    repo,
                    details={
                        "version": latest,
                        "error": "Failed to create symbolic link",
                    },
                    success=False,
                )
                continue

            print(f"{Fore.GREEN}✅ {repo} updated to version {latest}{Style.RESET_ALL}")

            # Track if this was an update or a fresh install
            is_update = current_version and current_version != latest

            # Update the version in the config
            tool["version"] = latest
            manager._save_config()
            print(f"{Fore.GREEN}✅ Updated version in config file{Style.RESET_ALL}")

            # Log the successful installation/update
            if is_update:
                add_history_entry(
                    OP_UPDATE,
                    repo,
                    details={
                        "from_version": current_version,
                        "to_version": latest,
                        "install_path": install_path,
                    },
                    success=True,
                )
            else:
                add_history_entry(
                    OP_INSTALL,
                    repo,
                    details={"version": latest, "install_path": install_path},
                    success=True,
                )

            # Clean old versions if auto_cleanup is enabled
            if manager.config.get("options", {}).get("auto_cleanup", False):
                keep_versions = manager.config.get("options", {}).get(
                    "keep_versions", 2
                )
                manager._clean_old_versions(install_path, latest, keep_versions)

        except Exception as e:
            print(f"{Fore.RED}❌ Failed to install {repo}: {e}{Style.RESET_ALL}")
            # Log the failed installation
            add_history_entry(
                OP_INSTALL,
                repo,
                details={"version": latest, "error": str(e)},
                success=False,
            )
        finally:
            # Clean up the downloaded file if it's not a cached file
            if download_path and os.path.exists(download_path) and not cached_download:
                os.remove(download_path)


def rollback_tool(manager: ToolManager, repo: str) -> None:
    """Rollback a tool to the previous version"""
    tools = manager.config.get("tools", [])

    for tool in tools:
        if tool.get("repo", "") == repo:
            install_path = tool.get("install_path", "/opt/" + repo.split("/")[-1])
            current_version = tool.get("version", "")
            current_link = os.path.join(install_path, "current")

            try:
                # List all available versions
                import re

                versions = []
                for item in os.listdir(install_path):
                    item_path = os.path.join(install_path, item)
                    if (
                        os.path.isdir(item_path)
                        and not os.path.islink(item_path)
                        and item != "current"
                    ):
                        versions.append(item)

                if not versions:
                    print(f"{Fore.RED}❌ No versions found for {repo}{Style.RESET_ALL}")
                    # Log failed rollback attempt - no versions found
                    add_history_entry(
                        OP_ROLLBACK,
                        repo,
                        details={
                            "current_version": current_version,
                            "reason": "No versions found",
                        },
                        success=False,
                    )
                    return

                # Sort versions (assuming semantic versioning) in descending order
                versions.sort(
                    key=lambda s: [
                        int(u) if u.isdigit() else u.lower()
                        for u in re.split(r"(\d+)", s)
                    ],
                    reverse=True,
                )

                # Find the current version index
                try:
                    current_idx = versions.index(current_version)
                    # If it's already the oldest version, can't rollback
                    if current_idx >= len(versions) - 1:
                        print(
                            f"{Fore.YELLOW}⚠️ {repo} is already at the oldest version ({current_version}){Style.RESET_ALL}"
                        )
                        # Log failed rollback attempt - already at oldest version
                        add_history_entry(
                            OP_ROLLBACK,
                            repo,
                            details={
                                "current_version": current_version,
                                "reason": "Already at oldest version",
                            },
                            success=False,
                        )
                        return

                    # Get the previous version
                    previous_version = versions[current_idx + 1]
                except ValueError:
                    # If current version not found, use the second newest
                    if len(versions) < 2:
                        print(
                            f"{Fore.YELLOW}⚠️ No older version available to rollback to{Style.RESET_ALL}"
                        )
                        # Log failed rollback attempt - no older version available
                        add_history_entry(
                            OP_ROLLBACK,
                            repo,
                            details={
                                "current_version": current_version,
                                "reason": "No older version available",
                            },
                            success=False,
                        )
                        return
                    previous_version = versions[1]

                print(
                    f"⬇️  Rolling back {repo} from {current_version} to {previous_version}..."
                )

                # Update the symbolic link
                previous_path = os.path.join(install_path, previous_version)
                if not manager._create_symlink(previous_path, current_link):
                    print(
                        f"{Fore.RED}❌ Failed to update symbolic link{Style.RESET_ALL}"
                    )
                    # Log failed rollback attempt - failed to update symlink
                    add_history_entry(
                        OP_ROLLBACK,
                        repo,
                        details={
                            "from_version": current_version,
                            "to_version": previous_version,
                            "reason": "Failed to update symbolic link",
                        },
                        success=False,
                    )
                    return

                # Update the version in the config
                tool["version"] = previous_version
                manager._save_config()

                print(
                    f"{Fore.GREEN}✅ Successfully rolled back to version {previous_version}{Style.RESET_ALL}"
                )

                # Log successful rollback
                add_history_entry(
                    OP_ROLLBACK,
                    repo,
                    details={
                        "from_version": current_version,
                        "to_version": previous_version,
                        "install_path": install_path,
                    },
                    success=True,
                )

            except Exception as e:
                print(f"{Fore.RED}❌ Failed to rollback {repo}: {e}{Style.RESET_ALL}")
                # Log failed rollback attempt due to exception
                add_history_entry(
                    OP_ROLLBACK,
                    repo,
                    details={"current_version": current_version, "error": str(e)},
                    success=False,
                )

            return

    print(f"{Fore.RED}❌ Tool {repo} not found in the configuration{Style.RESET_ALL}")
    # Log failed rollback attempt - repo not found
    add_history_entry(
        OP_ROLLBACK,
        repo,
        details={"reason": "Repository not found in configuration"},
        success=False,
    )


def clean_old_versions(manager: ToolManager) -> None:
    """Clean old versions of all tools"""
    tools = manager.config.get("tools", [])
    keep_versions = manager.config.get("options", {}).get("keep_versions", 2)
    clean_results = []

    for tool in tools:
        repo = tool.get("repo", "")
        current_version = tool.get("version", "")
        install_path = tool.get("install_path", "/opt/" + repo.split("/")[-1])

        if os.path.exists(install_path):
            # Collect all directories (excluding the 'current' symlink)
            versions = []
            try:
                for item in os.listdir(install_path):
                    item_path = os.path.join(install_path, item)
                    if (
                        os.path.isdir(item_path)
                        and not os.path.islink(item_path)
                        and item != "current"
                    ):
                        versions.append(item)

                # Sort versions in descending order (assuming semantic versioning)
                import re

                versions.sort(
                    key=lambda s: [
                        int(u) if u.isdigit() else u.lower()
                        for u in re.split(r"(\d+)", s)
                    ],
                    reverse=True,
                )

                # Track versions to keep and those to remove
                versions_to_keep = [current_version]
                for version in versions:
                    if (
                        version != current_version
                        and len(versions_to_keep) < keep_versions
                    ):
                        versions_to_keep.append(version)

                versions_to_remove = [v for v in versions if v not in versions_to_keep]

                # Pass to manager for actual cleaning
                manager._clean_old_versions(
                    install_path, current_version, keep_versions
                )

                # Track result for history logging
                clean_results.append(
                    {
                        "repo": repo,
                        "kept_versions": versions_to_keep,
                        "removed_versions": versions_to_remove,
                        "success": True,
                    }
                )
            except Exception as e:
                print(
                    f"{Fore.RED}❌ Failed to clean versions for {repo}: {e}{Style.RESET_ALL}"
                )
                clean_results.append({"repo": repo, "error": str(e), "success": False})

    # Log the cleaning operation
    for result in clean_results:
        repo = result["repo"]
        if result.get("success", False):
            add_history_entry(
                OP_CLEAN,
                repo,
                details={
                    "kept_versions": result.get("kept_versions", []),
                    "removed_versions": result.get("removed_versions", []),
                },
                success=True,
            )
        else:
            add_history_entry(
                OP_CLEAN,
                repo,
                details={"error": result.get("error", "Unknown error")},
                success=False,
            )


def add_tool(
    manager: ToolManager,
    repo: str,
    install_path: Optional[str] = None,
    install_after: bool = False,
) -> bool:
    """Add a tool to the configuration and optionally install it"""
    tools = manager.config.get("tools", [])

    # Check if the tool is already in the config
    for tool in tools:
        if tool.get("repo", "") == repo:
            print(
                f"{Fore.YELLOW}⚠️  Tool {repo} is already in the configuration{Style.RESET_ALL}"
            )
            return False

    # Validate repository format (should be owner/repo)
    if "/" not in repo or len(repo.split("/")) != 2:
        print(
            f"{Fore.RED}❌ Invalid repository format: {repo}. Should be owner/repo{Style.RESET_ALL}"
        )
        return False

    # Try to fetch the latest release to verify the repository exists
    latest, _ = manager._get_latest_release(repo)
    if not latest:
        print(
            f"{Fore.RED}❌ Failed to fetch release information for {repo}. Is the repository correct and has releases?{Style.RESET_ALL}"
        )
        # Log failed attempt
        add_history_entry(
            OP_ADD,
            repo,
            details={"reason": "Failed to fetch release information"},
            success=False,
        )
        return False

    # Determine install path if not provided
    if not install_path:
        repo_name = repo.split("/")[1]
        install_path = f"/opt/{repo_name}"

    # Add the tool to configuration
    new_tool = {"repo": repo, "version": latest, "install_path": install_path}

    tools.append(new_tool)
    manager.config["tools"] = tools

    # Save the updated configuration
    try:
        manager._save_config()
        print(
            f"{Fore.GREEN}✅ Added {repo} to configuration with version {latest}{Style.RESET_ALL}"
        )
        print(f"  Install path: {install_path}")

        # Log successful add operation
        add_history_entry(
            OP_ADD,
            repo,
            details={"version": latest, "install_path": install_path},
            success=True,
        )

        # Install the tool if requested
        if install_after:
            install_tool(manager, repo, prompt=False)

        return True
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to save the configuration: {e}{Style.RESET_ALL}")

        # Log failure
        add_history_entry(
            OP_ADD,
            repo,
            details={"version": latest, "install_path": install_path, "error": str(e)},
            success=False,
        )

        return False


def remove_tool(manager: ToolManager, repo: str) -> bool:
    """Remove a tool from the configuration"""
    tools = manager.config.get("tools", [])

    # Check if the tool is in the config
    found = False
    for i, tool in enumerate(tools):
        if tool.get("repo", "") == repo:
            found = True
            version = tool.get("version", "unknown")
            install_path = tool.get("install_path", f"/opt/{repo.split('/')[-1]}")

            # Confirm removal
            print(
                f"{Fore.YELLOW}⚠️  About to remove {repo} from configuration:{Style.RESET_ALL}"
            )
            print(f"  Install path: {install_path}")
            print(f"  Version: {version}")
            response = input(f"Are you sure you want to remove this tool? (y/N) ")

            if response.lower() != "y":
                print(f"{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")
                return False

            # Remove the tool
            tools.pop(i)
            manager.config["tools"] = tools

            # Save the updated configuration
            try:
                manager._save_config()
                print(
                    f"{Fore.GREEN}✅ Removed {repo} from configuration{Style.RESET_ALL}"
                )
                print(
                    f"{Fore.YELLOW}Note: The installed files were not removed. You can remove them manually.{Style.RESET_ALL}"
                )

                # Log the removal
                add_history_entry(
                    OP_REMOVE,
                    repo,
                    details={
                        "version": version,
                        "install_path": install_path,
                    },
                    success=True,
                )

                return True
            except Exception as e:
                print(
                    f"{Fore.RED}❌ Failed to save the configuration: {e}{Style.RESET_ALL}"
                )

                # Log the failed removal attempt
                add_history_entry(
                    OP_REMOVE,
                    repo,
                    details={
                        "version": version,
                        "install_path": install_path,
                        "error": str(e),
                    },
                    success=False,
                )

                return False

    if not found:
        print(
            f"{Fore.RED}❌ Tool {repo} not found in the configuration{Style.RESET_ALL}"
        )

        # Log the attempt to remove a non-existent tool
        add_history_entry(
            OP_REMOVE,
            repo,
            details={"reason": "Repository not found in configuration"},
            success=False,
        )

        return False


def show_history(limit: Optional[int] = None) -> None:
    """Show the operation history"""
    history = get_history(limit)

    if not history:
        print(f"{Fore.YELLOW}No history entries found.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Operation History:{Style.RESET_ALL}\n")

    for entry in history:
        formatted = format_history_entry(entry)

        # Color-code based on success status
        if entry["success"]:
            print(f"{Fore.GREEN}{formatted}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}{formatted}{Style.RESET_ALL}")

    print(f"\nTotal entries: {len(history)}")


def clear_history() -> None:
    """Clear the operation history"""
    print(f"{Fore.YELLOW}About to clear all history entries.{Style.RESET_ALL}")
    response = input("Are you sure you want to continue? (y/N) ")

    if response.lower() != "y":
        print(f"{Fore.YELLOW}Operation cancelled.{Style.RESET_ALL}")
        return

    if clear_history_util():
        print(f"{Fore.GREEN}✅ History cleared successfully.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Failed to clear history.{Style.RESET_ALL}")
