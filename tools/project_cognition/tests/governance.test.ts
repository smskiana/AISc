import assert from "node:assert/strict";
import test from "node:test";
import { emptySnapshot } from "../src/domain/model.js";
import { confirmDomainStructure, rejectProposal, setSymbolMembership, updateManualSummary } from "../src/governance/governance-service.js";

test("manual governance confirms and protects cognition", () => {
  const snapshot = emptySnapshot("AISc");
  snapshot.domains.push({ id: "domain", projectId: "AISc", name: "Domain", summary: "", status: "proposed", source: "ai", locked: false });
  snapshot.symbols.push({ id: "symbol", projectId: "AISc", language: "C#", kind: "Class", filePath: "a.cs", qualifiedName: "A", analyzerIdentity: "A" });
  const confirmed = confirmDomainStructure(snapshot, ["domain"]);
  const assigned = setSymbolMembership(confirmed, "symbol", "domain", "primary", true);
  const summarized = updateManualSummary(assigned, "symbol", "Manual responsibility");
  assert.equal(summarized.domains[0].status, "confirmed");
  assert.equal(summarized.memberships[0].source, "manual");
  assert.equal(summarized.symbols[0].summary, "Manual responsibility");
  assert.throws(() => setSymbolMembership(summarized, "symbol", "domain", "secondary", false), /Locked membership/);
});

test("reject proposal removes only proposed content", () => {
  const snapshot = emptySnapshot("AISc");
  snapshot.semantics.push({ id: "proposal", sourceSymbolId: "a", targetSymbolId: "b", summary: "x", evidenceIds: [], status: "proposed", source: "fixture" });
  assert.equal(rejectProposal(snapshot, "proposal").semantics.length, 0);
  assert.throws(() => rejectProposal(snapshot, "missing"), /PROPOSAL_NOT_FOUND/);
});
