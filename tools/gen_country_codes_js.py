#!/usr/bin/env python3
"""
gen_country_codes_js.py — Régénère visualizer/js/country-codes.js depuis
data/country_codes.json.

But : garder UNE seule source de vérité (le JSON). Le module JS embarque la
donnée en dur pour rester synchrone à l'init (aucun fetch), mais ne doit jamais
être édité à la main : on le régénère avec ce script après toute modification du
JSON.

Usage :
    python tools/gen_country_codes_js.py            # écrit le fichier
    python tools/gen_country_codes_js.py --check    # échoue si le JS est périmé

La logique JavaScript (stripAccents / normalizeCountryKey / resolve) est figée
ici et reste strictement identique à la version d'origine : seule la liste
COUNTRIES est générée.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "data" / "country_codes.json"
JS_PATH = REPO_ROOT / "visualizer" / "js" / "country-codes.js"

BANNER = (
    "// FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN.\n"
    "// Source : data/country_codes.json\n"
    "// Régénérer : python tools/gen_country_codes_js.py\n"
)

HEADER = """(function (App) {
  "use strict";

  function stripAccents(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\\u0300-\\u036f]/g, "");
  }

  function normalizeCountryKey(value) {
    return stripAccents(value)
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/\\s+/g, " ");
  }
"""

FOOTER = """
  function buildLookup() {
    var lookup = {};

    COUNTRIES.forEach(function (country) {
      var code = String(country.code || "").trim().toLowerCase();
      var values = [code, country.name].concat(country.aliases || []);

      values.forEach(function (value) {
        var key = normalizeCountryKey(value);
        if (key) {
          lookup[key] = code;
        }
      });
    });

    return lookup;
  }

  var lookup = buildLookup();
  var namesByCode = COUNTRIES.reduce(function (result, country) {
    result[country.code] = country.name;
    return result;
  }, {});

  function resolve(value, countryName) {
    var rawCode = String(value || "").trim().toLowerCase();

    if (rawCode) {
      if (/^[a-z]{2}$/.test(rawCode) && lookup[rawCode] === rawCode) {
        return rawCode;
      }

      var rawKey = normalizeCountryKey(value);
      if (lookup[rawKey]) {
        return lookup[rawKey];
      }

      throw new Error(
        "Code pays ISO-3166 alpha-2 inconnu pour \\"" + rawCode +
        "\\". Ajoutez un alias dans data/country_codes.json ou renseignez le code pays."
      );
    }

    var key = normalizeCountryKey(countryName);
    if (lookup[key]) {
      return lookup[key];
    }

    var label = String(countryName || "").trim() || "<vide>";
    throw new Error(
      "Code pays ISO-3166 alpha-2 inconnu pour \\"" + label +
      "\\". Ajoutez un alias dans data/country_codes.json ou renseignez le code pays."
    );
  }

  App.CountryCodes = {
    countries: COUNTRIES,
    namesByCode: namesByCode,
    normalizeKey: normalizeCountryKey,
    resolve: resolve
  };
})(window.CS2Zoning = window.CS2Zoning || {});
"""


def load_countries() -> list[dict]:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    countries = data.get("countries", [])

    if not isinstance(countries, list) or not countries:
        raise SystemExit(f"[ERREUR] Aucun pays dans {JSON_PATH}")

    normalized: list[dict] = []
    seen: set[str] = set()

    for entry in countries:
        code = str(entry.get("code", "")).strip().lower()

        if not re.fullmatch(r"[a-z]{2}", code):
            raise SystemExit(f"[ERREUR] Code ISO-3166 alpha-2 invalide : {code!r}")

        if code in seen:
            raise SystemExit(f"[ERREUR] Code pays dupliqué : {code!r}")
        seen.add(code)

        normalized.append({
            "code": code,
            "name": str(entry.get("name", "")).strip(),
            "aliases": [str(a) for a in entry.get("aliases", []) if str(a).strip()],
        })

    # Tri déterministe par code (même ordre que la version d'origine).
    normalized.sort(key=lambda c: c["code"])
    return normalized


def render(countries: list[dict]) -> str:
    array_json = json.dumps(countries, indent=2, ensure_ascii=False)
    array_indented = "\n".join("  " + line for line in array_json.splitlines())
    countries_decl = "  var COUNTRIES = " + array_indented.lstrip() + ";\n"

    return BANNER + HEADER + "\n" + countries_decl + FOOTER


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="N'écrit rien ; code de sortie 1 si country-codes.js est périmé.",
    )
    args = parser.parse_args()

    countries = load_countries()
    content = render(countries)

    if args.check:
        current = JS_PATH.read_text(encoding="utf-8") if JS_PATH.exists() else ""
        if current != content:
            print("[PÉRIMÉ] country-codes.js diffère du JSON. "
                  "Lancez : python tools/gen_country_codes_js.py")
            return 1
        print("[OK] country-codes.js est à jour.")
        return 0

    JS_PATH.write_text(content, encoding="utf-8")
    print(f"[OK] {JS_PATH.relative_to(REPO_ROOT)} régénéré "
          f"({len(countries)} pays).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
