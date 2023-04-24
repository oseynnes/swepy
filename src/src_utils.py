"""Module to retrieve root path"""
# https://stackoverflow.com/a/53465812/13147488

from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).parent.parent
