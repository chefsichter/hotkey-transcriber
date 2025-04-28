#!/usr/bin/env python3
"""
convert_imports.py

Script to convert relative imports in the hotkey_transcriber package to absolute imports.
Usage: python tools/convert_imports.py
"""
import re
from pathlib import Path

# Name of the package directory under src/
PKG_NAME = "hotkey_transcriber"
# Compute the path to src/hotkey_transcriber
SRC_ROOT = Path(__file__).parent.parent / "src" / PKG_NAME

# Regex to match statements like: from ..module import name
from_re = re.compile(
    r"^(?P<indent>\s*)from\s+(?P<dots>\.+)(?P<mod>[\w\.]*)\s+import\s+(?P<rest>.+)$"
)

def rewrite_file(path: Path):
    text = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    # Path of the file relative to the package root
    rel = path.parent.relative_to(SRC_ROOT)
    depth = 0 if rel == Path('.') else len(rel.parts)

    out_lines = []
    for line in text:
        m = from_re.match(line)
        if not m:
            out_lines.append(line)
            continue

        indent = m.group("indent")
        dots = m.group("dots")
        mod = m.group("mod")
        rest = m.group("rest")
        lvl = len(dots)

        # Determine absolute module path parts
        if rel == Path('.'):
            base_parts = []
        else:
            base_parts = list(rel.parts[: max(0, depth - lvl + 1)])
        if mod:
            base_parts.append(mod)
        abs_mod = ".".join([PKG_NAME] + base_parts)

        new_line = f"{indent}from {abs_mod} import {rest}\n"
        out_lines.append(new_line)
        changed = True

    if changed:
        path.write_text("".join(out_lines), encoding="utf-8")
        print(f"Updated imports in {path}")

def main():
    if not SRC_ROOT.is_dir():
        print(f"Error: source root {SRC_ROOT} not found.")
        return
    for py_file in SRC_ROOT.rglob("*.py"):
        rewrite_file(py_file)
    print("Done. Please review and commit the changes.")

if __name__ == "__main__":
    main()