#!/usr/bin/env python3
"""Replace semicolon-separated clauses in .tex files with sentence split.

Searches for patterns like "; die" and replaces with ". Die" (capitalizes
the first letter after the sentence break). Creates a .bak copy for each
modified file.
"""
import re
from pathlib import Path

ROOTS = [
    Path(r"e:/Fernuni/Master/Masterarbeit/hrqde-harmonizer"),
    Path(r"c:/Users/Alex/OneDrive2/OneDrive/Dokumente/Fernuni/Masterarbeit/Vorlage"),
]

# match semicolon + whitespace + lowercase letter
INLINE_PATTERN = re.compile(r";\s+([a-zäöüß])", flags=re.M)

# environments to skip entirely
SKIP_ENVS = {
    "tabular",
    "longtable",
    "tabularx",
    "table",
    "itemize",
    "enumerate",
    "description",
    "tikzpicture",
    "lstlisting",
    "verbatim",
    "align",
    "equation",
    "figure",
}


def process_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    original = text

    lines = text.splitlines(keepends=True)
    out_lines = []
    in_env = False
    env_name = None
    paragraph_buffer = []
    changes = 0

    def flush_paragraph(buf):
        nonlocal changes
        if not buf:
            return []
        para = "".join(buf)
        # skip if paragraph contains table markers or manual latex line breaks
        if "&" in para or "\\\\" in para:
            return buf
        # first non-space character of paragraph
        m = re.search(r"\S", para)
        if not m:
            return buf
        first_char = para[m.start()]
        if not re.match(r"[A-ZÄÖÜ]", first_char):
            return buf
        # perform inline replacements in this paragraph
        def repl(m):
            changes += 1
            return ". " + m.group(1).upper()
        new_para, n = INLINE_PATTERN.subn(lambda m: (". " + m.group(1).upper()), para)
        if n > 0:
            changes += n
            return [new_para]
        return buf

    for line in lines:
        # detect environment begin/end
        begin = re.match(r"\\\\begin\{([^}]+)\}", line)
        end = re.match(r"\\\\end\{([^}]+)\}", line)
        if begin:
            # flush any pending paragraph before entering env
            out_lines.extend(flush_paragraph(paragraph_buffer))
            paragraph_buffer = []
            in_env = True
            env_name = begin.group(1)
            out_lines.append(line)
            continue
        if end:
            out_lines.extend(flush_paragraph(paragraph_buffer))
            paragraph_buffer = []
            in_env = False
            env_name = None
            out_lines.append(line)
            continue

        if in_env and env_name in SKIP_ENVS:
            out_lines.append(line)
            continue

        # treat blank line as paragraph separator
        if line.strip() == "":
            out_lines.extend(flush_paragraph(paragraph_buffer))
            paragraph_buffer = []
            out_lines.append(line)
            continue

        # accumulate into paragraph buffer
        paragraph_buffer.append(line)

    # flush any remaining paragraph
    out_lines.extend(flush_paragraph(paragraph_buffer))

    new_text = "".join(out_lines)
    # write only if changed
    if new_text != original:
        bak = path.with_suffix(path.suffix + ".bak")
        bak.write_text(original, encoding="utf-8")
        path.write_text(new_text, encoding="utf-8")
        # compute number of replacements as difference in occurrences
        changes = len(re.findall(r"\. [A-ZÄÖÜ]", new_text)) - len(re.findall(r"; [a-zäöüß]", original))
        # fallback if negative
        if changes < 0:
            changes = INLINE_PATTERN.subn(lambda m: (". " + m.group(1).upper()), original)[1]
    else:
        changes = 0
    return changes


def main():
    total_changes = 0
    files_changed = 0
    for root in ROOTS:
        if not root.exists():
            print(f"Skipping missing root: {root}")
            continue
        for p in sorted(root.rglob("*.tex")):
            try:
                n = process_file(p)
            except Exception as e:
                print(f"Error processing {p}: {e}")
                continue
            if n > 0:
                print(f"Modified {p} — {n} replacements")
                total_changes += n
                files_changed += 1
    print(f"Done. Files changed: {files_changed}, total replacements: {total_changes}")


if __name__ == "__main__":
    main()
