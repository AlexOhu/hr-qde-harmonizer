#!/usr/bin/env python3
"""Restore .tex files from their .tex.bak backups and remove the .bak files.

Searches the workspace roots for files ending with `.tex.bak`, restores the
original `.tex` file (overwriting any current file), and deletes the `.bak`.
Prints a summary of restored files.
"""
from pathlib import Path

ROOTS = [
    Path(r"e:/Fernuni/Master/Masterarbeit/hrqde-harmonizer"),
    Path(r"c:/Users/Alex/OneDrive2/OneDrive/Dokumente/Fernuni/Masterarbeit/Vorlage"),
]

def main():
    restored = 0
    failed = []
    for root in ROOTS:
        if not root.exists():
            print(f"Skipping missing root: {root}")
            continue
        for bak in sorted(root.rglob("*.tex.bak")):
            orig = bak.with_suffix("")  # removes the .bak suffix -> file.tex
            try:
                content = bak.read_bytes()
                orig.write_bytes(content)
                bak.unlink()
                print(f"Restored {orig}")
                restored += 1
            except Exception as e:
                failed.append((bak, str(e)))
    print(f"Done. Restored: {restored}, Failures: {len(failed)}")
    if failed:
        print("Failures:")
        for f, err in failed:
            print(f"  {f}: {err}")

if __name__ == '__main__':
    main()
