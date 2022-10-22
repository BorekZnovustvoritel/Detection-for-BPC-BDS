from pathlib import Path


def get_self_project_root() -> Path:
    return Path(__file__).parent
