import assert from "node:assert/strict";
import test from "node:test";
import { toCodeSymbol } from "../src/adapters/code-graph/codebase-memory.js";

test("code graph symbol preserves source location for IDE navigation", () => {
  const symbol = toCodeSymbol("AISc", { qualified_name: "AISc.GameManager.Awake", file_path: "Assets/Scripts/Core/GameManager.cs", label: "Method", start_line: 65, end_line: 130 });
  assert.deepEqual(symbol?.location, { startLine: 65, endLine: 130 });
});
