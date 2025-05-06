#!/usr/bin/env python3

import os
import json
import hashlib
import shutil
import time
from typing import Dict, Optional

from .system import get_real_home

# Default paths
CACHE_DIR = os.path.join(get_real_home(), ".cache/ghr-cli")


def ensure_cache_dir() -> None:
    """Ensure the cache directory exists"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    # Create subdirectories
    os.makedirs(os.path.join(CACHE_DIR, "api"), exist_ok=True)
    os.makedirs(os.path.join(CACHE_DIR, "downloads"), exist_ok=True)


def cache_api_response(
    repo: str, response_data: Dict, cache_expiry: int = 3600
) -> None:
    """Cache the API response for a repository"""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, "api", f"{repo.replace('/', '_')}.json")
    data = {"timestamp": time.time(), "expiry": cache_expiry, "data": response_data}
    with open(cache_file, "w") as f:
        json.dump(data, f)


def get_cached_api_response(repo: str, cache_expiry: int = 3600) -> Optional[Dict]:
    """Get a cached API response if it exists and is not expired"""
    cache_file = os.path.join(CACHE_DIR, "api", f"{repo.replace('/', '_')}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
            # Check if cache is expired
            if time.time() - cache_data["timestamp"] < cache_data.get(
                "expiry", cache_expiry
            ):
                return cache_data["data"]
        except (json.JSONDecodeError, KeyError, IOError):
            # If there's any error reading the cache, ignore it
            pass
    return None


def get_cached_download(url: str) -> Optional[str]:
    """Get a cached download if it exists"""
    ensure_cache_dir()
    # Create a hash of the URL to use as the filename
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, "downloads", url_hash)
    if os.path.exists(cache_file):
        return cache_file
    return None


def cache_download(url: str, file_path: str) -> str:
    """Cache a downloaded file"""
    ensure_cache_dir()
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = os.path.join(CACHE_DIR, "downloads", url_hash)
    shutil.copy2(file_path, cache_file)
    return cache_file


def clear_cache() -> bool:
    """Clear GHR CLI's cache"""
    if not os.path.exists(CACHE_DIR):
        return False

    try:
        # Remove API cache
        api_cache = os.path.join(CACHE_DIR, "api")
        if os.path.exists(api_cache):
            for file in os.listdir(api_cache):
                os.remove(os.path.join(api_cache, file))

        # Remove downloads cache
        downloads_cache = os.path.join(CACHE_DIR, "downloads")
        if os.path.exists(downloads_cache):
            for file in os.listdir(downloads_cache):
                os.remove(os.path.join(downloads_cache, file))

        return True
    except Exception:
        return False


def get_cache_info() -> Dict:
    """Get information about the cache"""
    info = {
        "exists": os.path.exists(CACHE_DIR),
        "path": CACHE_DIR,
        "size_bytes": 0,
        "api_entries": 0,
        "download_entries": 0,
    }

    if not info["exists"]:
        return info

    # Calculate cache size and entries
    api_cache = os.path.join(CACHE_DIR, "api")
    downloads_cache = os.path.join(CACHE_DIR, "downloads")

    if os.path.exists(api_cache):
        api_files = os.listdir(api_cache)
        info["api_entries"] = len(api_files)
        for file in api_files:
            info["size_bytes"] += os.path.getsize(os.path.join(api_cache, file))

    if os.path.exists(downloads_cache):
        download_files = os.listdir(downloads_cache)
        info["download_entries"] = len(download_files)
        for file in download_files:
            info["size_bytes"] += os.path.getsize(os.path.join(downloads_cache, file))

    return info
