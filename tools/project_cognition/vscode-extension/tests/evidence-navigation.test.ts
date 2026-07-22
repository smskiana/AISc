import assert from "node:assert/strict";
import test from "node:test";
import { buildEvidencePicks } from "../src/uml/evidence-navigation.js";

test("method evidence navigates to the source method represented by its label", () => {
  const source = { id: "method-start", qualifiedName: "AISc.Assets.Scripts.Core.GameManager.GameManager.Start", filePath: "Assets/Scripts/Core/GameManager.cs", kind: "Method", location: { startLine: 42, endLine: 55 } };
  const target = { id: "method-load", qualifiedName: "AISc.Assets.Scripts.Core.AssetLoader.Load", filePath: "Assets/Scripts/Core/AssetLoader.cs", kind: "Method", location: { startLine: 18, endLine: 30 } };
  const picks = buildEvidencePicks({ evidence: [{ id: "call", type: "CALLS", sourceSymbolId: source.id, targetSymbolId: target.id, sourceQualifiedName: source.qualifiedName, targetQualifiedName: target.qualifiedName }], missingEvidenceIds: [] }, [source, target]);

  assert.equal(picks[0]?.label, "CALLS: Start -> Load");
  assert.deepEqual(picks[0]?.symbol, source);
  assert.deepEqual(picks[0]?.symbol?.location, { startLine: 42, endLine: 55 });
});
