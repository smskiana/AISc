import { randomUUID } from "node:crypto";
import { CognitionError } from "../domain/errors.js";
import { MembershipType, ProjectSnapshot } from "../domain/model.js";

/** Confirms proposed domains without allowing locked structure to move. */
export function confirmDomainStructure(snapshot: ProjectSnapshot, domainIds: string[]): ProjectSnapshot {
  const requested = new Set(domainIds);
  if (domainIds.some(id => !snapshot.domains.some(domain => domain.id === id))) throw new CognitionError("DOMAIN_NOT_FOUND");
  return nextSnapshot(snapshot, { domains: snapshot.domains.map(domain => requested.has(domain.id) ? { ...domain, status: "confirmed", source: "manual", lastReviewedRevision: snapshot.codeRevision } : domain) });
}

/** Sets one membership while preserving locked records and one-primary identity. */
export function setSymbolMembership(snapshot: ProjectSnapshot, symbolId: string, domainId: string, type: MembershipType, locked: boolean): ProjectSnapshot {
  if (!snapshot.symbols.some(symbol => symbol.id === symbolId)) throw new CognitionError("SYMBOL_NOT_FOUND");
  if (!snapshot.domains.some(domain => domain.id === domainId)) throw new CognitionError("DOMAIN_NOT_FOUND");
  const conflicting = snapshot.memberships.find(item => item.symbolId === symbolId && item.locked && (item.domainId !== domainId || item.type !== type));
  if (conflicting) throw new CognitionError("LOCKED_CONTENT_CONFLICT", "Locked membership cannot be replaced.", { membershipId: conflicting.id });
  let memberships = snapshot.memberships.filter(item => !(item.symbolId === symbolId && item.domainId === domainId));
  if (type === "primary") memberships = memberships.filter(item => item.symbolId !== symbolId || item.type !== "primary" || item.locked);
  memberships.push({ id: randomUUID(), domainId, symbolId, type, status: "confirmed", source: "manual", locked });
  return nextSnapshot(snapshot, { memberships });
}

/** Stores a manual symbol summary and protects it from automatic replacement. */
export function updateManualSummary(snapshot: ProjectSnapshot, symbolId: string, summary: string): ProjectSnapshot {
  if (!snapshot.symbols.some(symbol => symbol.id === symbolId)) throw new CognitionError("SYMBOL_NOT_FOUND");
  return nextSnapshot(snapshot, { symbols: snapshot.symbols.map(symbol => symbol.id === symbolId ? { ...symbol, summary, status: "confirmed", source: "manual", locked: true } : symbol) });
}

/** Rejects one proposed domain, membership, or semantic relation. */
export function rejectProposal(snapshot: ProjectSnapshot, proposalId: string): ProjectSnapshot {
  const proposed = snapshot.domains.some(item => item.id === proposalId && item.status === "proposed") || snapshot.memberships.some(item => item.id === proposalId && item.status === "proposed") || snapshot.semantics.some(item => item.id === proposalId && item.status === "proposed");
  if (!proposed) throw new CognitionError("PROPOSAL_NOT_FOUND");
  return nextSnapshot(snapshot, { domains: snapshot.domains.filter(item => item.id !== proposalId), memberships: snapshot.memberships.filter(item => item.id !== proposalId), semantics: snapshot.semantics.filter(item => item.id !== proposalId) });
}

/** Creates the next immutable snapshot head for a governance change. */
function nextSnapshot(snapshot: ProjectSnapshot, changes: Partial<ProjectSnapshot>): ProjectSnapshot {
  return { ...snapshot, ...changes, id: randomUUID(), parentSnapshotId: snapshot.id, createdAt: new Date().toISOString() };
}
