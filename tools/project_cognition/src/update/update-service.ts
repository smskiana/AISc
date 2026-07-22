import { randomUUID } from "node:crypto";
import { CodeSymbol, ProjectSnapshot } from "../domain/model.js";
import { ScopeResolution, validateScope } from "../scope/scope-engine.js";
import { JsonSnapshotStore } from "../adapters/snapshot-store/json-store.js";

export interface UpdatePreview { id: string; baseSnapshotId: string; scopeId: string; symbols: CodeSymbol[]; changeIds: string[]; }

/** Creates a bounded preview without writing the formal snapshot. */
export function previewUpdate(scope: ScopeResolution, snapshot: ProjectSnapshot, symbols: CodeSymbol[], currentCodeRevision = scope.codeRevision): UpdatePreview {
  validateScope(scope, snapshot, currentCodeRevision);
  const allowed = symbols.filter(symbol => scope.mutationScope.includes(symbol.id));
  return { id: randomUUID(), baseSnapshotId: snapshot.id, scopeId: scope.scopeId, symbols: allowed, changeIds: allowed.map(symbol => `upsert:${symbol.id}`) };
}

/** Applies only explicitly accepted preview changes with optimistic concurrency. */
export async function applyUpdate(store: JsonSnapshotStore, snapshot: ProjectSnapshot, scope: ScopeResolution, preview: UpdatePreview, acceptedChangeIds: string[], currentCodeRevision = scope.codeRevision): Promise<ProjectSnapshot> {
  validateScope(scope, snapshot, currentCodeRevision);
  if (preview.baseSnapshotId !== snapshot.id || preview.scopeId !== scope.scopeId) throw new Error("PREVIEW_CONFLICT");
  const accepted = new Set(acceptedChangeIds);
  if ([...accepted].some(id => !preview.changeIds.includes(id))) throw new Error("UNKNOWN_CHANGE_ID");
  const updates = preview.symbols.filter(symbol => accepted.has(`upsert:${symbol.id}`));
  const updatedIds = new Set(updates.map(symbol => symbol.id));
  const next: ProjectSnapshot = { ...snapshot, id: randomUUID(), parentSnapshotId: snapshot.id, codeRevision: currentCodeRevision, createdAt: new Date().toISOString(), symbols: [...snapshot.symbols.filter(symbol => !updatedIds.has(symbol.id)), ...updates] };
  await store.commit(next, snapshot.id);
  return next;
}
