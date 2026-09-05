"""
Ergaenzt data/formalized/ecf.ttl um die e-CF-Dimension-3-Angaben
(Proficiency-Stufen e-1 ... e-5) je Kompetenz A.1 ... E.9.

Praedikat: hrqde:proficiencyLevel (Namensraum https://hrqde.example.org/ontology#,
bereits im Header von ecf.ttl gebunden), ein Literal je zugeordneter Stufe.

QUELLE
------
Die Zuordnungstabelle unten ist aus der e-CF-3.0-Spezifikation
(CWA 16234-1:2014, "European e-Competence Framework 3.0", Teil 1, je
Kompetenz die Zeile "Dimension 3 - e-Competence proficiency levels e-1 to
e-5") uebertragen. Stufenbaender (z. B. D.11 auf e-3 .. e-5) sind gewollt:
dieselbe Kompetenz auf verschiedenen Verantwortungsebenen. Anzahl der
resultierenden LevelMappings (135) und die Range-Semantik sind bestaetigt.

Textbasiertes Einfuegen (kein rdflib-Reserialize), damit Kommentare,
Reihenfolge und Formatierung von ecf.ttl unveraendert bleiben. Idempotent:
ein bereits vorhandenes hrqde:proficiencyLevel wird nicht erneut ergaenzt.
"""

from __future__ import annotations

from pathlib import Path

ECF_TTL = Path(__file__).resolve().parents[1] / "data" / "formalized" / "ecf.ttl"

# e-CF 3.0, Dimension 3: Kompetenz -> zugeordnete Proficiency-Stufen
DIMENSION_3: dict[str, list[str]] = {
    # A. PLAN
    "A.1": ["e-4", "e-5"],
    "A.2": ["e-3", "e-4"],
    "A.3": ["e-3", "e-4", "e-5"],
    "A.4": ["e-2", "e-3", "e-4"],
    "A.5": ["e-3", "e-4", "e-5"],
    "A.6": ["e-1", "e-2", "e-3"],
    "A.7": ["e-4", "e-5"],
    "A.8": ["e-2", "e-3", "e-4"],
    "A.9": ["e-4", "e-5"],
    # B. BUILD
    "B.1": ["e-1", "e-2", "e-3"],
    "B.2": ["e-2", "e-3"],
    "B.3": ["e-1", "e-2", "e-3", "e-4"],
    "B.4": ["e-1", "e-2", "e-3"],
    "B.5": ["e-1", "e-2", "e-3"],
    "B.6": ["e-3", "e-4"],
    # C. RUN
    "C.1": ["e-1", "e-2", "e-3"],
    "C.2": ["e-2", "e-3"],
    "C.3": ["e-1", "e-2", "e-3"],
    "C.4": ["e-2", "e-3", "e-4"],
    # D. ENABLE
    "D.1": ["e-4", "e-5"],
    "D.2": ["e-4", "e-5"],
    "D.3": ["e-3", "e-4"],
    "D.4": ["e-2", "e-3", "e-4"],
    "D.5": ["e-3", "e-4"],
    "D.6": ["e-3", "e-4"],
    "D.7": ["e-3", "e-4"],
    "D.8": ["e-3", "e-4"],
    "D.9": ["e-2", "e-3", "e-4"],
    "D.10": ["e-3", "e-4", "e-5"],
    "D.11": ["e-3", "e-4"],
    "D.12": ["e-3", "e-4", "e-5"],
    # E. MANAGE
    "E.1": ["e-3", "e-4"],
    "E.2": ["e-3", "e-4", "e-5"],
    "E.3": ["e-2", "e-3", "e-4"],
    "E.4": ["e-3", "e-4"],
    "E.5": ["e-3", "e-4"],
    "E.6": ["e-2", "e-3", "e-4"],
    "E.7": ["e-3", "e-4"],
    "E.8": ["e-2", "e-3", "e-4"],
    "E.9": ["e-4", "e-5"],
}


def main() -> None:
    lines = ECF_TTL.read_text(encoding="utf-8").splitlines(keepends=True)
    if any("hrqde:proficiencyLevel" in ln for ln in lines):
        print("ecf.ttl traegt bereits hrqde:proficiencyLevel -- nichts zu tun.")
        return

    out: list[str] = []
    inserted = 0
    for line in lines:
        out.append(line)
        stripped = line.strip()
        if stripped.startswith("hrqde:sourceIdentifier "):
            comp_id = stripped.split('"')[1]
            levels = DIMENSION_3.get(comp_id)
            if levels:
                indent = line[: len(line) - len(line.lstrip())]
                values = ", ".join(f'"{lv}"' for lv in levels)
                out.append(f"{indent}hrqde:proficiencyLevel {values} ;\n")
                inserted += 1

    ECF_TTL.write_text("".join(out), encoding="utf-8")
    total_levels = sum(len(v) for v in DIMENSION_3.values())
    print(f"hrqde:proficiencyLevel ergaenzt fuer {inserted} Kompetenzen "
          f"({total_levels} Stufen-Zuordnungen).")


if __name__ == "__main__":
    main()
