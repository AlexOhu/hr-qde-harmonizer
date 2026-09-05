/**
 * Ableitung der Framework-Paare aus dem Pipelinestatus.
 *
 * Diese Logik ist die einzige Stelle, an der die UI etwas aus Backendwerten
 * zusammensetzt — entsprechend genau geprueft.
 */

import { describe, expect, it } from "vitest";

import {
  countActionableReviews,
  countUnresolved,
  derivePairLifecycle,
  derivePairs,
  pairHasOpenWork,
  runsForPair,
} from "./status";
import { makeJob, makePairStatus } from "@/test/utils";

describe("derivePairLifecycle", () => {
  it("meldet einen laufenden Job unabhängig von offenen Reviews", () => {
    const lifecycle = derivePairLifecycle(
      makePairStatus({ job_status: "running", pending_review_count: 12 }),
    );
    expect(lifecycle).toBe("running");
  });

  it("verlangt Review, solange Mappings unter der Schwelle offen sind", () => {
    expect(derivePairLifecycle(makePairStatus({ pending_review_count: 12 }))).toBe(
      "review_required",
    );
  });

  it("behandelt UNRESOLVED-Fälle ebenfalls als offenen Review", () => {
    expect(derivePairLifecycle(makePairStatus({ unresolved_count: 3 }))).toBe("review_required");
  });

  it("verlangt Integration erst, wenn der Review abgeschlossen ist", () => {
    expect(
      derivePairLifecycle(
        makePairStatus({ pending_review_count: 0, unresolved_count: 0, disjoint_open: 4 }),
      ),
    ).toBe("integration_required");
  });

  it("gilt als abgeschlossen, wenn nichts mehr offen ist", () => {
    expect(derivePairLifecycle(makePairStatus())).toBe("complete");
  });

  it("bildet Fehlerzustände ab", () => {
    expect(derivePairLifecycle(makePairStatus({ job_status: "failed" }))).toBe("failed");
    expect(derivePairLifecycle(makePairStatus({ job_status: "interrupted" }))).toBe("interrupted");
    expect(derivePairLifecycle(makePairStatus({ job_status: "paused" }))).toBe("paused");
    expect(derivePairLifecycle(makePairStatus({ job_status: null }))).toBe("not_started");
  });
});

describe("derivePairs", () => {
  it("fasst mehrere Läufe desselben Paares zu einem Eintrag zusammen", () => {
    // Das Backend liefert einen Eintrag pro Job, nicht pro Paar.
    const pairs = derivePairs([
      makePairStatus({ job_id: "job_a", job_status: "interrupted", classified_pairs: 395 }),
      makePairStatus({ job_id: "job_b", job_status: "completed", classified_pairs: 900 }),
    ]);

    expect(pairs).toHaveLength(1);
    expect(pairs[0].leadingJobId).toBe("job_b");
    expect(pairs[0].lifecycle).toBe("complete");
  });

  it("bevorzugt einen laufenden Job als maßgeblichen Lauf", () => {
    const pairs = derivePairs([
      makePairStatus({ job_id: "old", job_status: "completed" }),
      makePairStatus({ job_id: "new", job_status: "running", classified_pairs: 100 }),
    ]);

    expect(pairs[0].leadingJobId).toBe("new");
    expect(pairs[0].lifecycle).toBe("running");
  });

  it("behandelt die Paar-Reihenfolge als unerheblich", () => {
    const pairs = derivePairs([
      makePairStatus({ kqr_a_id: "ecf", kqr_b_id: "esco", job_id: "a" }),
      makePairStatus({ kqr_a_id: "esco", kqr_b_id: "ecf", job_id: "b" }),
    ]);

    expect(pairs).toHaveLength(1);
  });

  it("rechnet den Fortschritt aus klassifizierten und gesamten Konzeptpaaren", () => {
    const pairs = derivePairs([
      makePairStatus({ job_status: "running", classified_pairs: 450, total_pairs: 900 }),
    ]);

    expect(pairs[0].percent).toBe(50);
  });

  it("zählt die Läufe eines Paares für die Historie", () => {
    const pairs = derivePairs(
      [makePairStatus({ job_id: "job_1" })],
      [makeJob({ job_id: "job_1" }), makeJob({ job_id: "job_2" })],
    );

    expect(pairs[0].runCount).toBe(2);
  });
});

describe("runsForPair", () => {
  it("liefert die Läufe eines Paares mit dem neuesten zuerst", () => {
    const runs = runsForPair(
      [
        makeJob({ job_id: "alt", started_at: "2026-08-01T08:00:00+00:00" }),
        makeJob({ job_id: "neu", started_at: "2026-08-20T08:00:00+00:00" }),
        makeJob({ job_id: "fremd", kqr_a_id: "dqr", kqr_b_id: "esco" }),
      ],
      "ecf",
      "esco",
    );

    expect(runs.map((run) => run.job_id)).toEqual(["neu", "alt"]);
  });
});

describe("pairHasOpenWork", () => {
  it("erkennt offene Arbeit aus Review und Integration", () => {
    const [complete] = derivePairs([makePairStatus()]);
    const [withReview] = derivePairs([makePairStatus({ pending_review_count: 1 })]);
    const [withIntegration] = derivePairs([makePairStatus({ disjoint_open: 1 })]);

    expect(pairHasOpenWork(complete)).toBe(false);
    expect(pairHasOpenWork(withReview)).toBe(true);
    expect(pairHasOpenWork(withIntegration)).toBe(true);
  });
});

describe("Zählung offener Reviews", () => {
  it("zählt UNRESOLVED nicht als bearbeitbaren Review", () => {
    // Regression: `GET /mappings/` liefert UNRESOLVED-Fälle nie -- sie werden
    // nicht persistiert. Beide Zahlen zu addieren versprach in der
    // Mapping-Ansicht Arbeit, die dort gar nicht erscheint.
    const pairs = derivePairs([
      makePairStatus({ pending_review_count: 0, unresolved_count: 48 }),
    ]);

    expect(countActionableReviews(pairs)).toBe(0);
    expect(countUnresolved(pairs)).toBe(48);
  });

  it("summiert bearbeitbare Reviews über alle Paare", () => {
    const pairs = derivePairs([
      makePairStatus({ kqr_a_id: "ecf", pending_review_count: 5, unresolved_count: 2 }),
      makePairStatus({ kqr_a_id: "dqr", pending_review_count: 7, unresolved_count: 3 }),
    ]);

    expect(countActionableReviews(pairs)).toBe(12);
    expect(countUnresolved(pairs)).toBe(5);
  });
});
