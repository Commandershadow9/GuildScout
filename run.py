#!/usr/bin/env python3
"""
GuildScout Bot Runner

This is the main entry point to run the GuildScout Discord Bot.
Simply run: python run.py
"""

import sys
from src.bot import main
from src.utils import SingleInstanceLock

if __name__ == "__main__":
    # Ensure only one instance is running
    lock = SingleInstanceLock()
    if not lock.acquire():
        print(f"❌ Error: Another instance of GuildScout is already running (checked {lock.lock_file_path}).")
        print("Please stop the existing instance before starting a new one.")
        sys.exit(1)

    try:
        main()
    finally:
        lock.release()