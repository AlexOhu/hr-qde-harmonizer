import json
import threading
import time

from app.pipeline.step4_export.sssom_writer import write_sssom_tsv
from app.services import classification_service, kqr_service, mapping_service


def test_end_to_end_pipeline_produces_sssom(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic, tmp_path
):
    """Registriert Fixture-KQR, lässt sie klassifizieren (LLM gemockt) und
    prüft, dass sowohl der strukturelle Shortcut als auch LLM-Mappings in
    der resultierenden SSSOM-TSV landen (End-to-End-Verdrahtung von
    kqr_service, classification_service, mapping_service, sssom_writer)."""
    mock_anthropic("EQUIVALENT | Testbegründung")

    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR",
        source_format="turtle",
        filename="hub.ttl",
        content=hub_ttl.encode("utf-8"),
        is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR",
        source_format="turtle",
        filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"),
        is_hub=False,
    )

    assert hub_kqr.status == "bereit"
    assert satellite_kqr.status == "bereit"

    job_id = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)

    deadline = time.time() + 20
    progress = classification_service.get_job_progress(job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.1)
        progress = classification_service.get_job_progress(job_id)

    assert progress["status"] == "completed", progress

    mappings = mapping_service.list_mappings()
    assert any(m.mapping_justification.value == "semapv:StructuralMatching" for m in mappings)
    assert any(m.mapping_justification.value == "semapv:LLMBasedMatching" for m in mappings)

    # Der strukturelle Shortcut (level_5 -> eqf_level_6) darf den
    # LLM-Klassifikator nicht durchlaufen haben (kein doppeltes Mapping).
    struct_pairs = {(m.subject_id, m.object_id) for m in mappings if m.mapping_justification.value == "semapv:StructuralMatching"}
    llm_pairs = {(m.subject_id, m.object_id) for m in mappings if m.mapping_justification.value == "semapv:LLMBasedMatching"}
    assert struct_pairs.isdisjoint(llm_pairs)

    output_path = tmp_path / "export.tsv"
    write_sssom_tsv(mappings, output_path, confidence_threshold=0.0)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    header = next(line for line in lines if not line.startswith("#")).split("\t")
    for field in [
        "subject_id",
        "object_id",
        "predicate_id",
        "mapping_confidence",
        "mapping_tool",
        "mapping_justification",
        "comment",
        "mapping_source",
        "author_id",
    ]:
        assert field in header


def test_restarted_job_skips_already_classified_pairs(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic
):
    """Simuliert einen uvicorn---reload-Neustart mitten im Klassifikationslauf
    (_jobs wird geleert, wie es ein Prozess-Neustart täte) und prüft, dass ein
    erneuter start_classification_job()-Aufruf für dasselbe KQR-Paar keine
    bereits klassifizierten Paare erneut an das LLM schickt -- der eigentliche
    Kostenschutz hinter der inkrementellen Persistenz in mapping_service."""
    provider = mock_anthropic("EQUIVALENT | Testbegründung")

    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )

    job_id = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)
    deadline = time.time() + 20
    progress = classification_service.get_job_progress(job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
        progress = classification_service.get_job_progress(job_id)
    assert progress["status"] == "completed", progress

    calls_after_first_run = len(provider.calls)
    assert calls_after_first_run > 0

    # Prozess-Neustart simulieren: _jobs (In-Memory-Job-Registry) geleert,
    # persistierte Mappings/ClassificationResults bleiben unberührt.
    classification_service._jobs.clear()

    second_job_id = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)
    deadline = time.time() + 20
    progress = classification_service.get_job_progress(second_job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
        progress = classification_service.get_job_progress(second_job_id)
    assert progress["status"] == "completed", progress
    assert progress["done_pairs"] == progress["total_pairs"]

    # Kein einziger zusätzlicher LLM-Aufruf für die bereits entschiedenen Paare.
    assert len(provider.calls) == calls_after_first_run


def test_pause_job_stops_before_next_pair_and_resume_continues(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic
):
    """pause_job() muss vor dem nächsten Paar greifen (kein Abbruch mitten in
    einem laufenden LLM-Aufruf) und resume_job() muss exakt dort weitermachen,
    ohne bereits entschiedene Paare erneut zu klassifizieren."""

    pause_after_first_call = threading.Event()

    def _response(_prompt: str) -> str:
        pause_after_first_call.set()
        return "EQUIVALENT | Testbegründung"

    provider = mock_anthropic(_response)

    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )

    job_id = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)

    assert pause_after_first_call.wait(timeout=10), "Kein LLM-Aufruf innerhalb des Timeouts erfolgt"
    classification_service.pause_job(job_id)

    deadline = time.time() + 20
    progress = classification_service.get_job_progress(job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.02)
        progress = classification_service.get_job_progress(job_id)

    assert progress["status"] == "paused", progress
    assert 0 < progress["done_pairs"] < progress["total_pairs"]
    # Alle Aufrufe vor der Pause galten ausschließlich dem einen (vollständig
    # abgeschlossenen) ersten Paar -- Pause wirkt erst zwischen zwei Paaren.
    first_pair_prompt = provider.calls[0]
    calls_for_first_pair_before_resume = provider.calls.count(first_pair_prompt)

    classification_service.resume_job(job_id)
    deadline = time.time() + 20
    progress = classification_service.get_job_progress(job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.02)
        progress = classification_service.get_job_progress(job_id)

    assert progress["status"] == "completed", progress
    assert progress["done_pairs"] == progress["total_pairs"]
    # Das vor der Pause bereits entschiedene erste Paar darf nach dem
    # Fortsetzen nicht erneut an das LLM geschickt worden sein (identischer
    # Prompt -> Aufrufzahl für dieses Paar bleibt unverändert).
    assert provider.calls.count(first_pair_prompt) == calls_for_first_pair_before_resume


def test_list_jobs_shows_concurrently_started_jobs(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic
):
    """Zwei unabhängig gestartete Jobs müssen beide über list_jobs()
    sichtbar sein -- Grundlage für die UI-Fortschrittsanzeige, die nicht nur
    den zuletzt in der eigenen Browser-Session gestarteten Job zeigen soll."""
    mock_anthropic("EQUIVALENT | Testbegründung")

    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )

    job_id_1 = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)
    job_id_2 = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)

    deadline = time.time() + 20
    while time.time() < deadline and any(
        job["status"] == "running" for job in classification_service.list_jobs()
    ):
        time.sleep(0.05)

    jobs_by_id = {job["job_id"]: job for job in classification_service.list_jobs()}
    assert {job_id_1, job_id_2} <= jobs_by_id.keys()
    assert jobs_by_id[job_id_1]["status"] == "completed"
    assert jobs_by_id[job_id_2]["status"] == "completed"


def test_load_jobs_marks_stale_running_jobs_as_interrupted(isolated_services):
    """Ein von der Platte geladener Job mit status='running' kann unmöglich
    einen laufenden Thread haben -- Threads überleben keinen Prozess-Neustart
    (z. B. durch uvicorn --reload). _load_jobs() muss ihn deshalb auf
    'interrupted' korrigieren, statt ihn für immer als aktiv erscheinen zu
    lassen (sonst würde er in der 'alle Jobs'-UI ewig als laufend gezeigt)."""
    jobs_path = classification_service._jobs_path("default")
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(
        json.dumps(
            {
                "abc": {
                    "job_id": "abc",
                    "kqr_a_id": "a",
                    "kqr_b_id": "b",
                    "status": "running",
                    "done_pairs": 3,
                    "total_pairs": 10,
                    "error": None,
                }
            }
        ),
        encoding="utf-8",
    )

    loaded = classification_service._load_jobs("default")
    assert loaded["abc"]["status"] == "interrupted"


def test_resume_job_continues_interrupted_job(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic
):
    """resume_job() muss nicht nur pausierte, sondern auch durch einen
    Prozess-Neustart unterbrochene Jobs (status='interrupted') unter
    derselben Job-ID fortsetzen können."""
    mock_anthropic("EQUIVALENT | Testbegründung")

    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )

    job_id = "fake-interrupted-job"
    classification_service._get_project_jobs("default")[job_id] = {
        "job_id": job_id,
        "kqr_a_id": hub_kqr.id,
        "kqr_b_id": satellite_kqr.id,
        "status": "interrupted",
        "done_pairs": 0,
        "total_pairs": 0,
        "error": None,
    }

    classification_service.resume_job(job_id)
    deadline = time.time() + 20
    progress = classification_service.get_job_progress(job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
        progress = classification_service.get_job_progress(job_id)

    assert progress["status"] == "completed", progress


def test_open_review_summary_counts_no_consensus_and_related(
    isolated_services, hub_ttl, satellite_ttl, mock_sentence_transformer, mock_anthropic
):
    """Simuliert einen Klassifikationslauf, bei dem jeder der drei Läufe pro
    Paar eine andere Relation liefert (kein Mehrheitsentscheid), um zu
    prüfen, dass export_summary() diese Fälle ohne Mehrheitsentscheid sichtbar
    macht (Gatekeeping-Prinzip, Funktionsgruppe 5)."""
    responses = iter(
        ["EQUIVALENT | a", "A_SUBSUMES_B | b", "RELATED | c"] * 100
    )
    mock_anthropic(lambda messages: next(responses))

    hub_kqr = kqr_service.register_kqr(
        name="Hub KQR", source_format="turtle", filename="hub.ttl",
        content=hub_ttl.encode("utf-8"), is_hub=True,
    )
    satellite_kqr = kqr_service.register_kqr(
        name="Satellite KQR", source_format="turtle", filename="satellite.ttl",
        content=satellite_ttl.encode("utf-8"), is_hub=False,
    )

    job_id = classification_service.start_classification_job(hub_kqr.id, satellite_kqr.id)
    deadline = time.time() + 20
    progress = classification_service.get_job_progress(job_id)
    while progress["status"] == "running" and time.time() < deadline:
        time.sleep(0.1)
        progress = classification_service.get_job_progress(job_id)
    assert progress["status"] == "completed", progress

    summary = mapping_service.get_open_review_summary()
    assert summary["no_consensus_pairs"] > 0
    assert summary["total_open"] >= summary["no_consensus_pairs"]
