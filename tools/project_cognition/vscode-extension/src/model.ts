export interface Domain { id: string; name: string; summary: string; parentId?: string; status: string; }
export interface SymbolRecord { id: string; qualifiedName: string; filePath: string; kind?: string; summary?: string; status?: string; location?: { startLine: number; endLine: number }; }
export interface Membership { domainId: string; symbolId: string; type: string; status: string; }
export interface Overview { snapshotId: string; codeRevision: string; domains: Domain[]; memberships: Membership[]; symbols: SymbolRecord[]; }
export interface Relation { id: string; sourceSymbolId: string; targetSymbolId: string; summary: string; status: string; source: string; evidenceIds: string[]; importance?: number; }
export interface RelationEvidence { evidence: Array<{ id: string; type: string; sourceSymbolId: string; targetSymbolId: string; sourceQualifiedName?: string; targetQualifiedName?: string }>; missingEvidenceIds: string[]; }
export interface ClassifierContext { symbols: SymbolRecord[]; relations: Array<Relation & { evidence: RelationEvidence["evidence"] }>; }
export interface ScopeSymbol { id: string; qualifiedName: string; filePath: string; kind: string; }
export interface ScopePreview {
  id: string;
  scopeId: string;
  changeIds: string[];
  targetDomain: { id?: string; name: string; exploration: boolean };
  includedSymbols: ScopeSymbol[];
  readOnlyEvidence: ScopeSymbol[];
  excludedSymbols: ScopeSymbol[];
  excludedDomains: Array<{ id: string; name: string }>;
  estimatedCost: { files: number; symbols: number; relationsBudget: number };
  warnings: string[];
}

/** Returns the compact class name used by tree and UML nodes. */
export function shortName(qualifiedName: string): string { return qualifiedName.split(/[.:]/).filter(Boolean).at(-1) ?? qualifiedName; }
