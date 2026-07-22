import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { JsonSnapshotStore } from "../src/adapters/snapshot-store/json-store.js";
import { resolveScope } from "../src/scope/scope-engine.js";
import { applyUpdate, previewUpdate } from "../src/update/update-service.js";

test("preview and apply write only accepted in-scope symbols", async () => { const store = new JsonSnapshotStore(await mkdtemp(path.join(os.tmpdir(), "cognition-"))); const snapshot = await store.load("AISc"); const symbol = { id: "a", projectId: "AISc", language: "C#", kind: "Class", filePath: "a.cs", qualifiedName: "A", analyzerIdentity: "A" }; const scope = resolveScope({ projectId: "AISc", query: "A", seedSymbols: [symbol] }, snapshot, { maxFiles: 2, maxSymbols: 2, maxRelations: 2 }); const preview = previewUpdate(scope, snapshot, [symbol]); const next = await applyUpdate(store, snapshot, scope, preview, preview.changeIds); assert.equal(next.symbols[0].id, "a"); await assert.rejects(() => applyUpdate(store, snapshot, scope, preview, preview.changeIds), /BASE_SNAPSHOT_CONFLICT/); });
