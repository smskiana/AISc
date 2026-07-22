import assert from "node:assert/strict";
import path from "node:path";
import { JsonSnapshotStore } from "../src/adapters/snapshot-store/json-store.js";
import { buildDomainOverview, UNCLASSIFIED_DOMAIN_ID } from "../src/query/domain-overview.js";

/** Verifies that the current local snapshot remains reachable without creating a formal domain. */
async function main(): Promise<void> {
  const stateRoot = process.env.PROJECT_COGNITION_STATE_DIR ?? path.resolve("../..", ".project-cognition");
  const snapshot = await new JsonSnapshotStore(stateRoot).load("AISc");
  const persistedDomainCount = snapshot.domains.length;
  const persistedMembershipCount = snapshot.memberships.length;
  const overview = buildDomainOverview(snapshot);
  const virtual = overview.domains.find(item => item.id === UNCLASSIFIED_DOMAIN_ID);
  const virtualMemberships = overview.memberships.filter(item => item.domainId === UNCLASSIFIED_DOMAIN_ID);
  assert.ok(virtual, "Current snapshot must expose an unclassified view when symbols lack membership.");
  assert.equal(virtualMemberships.length, snapshot.symbols.filter(symbol => !snapshot.memberships.some(item => item.symbolId === symbol.id)).length);
  assert.equal(snapshot.domains.length, persistedDomainCount);
  assert.equal(snapshot.memberships.length, persistedMembershipCount);
  console.log(JSON.stringify({ ok: true, persistedDomains: persistedDomainCount, persistedMemberships: persistedMembershipCount, visibleSymbols: virtualMemberships.length }));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
