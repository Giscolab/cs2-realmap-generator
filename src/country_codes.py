from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


class UnknownCountryCodeError(ValueError):
    """Raised when no explicit ISO-3166 alpha-2 country code can be resolved."""


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_country_key(value: str | None) -> str:
    ascii_value = strip_accents(value or "").lower()
    key = re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()
    return re.sub(r"\s+", " ", key)


@lru_cache(maxsize=1)
def load_country_code_data() -> dict[str, Any]:
    data_path = Path(__file__).resolve().parent.parent / "data" / "country_codes.json"

    try:
        return json.loads(data_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Fichier de codes pays introuvable : {data_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Fichier de codes pays invalide : {data_path} ({exc})") from exc


@lru_cache(maxsize=1)
def country_code_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}

    for country in load_country_code_data().get("countries", []):
        code = str(country.get("code", "")).strip().lower()

        if not re.fullmatch(r"[a-z]{2}", code):
            raise RuntimeError(f"Code pays ISO-3166 alpha-2 invalide : {code!r}")

        values = [code, country.get("name", ""), *country.get("aliases", [])]

        for value in values:
            key = normalize_country_key(str(value))
            if key:
                lookup[key] = code

    return lookup


def resolve_country_code(value: str | None, country_name: str | None = None) -> str:
    raw_code = str(value or "").strip().lower()
    lookup = country_code_lookup()

    if raw_code:
        if re.fullmatch(r"[a-z]{2}", raw_code) and raw_code in lookup.values():
            return raw_code

        key = normalize_country_key(value)
        if key in lookup:
            return lookup[key]

        raise UnknownCountryCodeError(
            f"Code pays ISO-3166 alpha-2 inconnu pour {raw_code!r}. "
            "Ajoutez un alias dans data/country_codes.json ou passez --country-code."
        )

    key = normalize_country_key(country_name)
    if key in lookup:
        return lookup[key]

    label = str(country_name or "").strip() or "<vide>"
    raise UnknownCountryCodeError(
        f"Code pays ISO-3166 alpha-2 inconnu pour {label!r}. "
        "Ajoutez un alias dans data/country_codes.json ou passez --country-code."
    )


def country_name_by_code() -> dict[str, str]:
    result: dict[str, str] = {}

    for country in load_country_code_data().get("countries", []):
        code = str(country.get("code", "")).strip().lower()
        name = str(country.get("name", "")).strip()

        if code and name:
            result[code] = name

    return result
