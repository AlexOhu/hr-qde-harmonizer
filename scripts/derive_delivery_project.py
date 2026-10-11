"""
Leitet ein Lieferprojekt aus einem bestehenden Lieferprojekt ab, ohne die
Klassifikation neu auszufuehren.

Anlass: Lieferung v0.5 = Klassifikationsbestand der Lieferung v0.4
(identische Mappings und Klassifikationsergebnisse) plus kuratierte
Integrationsentscheidungen fuer die disjunkten e-CF-Konzepte. Das
Quellprojekt bleibt unveraendert, damit es die Lieferung v0.4 weiterhin
reproduziert.

Kopiert werden byte-identisch:
  mappings.json, classification_results.json, classification_jobs.json
  delivery/run_config.json   (Provenienz des Klassifikationslaufs)
Nicht kopiert werden disjoint_decisions.json (soll im neuen Projekt neu
entschieden werden) und die Lieferartefakte unter delivery/.

Zusaetzlich entsteht derivation.json mit Quellprojekt und SHA-256 der
kopierten Dateien.

    python scripts/derive_delivery_project.py \
        --source saeule_d_lieferung_v0_4_t_0_mistral_small_2603_20261004T185355Z \
        --name "Saeule D Lieferung v0.5 (Klassifikation v0.4, kuratierte Integrationsentscheidungen)" \
        --version-label 0.5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import Project, ProjectStatus
from app.services import project_service

COPY_FILES = ["mappings.json", "classification_results.json", "classification_jobs.json"]
COPY_DELIVERY_FILES = ["run_config.json"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(source_id: str, name: str, version_label: str, description: str | None) -> Project:
    source = project_service.get_project(source_id)
    for project in project_service.list_projects():
        if project.name == name:
            raise SystemExit(f"Projekt mit Namen '{name}' existiert bereits: {project.project_id}")

    src_dir = project_service.get_project_data_dir(source_id)
    missing = [f for f in COPY_FILES if not (src_dir / f).exists()]
    if missing:
        raise SystemExit(f"Quellprojekt unvollstaendig, fehlt: {missing}")

    derived = Project(
        project_id=project_service._new_project_id(name),
        name=name,
        description=description,
        kqr_ids=list(source.kqr_ids),
        kqr_scopes=dict(source.kqr_scopes),
        hub_kqr_id=source.hub_kqr_id,
        status=ProjectStatus.ACTIVE,
        parent_project_id=source_id,
        version_label=version_label,
    )
    project_service._write_project(derived)
    dst_dir = project_service.get_project_data_dir(derived.project_id)

    copied: dict[str, str] = {}
    for fname in COPY_FILES:
        shutil.copyfile(src_dir / fname, dst_dir / fname)
        copied[fname] = _sha256(dst_dir / fname)
    for fname in COPY_DELIVERY_FILES:
        src = src_dir / "delivery" / fname
        if src.exists():
            (dst_dir / "delivery").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst_dir / "delivery" / fname)
            copied[f"delivery/{fname}"] = _sha256(dst_dir / "delivery" / fname)

    for rel, digest in copied.items():
        if _sha256(src_dir / rel) != digest:
            raise SystemExit(f"Kopie weicht von der Quelle ab: {rel}")

    record = {
        "derived_project_id": derived.project_id,
        "source_project_id": source_id,
        "version_label": version_label,
        "derived_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Lieferung ohne neue Klassifikation: Mappings und Klassifikationsergebnisse "
                   "byte-identisch aus dem Quellprojekt, Integrationsentscheidungen neu.",
        "copied_sha256": copied,
        "not_copied": ["disjoint_decisions.json", "delivery/*.ttl", "delivery/*.md"],
    }
    (dst_dir / "derivation.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return derived


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version-label", required=True)
    parser.add_argument("--description", default=None)
    args = parser.parse_args()
    derived = derive(args.source, args.name, args.version_label, args.description)
    print(f"Abgeleitet: {derived.project_id}  (parent={derived.parent_project_id})")


if __name__ == "__main__":
    main()
