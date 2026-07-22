import { SemanticRelation } from "../../domain/model.js";

export interface SemanticSuggestion { summary: string; sourceSymbolId: string; targetSymbolId: string; evidenceIds: string[]; }

/** Validates all model evidence against the signed evidence whitelist. */
export function validateSemanticSuggestions(suggestions: SemanticSuggestion[], evidenceScope: Set<string>): SemanticRelation[] {
  for (const suggestion of suggestions) if (suggestion.evidenceIds.some(id => !evidenceScope.has(id))) throw new Error("UNKNOWN_EVIDENCE_ID");
  return suggestions.map((item, index) => ({ id: `semantic-${index}-${item.sourceSymbolId}`, ...item, status: "proposed", source: "fixture" }));
}
