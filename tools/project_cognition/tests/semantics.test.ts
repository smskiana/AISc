import assert from "node:assert/strict";
import test from "node:test";
import { validateSemanticSuggestions } from "../src/adapters/ai-semantics/fixture-adapter.js";

test("semantic adapter rejects evidence outside the whitelist", () => { assert.throws(() => validateSemanticSuggestions([{ summary: "x", sourceSymbolId: "a", targetSymbolId: "b", evidenceIds: ["outside"] }], new Set(["inside"])), /UNKNOWN_EVIDENCE_ID/); });
