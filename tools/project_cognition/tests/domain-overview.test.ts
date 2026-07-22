import assert from "node:assert/strict";
import test from "node:test";
import { emptySnapshot } from "../src/domain/model.js";
import { buildDomainOverview, UNCLASSIFIED_DOMAIN_ID } from "../src/query/domain-overview.js";

test("domain overview projects unassigned symbols into a non-persistent unclassified domain", () => {
  const snapshot = emptySnapshot("AISc");
  snapshot.domains.push({ id: "known", projectId: "AISc", name: "Known", summary: "", status: "confirmed", source: "manual", locked: true });
  snapshot.symbols.push({ id: "assigned", projectId: "AISc", language: "C#", kind: "Class", filePath: "a.cs", qualifiedName: "A", analyzerIdentity: "A" }, { id: "orphan", projectId: "AISc", language: "C#", kind: "Class", filePath: "b.cs", qualifiedName: "B", analyzerIdentity: "B" });
  snapshot.memberships.push({ id: "membership", domainId: "known", symbolId: "assigned", type: "primary", status: "confirmed", source: "manual", locked: true });
  const overview = buildDomainOverview(snapshot);
  assert.ok(overview.domains.some(item => item.id === UNCLASSIFIED_DOMAIN_ID && item.status === "proposed"));
  assert.deepEqual(overview.memberships.filter(item => item.domainId === UNCLASSIFIED_DOMAIN_ID).map(item => item.symbolId), ["orphan"]);
  assert.deepEqual(overview.symbols.map(item => item.id).sort(), ["assigned", "orphan"]);
  assert.equal(snapshot.domains.length, 1);
  assert.equal(snapshot.memberships.length, 1);
});

test("domain overview omits the virtual domain when every symbol is assigned", () => {
  const snapshot = emptySnapshot("AISc");
  snapshot.domains.push({ id: "known", projectId: "AISc", name: "Known", summary: "", status: "confirmed", source: "manual", locked: true });
  snapshot.symbols.push({ id: "assigned", projectId: "AISc", language: "C#", kind: "Class", filePath: "a.cs", qualifiedName: "A", analyzerIdentity: "A" });
  snapshot.memberships.push({ id: "membership", domainId: "known", symbolId: "assigned", type: "primary", status: "confirmed", source: "manual", locked: true });
  assert.ok(!buildDomainOverview(snapshot).domains.some(item => item.id === UNCLASSIFIED_DOMAIN_ID));
});
