import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

interface ToolEnvelope<T> { ok: boolean; data: T; }
interface ScopeData { scopeId: string; includedSymbols: Array<{ qualifiedName: string; location?: { startLine: number } }>; }
interface PreviewData { includedSymbols: Array<{ qualifiedName: string }>; changeIds: string[]; }

/** Verifies exact IDE file/symbol context and resolve-to-preview stability through stdio. */
async function main(): Promise<void> {
  const stateDir = await mkdtemp(path.join(os.tmpdir(), "cognition-context-"));
  const client = new Client({ name: "context-smoke", version: "0.1.0" });
  const env = { ...process.env, PROJECT_COGNITION_STATE_DIR: stateDir, CODEBASE_MEMORY_COMMAND: process.env.CODEBASE_MEMORY_COMMAND ?? "C:/Users/HP/.local/bin/codebase-memory-mcp.exe" } as Record<string, string>;
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [path.resolve("dist/src/server.js")], env }));
  try {
    const cases = [
      { symbolName: "GameManager", filePath: "Assets/Scripts/Core/GameManager.cs" },
      { symbolName: "NpcSpawner", filePath: "Assets/Scripts/NPC/NpcSpawner.cs" }
    ];
    for (const item of cases) {
      const resolved = await call<ScopeData>(client, "resolve_update_scope", { projectId: "AISc", query: item.symbolName, symbolName: item.symbolName, filePath: item.filePath, maxFiles: 20, maxSymbols: 30, maxRelations: 100 });
      assert.equal(resolved.includedSymbols.length, 1, `${item.symbolName} must resolve to one exact symbol`);
      assert.match(resolved.includedSymbols[0].qualifiedName, new RegExp(`${item.symbolName}$`));
      const preview = await call<PreviewData>(client, "preview_scoped_update", { projectId: "AISc", scopeId: resolved.scopeId });
      assert.deepEqual(preview.includedSymbols.map(symbol => symbol.qualifiedName), resolved.includedSymbols.map(symbol => symbol.qualifiedName));
      assert.equal(preview.changeIds.length, 1);
    }
    console.log(JSON.stringify({ ok: true, cases: cases.map(item => item.symbolName) }));
  } finally { await client.close(); }
}

/** Calls one successful MCP tool and extracts its structured payload. */
async function call<T>(client: Client, name: string, args: Record<string, unknown>): Promise<T> {
  const result = await client.callTool({ name, arguments: args }) as { structuredContent?: ToolEnvelope<T> };
  assert.equal(result.structuredContent?.ok, true);
  return result.structuredContent!.data;
}

main().catch(error => { console.error(error); process.exitCode = 1; });
