"""Tests for the Folkbibliotek Sverige custom integration."""

from pathlib import Path

BASE_URL = "https://folkbiblioteken.lund.se"
USERNAME = "username"
PASSWORD = "password"


def load_fixture(filename: str) -> str:
    """Load a fixture."""
    path = Path(__package__) / "fixtures" / filename
    return path.read_text(encoding="utf-8")
