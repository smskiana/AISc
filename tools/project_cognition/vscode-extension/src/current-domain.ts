import { Membership, Overview, SymbolRecord } from "./model.js";

export interface CurrentDomainResolution { domainId: string; focusId: string; overview: Overview; }
export interface DocumentSymbolLike { name: string; kind: number; children?: DocumentSymbolLike[]; }

/** Finds the first class in flat SymbolInformation or nested DocumentSymbol results. */
export function firstClassName(symbols: DocumentSymbolLike[], classKind: number): string | undefined {
  for (const symbol of symbols) {
    if (symbol.kind === classKind) return symbol.name;
    const nested = symbol.children ? firstClassName(symbol.children, classKind) : undefined;
    if (nested) return nested;
  }
  return undefined;
}

/** Selects the earliest analyzer-located class when an IDE language provider is unavailable. */
export function firstClassifier(symbols: SymbolRecord[]): SymbolRecord | undefined {
  return [...symbols].sort((left, right) => (left.location?.startLine ?? Number.MAX_SAFE_INTEGER) - (right.location?.startLine ?? Number.MAX_SAFE_INTEGER) || left.qualifiedName.localeCompare(right.qualifiedName))[0];
}

/** Resolves a current-file class to its closest known domain without persisting inferred membership. */
export function resolveCurrentDomain(overview: Overview, symbol: SymbolRecord, filePath: string): CurrentDomainResolution | undefined {
  const normalizedPath = normalizePath(filePath);
  const symbolsById = new Map(overview.symbols.map(item => [item.id, item]));
  const ownMemberships = overview.memberships.filter(item => item.symbolId === symbol.id);
  const fileMemberships = overview.memberships.filter(item => normalizePath(symbolsById.get(item.symbolId)?.filePath ?? "") === normalizedPath);
  const membership = chooseMembership([...ownMemberships, ...fileMemberships]);
  const fallbackDomain = overview.domains.find(item => item.id === "virtual:unclassified");
  const domainId = membership?.domainId ?? fallbackDomain?.id;
  if (!domainId) return undefined;
  const symbols = overview.symbols.some(item => item.id === symbol.id) ? overview.symbols : [...overview.symbols, symbol];
  const memberships = overview.memberships.some(item => item.symbolId === symbol.id && item.domainId === domainId)
    ? overview.memberships
    : [...overview.memberships, { domainId, symbolId: symbol.id, type: "reference", status: "analyzer" }];
  return { domainId, focusId: symbol.id, overview: { ...overview, symbols, memberships } };
}

/** Prefers primary, then secondary, then reference memberships while preserving source order. */
function chooseMembership(memberships: Membership[]): Membership | undefined {
  const rank = new Map([["primary", 0], ["secondary", 1], ["reference", 2]]);
  return memberships.map((item, index) => ({ item, index })).sort((left, right) => (rank.get(left.item.type) ?? 3) - (rank.get(right.item.type) ?? 3) || left.index - right.index)[0]?.item;
}

function normalizePath(value: string): string { return value.replaceAll("\\", "/").toLowerCase(); }
