"""
Ergaenzt fehlende skos:prefLabel@en im formalisierten DQR (data/formalized/dqr.ttl)
per Mistral-Batch-Uebersetzung der skos:prefLabel@de der betroffenen Konzepte.

Hintergrund (vgl. Docstring von scripts/04_dqr_augment.py): die acht DQR-Hauptniveaus
erhalten dort bereits ein aus dqr:mapsToEQF/skos:exactMatch abgeleitetes @en-Label
("EQF Level N"); alle uebrigen (Unter-)Konzepte haben kein EQF-Mapping und bleiben
ohne skos:prefLabel@en -- genau diese werden hier per LLM uebersetzt.

WICHTIG: LLM-generierte Uebersetzungen sind laut VH1.3 kein automatisch validiertes
Artefakt -- die Ergaenzung ist manuell zu pruefen, bevor der KQR in den Status
"formalisiert" wechselt.

    python scripts/12_dqr_translate_en.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rdflib import RDF, SKOS, Graph, Literal, URIRef  # noqa: E402
from tqdm import tqdm  # noqa: E402

from app.config import settings  # noqa: E402
from app.models.schemas import KQR  # noqa: E402
from app.pipeline.step1_formalization.formalize import validate_formalization  # noqa: E402
from app.pipeline.step3_classification.llm_provider.factory import get_provider  # noqa: E402

INPUT_PATH = ROOT / "data" / "formalized" / "dqr.ttl"
OUTPUT_PATH = ROOT / "data" / "formalized" / "dqr_translated.ttl"

BATCH_SIZE = 10

# Muss zum KQR-Objekt aus scripts/04_dqr_augment.py passen -- validate_formalization
# nutzt kqr nur fuer Fehlermeldungen, nicht fuer die Feldpruefung selbst.
DQR_KQR = KQR(
    id="dqr",
    name="Deutscher Qualifikationsrahmen 2013",
    namespace_uri="http://data.bmbf.de/dqr/",
    source_format="turtle",
)

TRANSLATE_PROMPT_PREFIX = (
    "Übersetze diese deutschen Labels ins Englische. Antworte nur mit den "
    "englischen Labels (eine pro Zeile), keine Erklärungen.\n\n"
)


def _find_concepts_without_en_label(graph: Graph) -> list[URIRef]:
    """Findet alle skos:Concept ohne skos:prefLabel@en."""
    missing: list[URIRef] = []
    for subject in graph.subjects(RDF.type, SKOS.Concept):
        if not isinstance(subject, URIRef):
            continue
        has_en = any(
            getattr(label, "language", None) == "en"
            for label in graph.objects(subject, SKOS.prefLabel)
        )
        if not has_en:
            missing.append(subject)
    return missing


def _de_label(graph: Graph, subject: URIRef) -> str | None:
    """Holt das skos:prefLabel@de eines Konzepts (None, falls keins vorhanden)."""
    for label in graph.objects(subject, SKOS.prefLabel):
        if getattr(label, "language", None) == "de":
            return str(label)
    return None


def _translate_batch(provider, de_labels: list[str]) -> list[str]:
    """Uebersetzt bis zu BATCH_SIZE deutsche Labels in einem Mistral-Call.

    Der Prompt fordert genau ein englisches Label pro Zeile. Weicht die
    Zeilenzahl der Antwort davon ab, gibt der Aufrufer (translate_missing_labels)
    die ueberzaehligen/fehlenden Konzepte unuebersetzt zurueck, statt hier zu
    raten oder abzubrechen -- manuelle Pruefung ist laut VH1.3 ohnehin noetig.
    """
    prompt = TRANSLATE_PROMPT_PREFIX + "\n".join(de_labels)
    response = provider.complete(prompt, max_tokens=500)
    return [line.strip() for line in response.splitlines() if line.strip()]


def translate_missing_labels(graph: Graph, provider) -> int:
    """Ergaenzt skos:prefLabel@en fuer alle Konzepte ohne englisches Label.

    Gibt die Anzahl tatsaechlich ergaenzter Konzepte zurueck (kann kleiner sein
    als die Anzahl der Konzepte ohne @en-Label, z.B. falls ein Konzept auch
    kein @de-Label hat oder eine Batch-Antwort zu wenige Zeilen enthaelt).
    """
    missing = _find_concepts_without_en_label(graph)
    batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]

    n_translated = 0
    for batch in tqdm(batches, desc="Übersetze DQR-Labels", unit="Batch"):
        pairs = [(subject, _de_label(graph, subject)) for subject in batch]
        pairs = [(subject, label) for subject, label in pairs if label is not None]
        if not pairs:
            continue

        de_labels = [label for _, label in pairs]
        en_labels = _translate_batch(provider, de_labels)

        if len(en_labels) != len(pairs):
            print(
                f"  Warnung: {len(de_labels)} Labels gesendet, "
                f"{len(en_labels)} Zeilen in der Antwort -- gleiche per Index ab, "
                "ueberzaehlige Konzepte bleiben unuebersetzt."
            )

        for (subject, _), en_label in zip(pairs, en_labels):
            graph.add((subject, SKOS.prefLabel, Literal(en_label, lang="en")))
            n_translated += 1

    return n_translated


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(
            f"Fehler: {INPUT_PATH} nicht gefunden (zuerst scripts/04_dqr_augment.py ausführen)."
        )

    print(f"Lade {INPUT_PATH} ...")
    graph = Graph()
    graph.parse(INPUT_PATH, format="turtle")

    errors_before = validate_formalization(graph.serialize(format="turtle"), DQR_KQR)

    provider = get_provider("mistral", settings)
    n_translated = translate_missing_labels(graph, provider)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    turtle_after = graph.serialize(format="turtle")
    OUTPUT_PATH.write_text(turtle_after, encoding="utf-8")
    print(f"Geschrieben: {OUTPUT_PATH}")

    errors_after = validate_formalization(turtle_after, DQR_KQR)

    print(f"\n{n_translated} Konzepte übersetzt (skos:prefLabel@en ergänzt)")
    print(f"{len(errors_before)} Fehler vorher → {len(errors_after)} Fehler nachher")
    if errors_after:
        print("Verbleibende Fehler (erste 10):")
        for err in errors_after[:10]:
            print(f"  - {err}")
    else:
        print("Validierung erfolgreich: alle Pflichtfelder aus Tabelle 3.7 vorhanden.")


if __name__ == "__main__":
    main()
