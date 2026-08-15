#!/usr/bin/env python3
"""
Minifie des GeoJSON produits par json.dumps(..., indent=N) sans les charger
en mémoire et sans rejouer le pipeline de génération.

Hypothèse sur l'entrée : sortie de json.dumps avec indent, donc
  - un token par ligne
  - aucune string ne s'étend sur plusieurs lignes (interdit par JSON)
  - le seul blanc interne à une ligne est le séparateur ": " après une clé

Usage :
    python minify_geojson.py fichier1.geojson [fichier2.geojson ...]

Écrit <nom>.min.geojson à côté de chaque fichier et affiche le gain.
"""

import re
import sys
from pathlib import Path

# Clé JSON en début de ligne, suivie du séparateur ':' entouré de blancs.
# Le motif de string gère les échappements, donc une clé contenant ':'
# ou des espaces n'est pas altérée.
KEY_SEPARATOR = re.compile(r'^("(?:[^"\\]|\\.)*")\s*:\s*')

READ_BUFFER = 1 << 20


def minify(src: Path, dst: Path) -> None:
    with src.open("r", encoding="utf-8", buffering=READ_BUFFER) as fin, \
         dst.open("w", encoding="utf-8", buffering=READ_BUFFER, newline="") as fout:

        out = []
        out_size = 0

        for line in fin:
            token = line.strip()

            if not token:
                continue

            token = KEY_SEPARATOR.sub(r"\1:", token, count=1)

            out.append(token)
            out_size += len(token)

            if out_size >= READ_BUFFER:
                fout.write("".join(out))
                out = []
                out_size = 0

        if out:
            fout.write("".join(out))


def human(size: int) -> str:
    return "{0:.2f} MiB".format(size / (1024 * 1024))


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    for raw in argv[1:]:
        src = Path(raw)

        if not src.is_file():
            print("introuvable : {0}".format(src))
            return 1

        dst = src.with_suffix(".min.geojson")

        before = src.stat().st_size
        minify(src, dst)
        after = dst.stat().st_size

        ratio = (1 - after / before) * 100 if before else 0

        print("{0}\n  avant : {1}\n  apres : {2}  (-{3:.1f} %)".format(
            src.name, human(before), human(after), ratio
        ))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))