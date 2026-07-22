import { CodeSymbol, FunctionalDomain, ProjectSnapshot } from "../domain/model.js";
import { ScopeBudget, ScopeResolution } from "./scope-engine.js";

export interface ScopeSymbolView { id: string; qualifiedName: string; filePath: string; kind: string; }
export interface ScopeView {
  targetDomain: { id?: string; name: string; exploration: boolean };
  includedSymbols: ScopeSymbolView[];
  readOnlyEvidence: ScopeSymbolView[];
  excludedSymbols: ScopeSymbolView[];
  excludedDomains: Array<Pick<FunctionalDomain, "id" | "name">>;
  estimatedCost: { files: number; symbols: number; relationsBudget: number };
}

/** Builds the auditable IDE-facing view of one already signed scope. */
export function buildScopeView(snapshot: ProjectSnapshot, scope: ScopeResolution, symbols: CodeSymbol[], budget: ScopeBudget, requestedDomainId?: string): ScopeView {
  const byId = new Map(symbols.map(symbol => [symbol.id, symbol]));
  const mapSymbols = (ids: string[]) => ids.map(id => byId.get(id)).filter((item): item is CodeSymbol => Boolean(item)).map(toView);
  const readOnlyIds = scope.evidenceScope.filter(id => !scope.mutationScope.includes(id));
  const externalDomainIds = new Set(snapshot.memberships.filter(item => readOnlyIds.includes(item.symbolId)).map(item => item.domainId));
  const target = snapshot.domains.find(item => item.id === requestedDomainId);
  return {
    targetDomain: target ? { id: target.id, name: target.name, exploration: false } : { name: "Exploration", exploration: true },
    includedSymbols: mapSymbols(scope.mutationScope),
    readOnlyEvidence: mapSymbols(readOnlyIds),
    excludedSymbols: mapSymbols(scope.excluded),
    excludedDomains: snapshot.domains.filter(item => externalDomainIds.has(item.id)).map(item => ({ id: item.id, name: item.name })),
    estimatedCost: { files: new Set(scope.resolvedScope.map(id => byId.get(id)?.filePath).filter(Boolean)).size, symbols: scope.resolvedScope.length, relationsBudget: budget.maxRelations }
  };
}

/** Reduces a code symbol to the stable fields shown in previews. */
function toView(symbol: CodeSymbol): ScopeSymbolView { return { id: symbol.id, qualifiedName: symbol.qualifiedName, filePath: symbol.filePath, kind: symbol.kind }; }
