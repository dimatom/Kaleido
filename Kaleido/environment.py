"""Environment variable helpers shared by Django and application code."""

import os
import re
from collections.abc import Iterable
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / "kaleido.env"
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(path: str | Path | None = None) -> None:
    """Load a local env file without overriding process-level variables."""
    env_path = Path(path or os.getenv("KALEIDO_ENV_FILE", DEFAULT_ENV_FILE))
    if not env_path.is_file():
        return

    for line_number, raw_line in enumerate(
        env_path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()

        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not ENV_NAME_PATTERN.fullmatch(name):
            raise ImproperlyConfigured(
                f"Invalid environment entry in {env_path} at line {line_number}"
            )

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


load_env_file()


def get_env(
    name: str,
    default: str | None = None,
    *,
    aliases: Iterable[str] = (),
    required: bool = False,
) -> str | None:
    """Read the first non-empty value from a canonical name and its aliases."""
    for candidate in (name, *aliases):
        value = os.getenv(candidate)
        if value is not None and value.strip():
            return value.strip()

    if required:
        raise ImproperlyConfigured(f"Required environment variable {name} is not set")
    return default


def get_bool(name: str, default: bool = False) -> bool:
    value = get_env(name)
    if value is None:
        return default

    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"Environment variable {name} must be true/false, yes/no, on/off, or 1/0"
    )


def get_int(name: str, default: int) -> int:
    value = get_env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be an integer"
        ) from exc


def get_list(name: str, default: Iterable[str] = ()) -> list[str]:
    value = get_env(name)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]
