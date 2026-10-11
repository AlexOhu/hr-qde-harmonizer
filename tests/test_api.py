from fastapi.testclient import TestClient
from rdflib import Graph

from app.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_kqr_starts_empty(isolated_services):
    response = client.get("/kqr/")
    assert response.status_code == 200
    assert response.json() == []


def test_upload_kqr_registers_and_lists(isolated_services, hub_ttl, mock_sentence_transformer):
    response = client.post(
        "/kqr/",
        data={"name": "Hub KQR", "source_format": "turtle", "is_hub": "true"},
        files={"file": ("hub.ttl", hub_ttl.encode("utf-8"), "text/turtle")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "formalisiert"
    assert body["concept_count"] == 6
    assert body["is_hub"] is True

    listed = client.get("/kqr/").json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_upload_kqr_rejects_invalid_turtle_without_registering_it(isolated_services):
    response = client.post(
        "/kqr/",
        data={"name": "Broken KQR", "source_format": "turtle", "is_hub": "false"},
        files={"file": ("broken.ttl", b"this is not turtle", "text/turtle")},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["errors"]
    assert client.get("/kqr/").json() == []


def test_download_skos_template_returns_turtle():
    response = client.get("/kqr/template")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/turtle")
    assert b"skos:ConceptScheme" in response.content


def test_upload_rdf_xml_is_normalised_and_formalised(
    isolated_services, hub_ttl, mock_sentence_transformer
):
    graph = Graph()
    graph.parse(data=hub_ttl, format="turtle")
    rdf_xml = graph.serialize(format="xml")

    response = client.post(
        "/kqr/",
        data={"name": "RDF KQR", "source_format": "rdf", "is_hub": "false"},
        files={"file": ("hub.rdf", rdf_xml.encode("utf-8"), "application/rdf+xml")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "formalisiert"


def test_get_status_for_unknown_kqr_returns_404(isolated_services):
    response = client.get("/kqr/does-not-exist/status")
    assert response.status_code == 404


def test_classification_preconditions_reports_missing_llm_key(isolated_services, monkeypatch):
    from app.config import settings

    # Testet den Fall "kein Anbieter konfiguriert" -- muss LLM_PROVIDERS
    # selbst festlegen, sonst haengt das Ergebnis vom lokalen .env ab
    # (z.B. LLM_PROVIDERS=mistral mit gesetztem mistral_api_key).
    monkeypatch.setattr(settings, "llm_providers", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    response = client.get("/classification/preconditions")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_configured"] is False
    assert "neo4j_reachable" in body


def test_export_summary_starts_at_zero(isolated_services):
    response = client.get("/export/summary")
    assert response.status_code == 200
    assert response.json()["total_open"] == 0
