import { RelationEvidence, shortName, SymbolRecord } from "../model.js";

export interface EvidencePick {
  label: string;
  description?: string;
  symbol?: SymbolRecord;
}

/** Maps a fact label and its navigation target from the same method-level evidence record. */
export function buildEvidencePicks(expanded: RelationEvidence, symbols: SymbolRecord[]): EvidencePick[] {
  const symbolsById = new Map(symbols.map(item => [item.id, item]));
  return expanded.evidence.map(fact => {
    const source = symbolsById.get(fact.sourceSymbolId);
    const target = symbolsById.get(fact.targetSymbolId);
    const sourceLabel = fact.sourceQualifiedName ? shortName(fact.sourceQualifiedName) : source ? shortName(source.qualifiedName) : fact.sourceSymbolId;
    const targetLabel = fact.targetQualifiedName ? shortName(fact.targetQualifiedName) : target ? shortName(target.qualifiedName) : fact.targetSymbolId;
    return { label: `${fact.type}: ${sourceLabel} -> ${targetLabel}`, description: source?.filePath, symbol: source ?? target };
  });
}
