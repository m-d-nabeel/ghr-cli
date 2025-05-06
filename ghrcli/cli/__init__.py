#!/usr/bin/env python3

import argparse
import sys
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init()

try:
    from version import __version__
except ImportError:
    __version__ = "0.0.0-unknown"
