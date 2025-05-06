#!/usr/bin/env python3

import os
import re
import shutil
import tempfile
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import requests
from colorama import Fore, Style

from ..utils.config import ConfigDict, find_config_file, load_config, save_config
from ..utils.cache import (
    cache_api_response,
    get_cached_api_response,
    get_cached_download,
    cache_download,
)
from ..utils.system import run_sudo_command


class ToolManager:
    """Core class for managing GitHub release-based tools"""

    def __init__(self, config_path: str):
        self.config_path = find_config_file(config_path)
        self.config = self._load_config()
        # Initialize cache settings
        self.cache_enabled = self.config.get("options", {}).get("cache_enabled", True)
        self.cache_expiry = self.config.get("options", {}).get("cache_expiry", 3600)

    def _load_config(self) -> ConfigDict:
        """Load the configuration file"""
        try:
            return load_config(self.config_path)
        except FileNotFoundError as e:
            print(f"{Fore.RED}❌ {e}{Style.RESET_ALL}")
            print(
                f"{Fore.YELLOW}Run with --init to create a default config file{Style.RESET_ALL}"
            )
            raise
        except ValueError as e:
            print(f"{Fore.RED}❌ {e}{Style.RESET_ALL}")
            raise

    def _save_config(self) -> None:
        """Save the configuration file"""
        try:
            save_config(self.config, self.config_path)
        except IOError as e:
            print(f"{Fore.RED}❌ {e}{Style.RESET_ALL}")
            raise

    def _get_latest_release(self, repo: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Get the latest release information from GitHub"""
        # Check if we have a cached response
        if self.cache_enabled:
            cached_data = get_cached_api_response(repo, self.cache_expiry)
            if cached_data:
                print(
                    f"📦 Using cached release information for {Fore.CYAN}{repo}{Style.RESET_ALL}"
                )
                tag_name = cached_data.get("tag_name", "")
                version = re.sub(r"^v", "", tag_name)
                if not version:
                    print(
                        f"{Fore.RED}⚠️ {repo}: Could not parse tag name{Style.RESET_ALL}"
                    )
                    return None, None
                return version, cached_data

        # If not cached or cache disabled, fetch from GitHub API
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        print(f"📥 Fetching information for {Fore.CYAN}{repo}{Style.RESET_ALL}...")

        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            # Cache the response if caching is enabled
            if self.cache_enabled:
                cache_api_response(repo, data, self.cache_expiry)

            # Extract version from tag_name (strip 'v' prefix if present)
            tag_name = data.get("tag_name", "")
            version = re.sub(r"^v", "", tag_name)

            if not version:
                print(f"{Fore.RED}⚠️ {repo}: Could not parse tag name{Style.RESET_ALL}")
                return None, None

            return version, data
        except requests.RequestException as e:
            print(
                f"{Fore.RED}❌ {repo}: Failed to fetch release info: {e}{Style.RESET_ALL}"
            )
            return None, None

    def _find_asset_url(
        self,
        repo: str,
        assets: List[Dict],
        platform: str = "linux",
        arch: str = "x86_64",
    ) -> Optional[str]:
        """Find the appropriate asset URL based on platform and architecture"""
        # Detect platform if not specified
        if not platform:
            platform = sys.platform
            if platform.startswith("linux"):
                platform = "linux"
            elif platform.startswith("darwin"):
                platform = "darwin"
            elif platform.startswith("win"):
                platform = "windows"

        # Detect architecture if not specified
        if not arch:
            arch_mapping = {
                "x86_64": ["x86_64", "amd64", "x64"],
                "aarch64": ["aarch64", "arm64", "aarch_64"],
                "arm": ["arm", "armv7"],
            }
            import platform as p

            system_arch = p.machine().lower()
            for target_arch, variants in arch_mapping.items():
                if any(v == system_arch for v in variants):
                    arch = target_arch
                    break

        # Get the repo name for pattern matching
        repo_name = repo.split("/")[1].lower()

        # Define known architecture variant terms
        arch_variants = {
            "x86_64": ["x86_64", "amd64", "x64"],
            "aarch64": ["aarch64", "arm64"],
            "arm": ["arm", "armv7"],
        }

        # Define known platform variant terms
        platform_variants = {
            "linux": [
                "linux",
                "unknown-linux",
                "unknown-linux-gnu",
                "unknown-linux-musl",
            ],
            "darwin": ["darwin", "apple-darwin", "macos"],
            "windows": ["windows", "pc-windows", "pc-windows-msvc"],
        }

        # File extension preference order (most preferred first)
        extension_priority = [".tar.gz", ".tgz", ".appimage", ".zip"]

        # Collection of matching assets with their details
        matching_assets = []

        # First, try to find exact architecture-specific matches
        for asset in assets:
            name = asset.get("name", "").lower()
            url = asset.get("browser_download_url", "")

            # Skip non-downloadable assets or checksums
            if (
                not url
                or ".sha256" in name
                or ".sha512" in name
                or ".sig" in name
                or ".zsync" in name
                or name == "checksums.txt"
            ):
                continue

            # Check for exact architecture match with platform
            current_arch_variants = arch_variants.get(arch, [arch])
            current_platform_variants = platform_variants.get(platform, [platform])

            # Try exact architecture matches with various platform terms
            for a_variant in current_arch_variants:
                for p_variant in current_platform_variants:
                    # Look for patterns like: arch-platform, platform-arch, etc.
                    if (
                        f"{a_variant}-{p_variant}" in name
                        or f"{p_variant}-{a_variant}" in name
                    ):
                        matching_assets.append(
                            {"name": name, "url": url, "match_type": "exact"}
                        )
                        break

                    # Look for patterns like: reponame-arch-platform or similar
                    if (
                        f"{repo_name}" in name
                        and f"{a_variant}" in name
                        and f"{p_variant}" in name
                    ):
                        matching_assets.append(
                            {"name": name, "url": url, "match_type": "repo_specific"}
                        )
                        break

        # If we found exact matches, sort by file extension priority and return the best one
        if matching_assets:
            return self._select_best_asset(matching_assets, extension_priority)

        # Common patterns to look for in filenames, most specific first
        patterns = [
            # Format: exact repository and architecture matches
            rf".*{repo_name}.*{arch}.*{platform}.*\.(?:tar\.gz|tgz|appimage|zip)",
            rf".*{repo_name}.*{platform}.*{arch}.*\.(?:tar\.gz|tgz|appimage|zip)",
            # Format: architecture and platform exact matches
            rf".*{arch}-.*{platform}.*\.(?:tar\.gz|tgz|appimage|zip)",
            rf".*{platform}-.*{arch}.*\.(?:tar\.gz|tgz|appimage|zip)",
            # Format: looser architecture and platform matches
            rf".*{arch}.*{platform}.*\.(?:tar\.gz|tgz|appimage|zip)",
            rf".*{platform}.*{arch}.*\.(?:tar\.gz|tgz|appimage|zip)",
            # Format: architecture with many platform variants
            *[
                rf".*{arch}.*{p_var}.*\.(?:tar\.gz|tgz|appimage|zip)"
                for p_var in platform_variants.get(platform, [platform])
            ],
            # Platform with specific architecture mentions (last resort)
            (
                rf".*{platform}.*64.*\.(?:tar\.gz|tgz|appimage|zip)"
                if "64" in arch
                else None
            ),
            # Just platform as a last resort
            rf".*{platform}.*\.(?:tar\.gz|tgz|appimage|zip)",
        ]

        # Remove None patterns
        patterns = [p for p in patterns if p]

        # Try to find assets that match our patterns
        for pattern in patterns:
            for asset in assets:
                name = asset.get("name", "").lower()
                url = asset.get("browser_download_url", "")

                # Skip non-downloadable assets or checksums
                if (
                    not url
                    or ".sha256" in name
                    or ".sha512" in name
                    or ".sig" in name
                    or ".zsync" in name
                    or name == "checksums.txt"
                ):
                    continue

                if re.match(pattern, name):
                    matching_assets.append(
                        {"name": name, "url": url, "match_type": "pattern"}
                    )

        # If we found pattern matches, sort by file extension priority and return the best one
        if matching_assets:
            return self._select_best_asset(matching_assets, extension_priority)

        # If no pattern match, check for "contains" matches as a fallback
        for asset in assets:
            name = asset.get("name", "").lower()
            url = asset.get("browser_download_url", "")

            # Skip non-downloadable assets or checksums
            if (
                not url
                or ".sha256" in name
                or ".sha512" in name
                or ".sig" in name
                or ".zsync" in name
                or name == "checksums.txt"
            ):
                continue

            # Check if both architecture and platform are in the name
            if arch in name and platform in name:
                matching_assets.append(
                    {"name": name, "url": url, "match_type": "contains"}
                )
                continue

            # Check for specific format like linux_x86_64
            if f"{platform}_{arch}" in name or f"{platform}-{arch}" in name:
                matching_assets.append(
                    {"name": name, "url": url, "match_type": "contains"}
                )
                continue

        # If we found contains matches, sort by file extension priority and return the best one
        if matching_assets:
            return self._select_best_asset(matching_assets, extension_priority)

        # If still nothing found, collect all archives and select the best one
        for asset in assets:
            name = asset.get("name", "").lower()
            url = asset.get("browser_download_url", "")

            # Skip non-downloadable assets or checksums
            if (
                not url
                or ".sha256" in name
                or ".sha512" in name
                or ".sig" in name
                or ".zsync" in name
                or name == "checksums.txt"
            ):
                continue

            if name.endswith((".tar.gz", ".tgz", ".appimage", ".zip")):
                matching_assets.append(
                    {"name": name, "url": url, "match_type": "fallback"}
                )

        # If we found any archives, sort by file extension priority and return the best one
        if matching_assets:
            return self._select_best_asset(matching_assets, extension_priority)

        return None

    def _select_best_asset(
        self, assets: List[Dict], extension_priority: List[str]
    ) -> Optional[str]:
        """Select the best asset based on file extension priority"""
        # First sort by match type (exact > repo_specific > pattern > contains > fallback)
        match_type_priority = {
            "exact": 0,
            "repo_specific": 1,
            "pattern": 2,
            "contains": 3,
            "fallback": 4,
        }

        # Sort assets by match type first
        sorted_assets = sorted(
            assets,
            key=lambda x: match_type_priority.get(x.get("match_type", "fallback"), 999),
        )

        # Group assets with the same match type
        grouped_by_match = {}
        for asset in sorted_assets:
            match_type = asset.get("match_type", "fallback")
            if match_type not in grouped_by_match:
                grouped_by_match[match_type] = []
            grouped_by_match[match_type].append(asset)

        # For each match type group (in priority order), get the best extension
        for match_type in sorted(
            grouped_by_match.keys(), key=lambda k: match_type_priority.get(k, 999)
        ):
            assets_in_group = grouped_by_match[match_type]

            # Find the first asset with the highest priority extension
            for ext in extension_priority:
                for asset in assets_in_group:
                    if asset["name"].endswith(ext):
                        return asset["url"]

            # If no preferred extension found, return the first asset in this group
            if assets_in_group:
                return assets_in_group[0]["url"]

        # If we've reached here, no assets were found
        return None

    def _extract_archive(
        self, archive_path: str, destination: str, strip_components: int = 0
    ) -> bool:
        """Extract an archive file to the destination directory"""
        try:
            # Check if destination needs sudo permissions
            needs_sudo = not os.access(os.path.dirname(destination), os.W_OK)

            # Create destination directory if it doesn't exist
            if needs_sudo:
                try:
                    run_sudo_command(["mkdir", "-p", destination])
                except subprocess.SubprocessError:
                    print(f"{Fore.RED}❌ Failed to create directory: {destination}")
                    print(
                        f"This operation requires sudo privileges. Please run with sudo.{Style.RESET_ALL}"
                    )
                    return False
            else:
                os.makedirs(destination, exist_ok=True)

            if archive_path.endswith((".tar.gz", ".tgz")):
                if strip_components > 0:
                    cmd = [
                        "tar",
                        "xzf",
                        archive_path,
                        "-C",
                        destination,
                        f"--strip-components={strip_components}",
                    ]
                else:
                    cmd = ["tar", "xzf", archive_path, "-C", destination]

                if needs_sudo:
                    run_sudo_command(cmd)
                else:
                    subprocess.run(cmd, check=True)

            elif archive_path.endswith(".zip"):
                # Create a temporary directory for extraction
                with tempfile.TemporaryDirectory() as temp_dir:
                    subprocess.run(
                        ["unzip", "-q", archive_path, "-d", temp_dir], check=True
                    )

                    # Handle strip_components for zip files
                    if strip_components > 0:
                        contents = os.listdir(temp_dir)
                        if len(contents) == 1 and os.path.isdir(
                            os.path.join(temp_dir, contents[0])
                        ):
                            # Move the contents of the top-level directory
                            inner_dir = os.path.join(temp_dir, contents[0])
                            for item in os.listdir(inner_dir):
                                src = os.path.join(inner_dir, item)
                                dst = os.path.join(destination, item)

                                if needs_sudo:
                                    if os.path.exists(dst):
                                        if os.path.isdir(dst):
                                            run_sudo_command(["rm", "-rf", dst])
                                        else:
                                            run_sudo_command(["rm", "-f", dst])

                                    if os.path.isdir(src):
                                        run_sudo_command(["cp", "-r", src, dst])
                                    else:
                                        run_sudo_command(["cp", src, dst])
                                else:
                                    if os.path.exists(dst) and os.path.isdir(dst):
                                        shutil.rmtree(dst)
                                    elif os.path.exists(dst):
                                        os.remove(dst)
                                    if os.path.isdir(src):
                                        shutil.copytree(src, dst)
                                    else:
                                        shutil.copy2(src, dst)
                        else:
                            # Just copy everything
                            for item in contents:
                                src = os.path.join(temp_dir, item)
                                dst = os.path.join(destination, item)

                                if needs_sudo:
                                    if os.path.exists(dst):
                                        if os.path.isdir(dst):
                                            run_sudo_command(["rm", "-rf", dst])
                                        else:
                                            run_sudo_command(["rm", "-f", dst])

                                    if os.path.isdir(src):
                                        run_sudo_command(["cp", "-r", src, dst])
                                    else:
                                        run_sudo_command(["cp", src, dst])
                                else:
                                    if os.path.exists(dst) and os.path.isdir(dst):
                                        shutil.rmtree(dst)
                                    elif os.path.exists(dst):
                                        os.remove(dst)
                                    if os.path.isdir(src):
                                        shutil.copytree(src, dst)
                                    else:
                                        shutil.copy2(src, dst)
                    else:
                        # Copy everything from the temp directory to the destination
                        for item in os.listdir(temp_dir):
                            src = os.path.join(temp_dir, item)
                            dst = os.path.join(destination, item)

                            if needs_sudo:
                                if os.path.exists(dst):
                                    if os.path.isdir(dst):
                                        run_sudo_command(["rm", "-rf", dst])
                                    else:
                                        run_sudo_command(["rm", "-f", dst])

                                if os.path.isdir(src):
                                    run_sudo_command(["cp", "-r", src, dst])
                                else:
                                    run_sudo_command(["cp", src, dst])
                            else:
                                if os.path.exists(dst) and os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                elif os.path.exists(dst):
                                    os.remove(dst)
                                if os.path.isdir(src):
                                    shutil.copytree(src, dst)
                                else:
                                    shutil.copy2(src, dst)
            else:
                print(
                    f"{Fore.RED}❌ Unsupported archive format: {archive_path}{Style.RESET_ALL}"
                )
                return False

            return True
        except subprocess.SubprocessError as e:
            print(f"{Fore.RED}❌ Failed to extract {archive_path}: {e}")
            print(
                f"This operation may require sudo privileges. Please run with sudo.{Style.RESET_ALL}"
            )
            return False
        except Exception as e:
            print(
                f"{Fore.RED}❌ Failed to extract {archive_path}: {e}{Style.RESET_ALL}"
            )
            return False

    def _create_symlink(self, source: str, link_name: str) -> bool:
        """Create a symbolic link from source to link_name"""
        try:
            # Check if destination needs sudo permissions
            needs_sudo = not os.access(os.path.dirname(link_name), os.W_OK)

            if os.path.exists(link_name):
                if os.path.islink(link_name):
                    if needs_sudo:
                        run_sudo_command(["rm", link_name])
                    else:
                        os.unlink(link_name)
                else:
                    # If it's not a symlink, remove it
                    if os.path.isdir(link_name):
                        if needs_sudo:
                            run_sudo_command(["rm", "-rf", link_name])
                        else:
                            shutil.rmtree(link_name)
                    else:
                        if needs_sudo:
                            run_sudo_command(["rm", "-f", link_name])
                        else:
                            os.remove(link_name)

            if needs_sudo:
                run_sudo_command(["ln", "-s", source, link_name])
            else:
                os.symlink(source, link_name)
            return True
        except subprocess.SubprocessError as e:
            print(f"{Fore.RED}❌ Failed to create symbolic link: {e}")
            print(
                f"This operation may require sudo privileges. Please run with sudo.{Style.RESET_ALL}"
            )
            return False
        except Exception as e:
            print(f"{Fore.RED}❌ Failed to create symbolic link: {e}{Style.RESET_ALL}")
            return False

    def _clean_old_versions(
        self, install_path: str, current_version: str, keep_versions: int
    ) -> None:
        """Clean old versions, keeping the N most recent"""
        print(
            f"{Fore.BLUE}🧹 Cleaning old versions in {install_path} (keeping {keep_versions} most recent){Style.RESET_ALL}"
        )

        try:
            # Check if we need sudo to access the install path
            needs_sudo = not os.access(install_path, os.W_OK)

            versions = []
            current_symlink = os.path.join(install_path, "current")

            # List all directories (excluding the 'current' symlink)
            for item in os.listdir(install_path):
                item_path = os.path.join(install_path, item)
                if (
                    os.path.isdir(item_path)
                    and not os.path.islink(item_path)
                    and item != "current"
                ):
                    versions.append(item)

            # Sort versions in descending order (assuming semantic versioning)
            versions.sort(
                key=lambda s: [
                    int(u) if u.isdigit() else u.lower() for u in re.split(r"(\d+)", s)
                ],
                reverse=True,
            )

            # Keep the current version and N-1 additional versions
            versions_to_keep = [current_version]
            for version in versions:
                if version != current_version and len(versions_to_keep) < keep_versions:
                    versions_to_keep.append(version)

            # Remove versions that are not in the keep list
            for version in versions:
                if version not in versions_to_keep:
                    version_path = os.path.join(install_path, version)
                    print(
                        f"{Fore.YELLOW}🗑️  Removing old version: {version_path}{Style.RESET_ALL}"
                    )

                    try:
                        if needs_sudo:
                            run_sudo_command(["rm", "-rf", version_path])
                        else:
                            shutil.rmtree(version_path)
                        print(
                            f"{Fore.GREEN}✓ Successfully removed {version_path}{Style.RESET_ALL}"
                        )
                    except Exception as e:
                        print(
                            f"{Fore.RED}❌ Failed to remove {version_path}: {e}{Style.RESET_ALL}"
                        )
                else:
                    print(
                        f"{Fore.GREEN}✓ Keeping version: {install_path}/{version}{Style.RESET_ALL}"
                    )

        except subprocess.SubprocessError as e:
            print(f"{Fore.RED}❌ Error cleaning old versions: {e}")
            print(
                f"This operation may require sudo privileges. Please run with sudo.{Style.RESET_ALL}"
            )
        except Exception as e:
            print(f"{Fore.RED}❌ Error cleaning old versions: {e}{Style.RESET_ALL}")

    def _detect_strip_components(self, repo: str, archive_path: str) -> int:
        """Detect how many components to strip based on the archive structure"""
        strip_components = 0

        # Auto-detect archive structure
        try:
            if archive_path.endswith((".tar.gz", ".tgz")):
                result = subprocess.run(
                    ["tar", "tf", archive_path],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                files = result.stdout.strip().split("\n")

                # If all files begin with the same directory, we can strip it
                if files and all(
                    f.startswith(files[0].split("/")[0] + "/") for f in files
                ):
                    strip_components = 1

            elif archive_path.endswith(".zip"):
                result = subprocess.run(
                    ["unzip", "-l", archive_path],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                output = result.stdout.strip()
                lines = output.split("\n")[3:-2]  # Skip header and footer lines

                if lines:
                    # Extract filenames from unzip -l output
                    files = [line.split()[-1] for line in lines]
                    # If all files begin with the same directory, we can strip it
                    if all(
                        "/" in f and f.startswith(files[0].split("/")[0] + "/")
                        for f in files
                    ):
                        strip_components = 1

        except Exception:
            # If anything goes wrong, default to no stripping
            pass

        return strip_components
