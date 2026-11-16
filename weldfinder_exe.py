"""PyInstaller entry point (absolute import so the package context exists)."""
import sys

from weldfinder.cli import main

if __name__ == "__main__":
    sys.exit(main())
