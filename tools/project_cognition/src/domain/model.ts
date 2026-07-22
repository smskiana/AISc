import { createHash, randomUUID } from "node:crypto";

export type MembershipType = "primary" | "secondary" | "reference";
export type ReviewStatus = "proposed" | "confirmed" | "locked" | "stale" | "conflicted";

export interface CodeSymbol {
  id: string;
  projectId: string;
  language: string;
  kind: string;
  filePath: string;
  qualifiedName: string;
  analyzerIdentity: string;
  contentFingerprint?: string;
  summary?: string;
  status?: ReviewStatus;
  source?: "analyzer" | "ai" | "manual";
  locked?: boolean;
  location?: { startLine: number; endLine: number };
}

export interface FunctionalDomain {
  id: string;
  projectId: string;
  name: string;
  summary: string;
  parentId?: string;
  status: ReviewStatus;
  source: "ai" | "manual";
  locked: boolean;
  lastReviewedRevision?: string;
}

export interface Membership {
  id: string;
  domainId: string;
  symbolId: string;
  type: MembershipType;
  status: ReviewStatus;
  source: "ai" | "manual";
  locked: boolean;
}

export interface FactRelation {
  id: string;
  sourceSymbolId: string;
  targetSymbolId: string;
  type: string;
  evidenceIds: string[];
  external: boolean;
}

export interface SemanticRelation {
  id: string;
  sourceSymbolId: string;
  targetSymbolId: string;
  summary: string;
  evidenceIds: string[];
  status: ReviewStatus;
  source: "fixture" | "ai" | "manual";
  scopeKind?: "within_domain" | "cross_domain";
  importance?: number;
  lastVerifiedRevision?: string;
}

export interface ProjectSnapshot {
  id: string;
  projectId: string;
  codeRevision: string;
  analyzerRevision: string;
  schemaVersion: 1;
  createdAt: string;
  parentSnapshotId?: string;
  domains: FunctionalDomain[];
  symbols: CodeSymbol[];
  memberships: Membership[];
  facts: FactRelation[];
  semantics: SemanticRelation[];
}

/** Creates the empty, versioned root snapshot for a project. */
export function emptySnapshot(projectId: string, codeRevision = "unknown"): ProjectSnapshot {
  return { id: randomUUID(), projectId, codeRevision, analyzerRevision: "codebase-memory-mcp", schemaVersion: 1, createdAt: new Date().toISOString(), domains: [], symbols: [], memberships: [], facts: [], semantics: [] };
}

/** Produces a stable hash for scope and optimistic-concurrency checks. */
export function stableHash(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}
