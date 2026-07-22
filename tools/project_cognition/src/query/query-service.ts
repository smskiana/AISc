import { FactRelation, ProjectSnapshot, SemanticRelation } from "../domain/model.js";

export interface RelationEvidence {
  relation: SemanticRelation;
  evidence: FactRelation[];
  missingEvidenceIds: string[];
}

/** Returns stored primary relations in stable display order. */
export function getPrimaryRelations(snapshot: ProjectSnapshot, nodeId: string): SemanticRelation[] {
  const memberIds = new Set(snapshot.memberships.filter(item => item.domainId === nodeId).map(item => item.symbolId));
  memberIds.add(nodeId);
  return snapshot.semantics
    .filter(item => memberIds.has(item.sourceSymbolId) || memberIds.has(item.targetSymbolId))
    .sort((left, right) => (right.importance ?? 0) - (left.importance ?? 0) || left.id.localeCompare(right.id));
}

/** Expands a semantic relation into bounded, current fact evidence. */
export function expandRelationEvidence(snapshot: ProjectSnapshot, relationId: string, limit: number): RelationEvidence | undefined {
  const relation = snapshot.semantics.find(item => item.id === relationId);
  if (!relation) return undefined;
  const facts = new Map(snapshot.facts.map(item => [item.id, item]));
  const evidence = relation.evidenceIds.map(id => facts.get(id)).filter((item): item is FactRelation => Boolean(item)).slice(0, limit);
  return { relation, evidence, missingEvidenceIds: relation.evidenceIds.filter(id => !facts.has(id)) };
}

/** Reports whether stored cognition matches a caller-supplied code revision. */
export function checkScopeFreshness(snapshot: ProjectSnapshot, currentCodeRevision?: string, nodeId?: string): Record<string, unknown> {
  const relevant = nodeId ? snapshot.symbols.some(item => item.id === nodeId) || snapshot.domains.some(item => item.id === nodeId) : true;
  const comparable = Boolean(currentCodeRevision && currentCodeRevision !== "unknown" && snapshot.codeRevision !== "unknown");
  return { snapshotId: snapshot.id, storedCodeRevision: snapshot.codeRevision, currentCodeRevision: currentCodeRevision ?? "unknown", status: !relevant ? "not_found" : !comparable ? "unknown" : currentCodeRevision === snapshot.codeRevision ? "fresh" : "stale" };
}
