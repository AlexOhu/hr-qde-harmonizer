"""Mistral-Implementierung von LLMProvider.

Lazy-Import von mistralai — das Paket muss nur installiert sein, wenn dieser
Provider konfiguriert wird (LLM_PROVIDERS=mistral).
Installation: pip install mistralai>=1.0

Mistral bietet starke mehrsprachige Modelle, die für den europäischen
IKT-Kontext des HR-QDE besonders geeignet sind (EU-Rechenzentren, DSGVO).
Empfohlene Modelle: mistral-small-latest, mistral-medium-latest, open-mistral-nemo
"""

from __future__ import annotations

import os
import random
import re
import threading
import time

from .base import LLMProvider

# Bei Klassifikationsläufen über mehrere tausend Paare wurden wiederholt
# kurze Ausfälle des Mistral-Gateways beobachtet (Status 503 "upstream
# connect error/timeout") sowie Rate-Limits (Status 429).
# classification_service._run_job markiert bei JEDER Exception den gesamten
# Job als "failed" (vgl. Kosten-/Absturzschutz dort) -- ohne Retry würde ein
# einzelner transienter Blip einen mehrstündigen Lauf abbrechen. 429/5xx
# gelten als vorübergehend und werden erneut versucht; alles andere (z.B. 401
# Authentifizierung, 400 ungültige Anfrage) wird sofort durchgereicht, da ein
# Retry daran nichts ändern würde.
#
# Über Umgebungsvariablen justierbar (Standard = bisheriges Verhalten):
#   MISTRAL_MAX_ATTEMPTS            (Standard 3)
#   MISTRAL_RETRY_BACKOFF_SECONDS   (Standard 5.0; effektiv backoff*Versuch + Jitter)
#   MISTRAL_MIN_REQUEST_INTERVAL_S  (Standard 0 = aus; prozessweiter Mindest-
#                                    abstand zwischen zwei Requests, hilft gegen
#                                    429 bei großen Läufen)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = int(os.getenv("MISTRAL_MAX_ATTEMPTS", "3"))
_RETRY_BACKOFF_SECONDS = float(os.getenv("MISTRAL_RETRY_BACKOFF_SECONDS", "5.0"))
_MIN_REQUEST_INTERVAL_S = float(os.getenv("MISTRAL_MIN_REQUEST_INTERVAL_S", "0"))

_rate_lock = threading.Lock()
_last_request_ts = 0.0


def _status_from_error(exc: Exception) -> int | None:
    """Holt den HTTP-Status aus einer mistralai-Ausnahme.

    Je nach Paketversion trägt die Ausnahme den Status als Attribut
    ``status_code``, als ``raw_response.status_code`` (httpx.Response) oder
    nur im Meldungstext ("... Status 429 ..."). Alle drei Wege werden
    geprüft, damit die Retry-Entscheidung nicht von der SDK-Version abhängt.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        raw = getattr(exc, "raw_response", None)
        status = getattr(raw, "status_code", None)
    if status is None:
        match = re.search(r"[Ss]tatus[ _]?(?:code[ :=]*)?(\d{3})", str(exc))
        if match:
            status = int(match.group(1))
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


class MistralProvider(LLMProvider):
    """LLMProvider-Implementierung für Mistral AI."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.0) -> None:
        try:
            from mistralai.client import Mistral
            from mistralai.client.errors import MistralError
        except ImportError as exc:
            raise ImportError(
                "Das Paket 'mistralai' ist nicht installiert. "
                "Bitte 'pip install mistralai>=1.0' ausführen."
            ) from exc

        self._client = Mistral(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._error_cls = MistralError

    @property
    def model_id(self) -> str:
        return f"mistral/{self._model}"

    def _throttle(self) -> None:
        """Erzwingt prozessweit (threadübergreifend) einen Mindestabstand
        zwischen zwei API-Requests, wenn MISTRAL_MIN_REQUEST_INTERVAL_S > 0
        ist. Standard 0 -> kein Effekt."""
        if _MIN_REQUEST_INTERVAL_S <= 0:
            return
        global _last_request_ts
        with _rate_lock:
            wait = _MIN_REQUEST_INTERVAL_S - (time.monotonic() - _last_request_ts)
            if wait > 0:
                time.sleep(wait)
            _last_request_ts = time.monotonic()

    def complete(self, prompt: str, max_tokens: int = 200) -> str:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            self._throttle()
            try:
                response = self._client.chat.complete(
                    model=self._model,
                    temperature=self._temperature,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return (response.choices[0].message.content or "").strip()
            except self._error_cls as exc:
                status = _status_from_error(exc)
                is_last_attempt = attempt == _MAX_ATTEMPTS
                if status not in _RETRYABLE_STATUS_CODES or is_last_attempt:
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS * attempt + random.uniform(0.0, 1.5))
