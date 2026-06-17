import re
from pathlib import Path

path = Path(r".\visualizer\zoning_data.js")
text = path.read_text(encoding="utf-8-sig")

print("FILE:", path.resolve())
print("SIZE:", len(text), "chars")
print()

tokens = [
    "FeatureCollection",
    '"Feature"',
    '"features"',
    '"geometry"',
    '"coordinates"',
    "window.",
    "const ",
    "let ",
    "var ",
]

print("TOKEN COUNTS")
for token in tokens:
    print(f"{token}: {text.count(token)}")

print()
print("ASSIGNMENT CANDIDATES")

patterns = [
    r'(?m)^\s*(?:window\.)?([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*=\s*([\[{])',
    r'(?m)^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([\[{])',
]

seen = set()
for pattern in patterns:
    for m in re.finditer(pattern, text):
        name = m.group(1)
        opener = m.group(2)
        idx = m.start(2)
        if idx in seen:
            continue
        seen.add(idx)
        excerpt = text[m.start():m.start()+300].replace("\n", "\\n")
        print()
        print("name:", name)
        print("index:", idx)
        print("opener:", opener)
        print("excerpt:", excerpt[:300])

print()
print("FIRST 2000 CHARS")
print(text[:2000])
