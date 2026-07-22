import assert from "node:assert/strict";
import test from "node:test";
import { emptySnapshot } from "../src/domain/model.js";
import { buildScopeView } from "../src/scope/scope-view.js";

test("scope view exposes signed symbol details and estimated cost", () => {
  const snapshot = emptySnapshot("AISc");
  snapshot.domains.push({ id: "target", projectId: "AISc", name: "Target", summary: "", status: "confirmed", source: "manual", locked: true }, { id: "other", projectId: "AISc", name: "Other", summary: "", status: "confirmed", source: "manual", locked: true });
  snapshot.memberships.push({ id: "m", domainId: "other", symbolId: "b", type: "primary", status: "confirmed", source: "manual", locked: true });
  const symbols = ["a", "b", "c"].map((id, index) => ({ id, projectId: "AISc", language: "C#", kind: "Method", filePath: `f${index}.cs`, qualifiedName: id, analyzerIdentity: id }));
  const scope = { scopeId: "scope", baseSnapshotId: snapshot.id, requestedScope: ["a", "b", "c"], resolvedScope: ["a", "b"], evidenceScope: ["a", "b"], mutationScope: ["a"], excluded: ["c"], warnings: ["CROSS_DOMAIN_READ_ONLY"], exploration: false, expiresAt: new Date(Date.now() + 60_000).toISOString(), scopeHash: "hash", codeRevision: "rev" };
  const view = buildScopeView(snapshot, scope, symbols, { maxFiles: 2, maxSymbols: 2, maxRelations: 10 }, "target");
  assert.deepEqual(view.includedSymbols.map(item => item.id), ["a"]);
  assert.deepEqual(view.readOnlyEvidence.map(item => item.id), ["b"]);
  assert.deepEqual(view.excludedSymbols.map(item => item.id), ["c"]);
  assert.deepEqual(view.excludedDomains.map(item => item.id), ["other"]);
  assert.deepEqual(view.estimatedCost, { files: 2, symbols: 2, relationsBudget: 10 });
});
