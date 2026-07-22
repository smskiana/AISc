import assert from "node:assert/strict";
import test from "node:test";
import { emptySnapshot } from "../src/domain/model.js";
import { checkScopeFreshness, expandRelationEvidence, getPrimaryRelations } from "../src/query/query-service.js";

test("primary relations sort by importance and expand valid evidence", () => {
  const snapshot = emptySnapshot("AISc", "rev-1");
  snapshot.facts.push({ id: "fact-1", sourceSymbolId: "a", targetSymbolId: "b", type: "CALLS", evidenceIds: [], external: false });
  snapshot.semantics.push({ id: "low", sourceSymbolId: "a", targetSymbolId: "b", summary: "low", evidenceIds: [], status: "proposed", source: "fixture", importance: 1 }, { id: "high", sourceSymbolId: "a", targetSymbolId: "b", summary: "high", evidenceIds: ["fact-1", "missing"], status: "confirmed", source: "manual", importance: 10 });
  assert.deepEqual(getPrimaryRelations(snapshot, "a").map(item => item.id), ["high", "low"]);
  const expanded = expandRelationEvidence(snapshot, "high", 10)!;
  assert.deepEqual(expanded.evidence.map(item => item.id), ["fact-1"]);
  assert.deepEqual(expanded.missingEvidenceIds, ["missing"]);
  assert.equal(checkScopeFreshness(snapshot, "rev-2").status, "stale");
});
