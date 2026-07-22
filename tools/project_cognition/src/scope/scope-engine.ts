import { randomUUID } from "node:crypto";
import { CodeSymbol, FunctionalDomain, ProjectSnapshot, stableHash } from "../domain/model.js";

export interface ScopeBudget { maxFiles: number; maxSymbols: number; maxRelations: number; }
export interface ScopeRequest { projectId: string; query: string; seedSymbols: CodeSymbol[]; requestedDomainId?: string; fullUpdate?: boolean; explicitConfirmation?: string; codeRevision?: string; }
export interface ScopeResolution {
  scopeId: string;
  baseSnapshotId: string;
  requestedScope: string[];
  resolvedScope: string[];
  evidenceScope: string[];
  mutationScope: string[];
  excluded: string[];
  warnings: string[];
  exploration: boolean;
  expiresAt: string;
  scopeHash: string;
  codeRevision: string;
}

/** Signs a deterministic, budget-limited update scope without mutating cognition. */
export function resolveScope(request: ScopeRequest, snapshot: ProjectSnapshot, budget: ScopeBudget): ScopeResolution {
  if (request.fullUpdate && request.explicitConfirmation !== `FULL UPDATE ${request.projectId}`) throw new Error("FULL_UPDATE_CONFIRMATION_REQUIRED");
  const unique = [...new Map(request.seedSymbols.map(symbol => [symbol.id, symbol])).values()];
  const files = new Set<string>();
  const accepted: CodeSymbol[] = [];
  const excluded: string[] = [];
  for (const symbol of unique) {
    if (accepted.length >= budget.maxSymbols || (!files.has(symbol.filePath) && files.size >= budget.maxFiles)) excluded.push(symbol.id);
    else { accepted.push(symbol); files.add(symbol.filePath); }
  }
  const domain = snapshot.domains.find(item => item.id === request.requestedDomainId);
  const existingMembership = new Map(snapshot.memberships.map(item => [item.symbolId, item.domainId]));
  const mutation = request.fullUpdate ? accepted : accepted.filter(symbol => !domain || existingMembership.get(symbol.id) === domain.id || !existingMembership.has(symbol.id));
  const warnings = excluded.length ? ["SCOPE_BUDGET_EXCEEDED"] : [];
  if (mutation.length < accepted.length) warnings.push("CROSS_DOMAIN_READ_ONLY");
  const codeRevision = request.codeRevision ?? snapshot.codeRevision;
  const payload = { baseSnapshotId: snapshot.id, codeRevision, requested: unique.map(x => x.id), resolved: accepted.map(x => x.id), evidence: accepted.map(x => x.id), mutation: mutation.map(x => x.id) };
  return { scopeId: randomUUID(), baseSnapshotId: snapshot.id, requestedScope: payload.requested, resolvedScope: payload.resolved, evidenceScope: payload.evidence, mutationScope: payload.mutation, excluded, warnings, exploration: !domain, expiresAt: new Date(Date.now() + 15 * 60_000).toISOString(), scopeHash: stableHash(payload), codeRevision };
}

/** Rejects stale, expired, or tampered scope capabilities. */
export function validateScope(scope: ScopeResolution, snapshot: ProjectSnapshot, currentCodeRevision = scope.codeRevision): void {
  if (scope.baseSnapshotId !== snapshot.id) throw new Error("BASE_SNAPSHOT_CONFLICT");
  if (Date.parse(scope.expiresAt) <= Date.now()) throw new Error("SCOPE_EXPIRED");
  if (scope.codeRevision !== currentCodeRevision) throw new Error("SCOPE_REVISION_STALE");
  const payload = { baseSnapshotId: scope.baseSnapshotId, codeRevision: scope.codeRevision, requested: scope.requestedScope, resolved: scope.resolvedScope, evidence: scope.evidenceScope, mutation: scope.mutationScope };
  if (stableHash(payload) !== scope.scopeHash) throw new Error("SCOPE_HASH_MISMATCH");
  if (scope.mutationScope.some(id => !scope.resolvedScope.includes(id))) throw new Error("MUTATION_SCOPE_VIOLATION");
}
