from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from country_codes import UnknownCountryCodeError, resolve_country_code


def test_resolves_north_korea_to_kp() -> None:
    assert resolve_country_code(None, "Corée du Nord") == "kp"


def test_resolves_france_to_fr() -> None:
    assert resolve_country_code(None, "France") == "fr"


def test_unknown_country_raises_explicit_error() -> None:
    with pytest.raises(UnknownCountryCodeError, match="Code pays ISO-3166 alpha-2 inconnu"):
        resolve_country_code(None, "Pays imaginaire")


def test_unknown_explicit_code_raises_explicit_error() -> None:
    with pytest.raises(UnknownCountryCodeError, match="Code pays ISO-3166 alpha-2 inconnu"):
        resolve_country_code("zz", "France")


def test_unknown_explicit_alias_does_not_fall_back_to_country() -> None:
    with pytest.raises(UnknownCountryCodeError, match="Code pays ISO-3166 alpha-2 inconnu"):
        resolve_country_code("not-a-code", "France")
