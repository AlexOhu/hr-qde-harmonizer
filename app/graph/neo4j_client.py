"""
Neo4j-Client für den Graph-Store der harmonisierten Ontologie.

Nutzt Neosemantics (n10s), um RDF/OWL/SKOS-Daten direkt als Property Graph
zu importieren und abzufragen (vgl. Abschnitt 2.2.4.4). Konfiguration des
n10s-Graph-Configs siehe n10s_config.cypher im selben Verzeichnis.

Persistenz-Design dieses Ausbaus (siehe Plan): Neo4j ist NICHT die primäre
Datenhaltung der API (das ist ein In-Prozess-/Datei-Store in app/services/),
sondern ein optionaler, best-effort Materialisierungsschritt. Aufrufer
sollten Verbindungsfehler abfangen, statt sie zu propagieren.
"""

from __future__ import annotations

import logging
from pathlib import Path

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)

_N10S_CONFIG_PATH = Path(__file__).parent / "n10s_config.cypher"


def get_driver(uri: str, user: str, password: str) -> Driver:
    """Erstellt den Neo4j-Treiber. Verbindung wird lazy aufgebaut."""
    return GraphDatabase.driver(uri, auth=(user, password))


def _split_cypher_statements(script: str) -> list[str]:
    """Zerlegt ein Cypher-Skript in einzelne, kommentarfreie Statements."""
    statements: list[str] = []
    for raw_statement in script.split(";"):
        lines = [
            line
            for line in raw_statement.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements


def init_n10s_config(driver: Driver) -> None:
    """
    Initialisiert die Neosemantics-Graph-Konfiguration (einmalig pro
    Datenbank nötig). Führt n10s_config.cypher aus.

    n10s.graphconfig.init und n10s.nsprefixes.add sind von Neosemantics
    aus nicht idempotent (sie werfen einen Fehler, wenn bereits eine
    Konfiguration bzw. ein Präfix existiert). Diese Funktion toleriert
    diesen Fehlerfall bewusst, damit sie bei jedem API-Start gefahrlos
    erneut aufgerufen werden kann; die Uniqueness-Constraint nutzt
    ohnehin bereits "IF NOT EXISTS".
    """
    statements = _split_cypher_statements(_N10S_CONFIG_PATH.read_text(encoding="utf-8"))

    with driver.session() as session:
        for statement in statements:
            try:
                session.run(statement)
            except Neo4jError as exc:
                logger.warning(
                    "n10s-Init-Statement übersprungen (vermutlich bereits konfiguriert): %s", exc
                )


def import_turtle(driver: Driver, turtle_content: str) -> None:
    """Importiert einen Turtle-String über n10s.rdf.import.inline."""
    with driver.session() as session:
        session.run(
            "CALL n10s.rdf.import.inline($rdf, 'Turtle')",
            rdf=turtle_content,
        )


def get_kqr_status(driver: Driver, kqr_id: str) -> dict:
    """
    Liefert den aktuellen Status eines KQR im Graphen (für Funktionsgruppe 1
    und die Statuszeilen in Funktionsgruppe 2, vgl. Abschnitt 3.8.3).

    Zählt Knoten, deren hrqde:derivedFrom-Property den kqr_id-Fragment-Anteil
    enthält. n10s bildet Properties bei handleVocabUris="MAP" auf
    "<präfix>__<localName>" ab (siehe n10s_config.cypher, Präfix "hrqde").
    """
    query = """
    MATCH (c:Resource)
    WHERE c.hrqde__derivedFrom IS NOT NULL
      AND ANY(value IN c.hrqde__derivedFrom WHERE value CONTAINS $kqr_id)
    RETURN count(c) AS concept_count
    """
    with driver.session() as session:
        record = session.run(query, kqr_id=kqr_id).single()
        concept_count = record["concept_count"] if record else 0

    return {"kqr_id": kqr_id, "concept_count": concept_count, "materialized": concept_count > 0}
