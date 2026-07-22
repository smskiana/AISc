import assert from "node:assert/strict";
import path from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

interface ToolEnvelope<T> { ok: boolean; data: T; }
interface Overview { domains: Array<{ id: string }>; memberships: Array<{ domainId: string; symbolId: string }>; symbols: Array<{ id: string; filePath: string; kind: string }>; }
interface ClassifierContext {
  symbols: Array<{ id: string; filePath: string; kind: string; location?: { startLine: number } }>;
  relations: Array<{ evidence: Array<{ sourceSymbolId: string }> }>;
}

/** Verifies that method-only domain members can resolve classifier nodes through public MCP. */
async function main(): Promise<void> {
  const client = new Client({ name: "uml-smoke", version: "0.1.0" });
  const env = { ...process.env, PROJECT_COGNITION_STATE_DIR: process.env.PROJECT_COGNITION_STATE_DIR ?? path.resolve("../..", ".project-cognition"), CODEBASE_MEMORY_COMMAND: process.env.CODEBASE_MEMORY_COMMAND ?? "C:/Users/HP/.local/bin/codebase-memory-mcp.exe" } as Record<string, string>;
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [path.resolve("dist/src/server.js")], env }));
  try {
    const overview = await call<Overview>(client, "get_domain_overview", { projectId: "AISc" });
    const unclassified = overview.domains.find(item => item.id === "virtual:unclassified");
    assert.ok(unclassified, "Current snapshot must expose the unclassified domain.");
    const symbolById = new Map(overview.symbols.map(item => [item.id, item]));
    const filePaths = [...new Set(overview.memberships.filter(item => item.domainId === unclassified.id).map(item => symbolById.get(item.symbolId)?.filePath).filter((item): item is string => Boolean(item)))].slice(0, 20);
    const classifierGroups = await Promise.all(filePaths.map(filePath => call<{ symbols: Array<{ kind: string; filePath: string }> }>(client, "find_symbol", { projectId: "AISc", query: "", filePath, kind: "Class", limit: 10 })));
    const classifiers = classifierGroups.flatMap(item => item.symbols).filter(item => item.kind === "Class");
    assert.ok(classifiers.length > 0, "At least one unclassified member file must resolve a class for UML projection.");
    const webSocket = await call<{ symbols: Array<{ qualifiedName: string; location?: { startLine: number } }> }>(client, "find_symbol", { projectId: "AISc", query: "WebSocketClient", filePath: "Assets/Scripts/Core/WebSocketClient.cs", symbolName: "WebSocketClient", kind: "Class", limit: 10 });
    assert.equal(webSocket.symbols[0]?.location?.startLine, 17, "Class location must be enriched from public snippet metadata.");
    const context = await call<ClassifierContext>(client, "get_classifier_context", { projectId: "AISc", qualifiedName: webSocket.symbols[0].qualifiedName, limit: 40 });
    assert.ok(context.relations.length > 0, "WebSocketClient must expose aggregated class relations.");
    const contextSymbols = new Map(context.symbols.map(item => [item.id, item]));
    const sourceMethod = contextSymbols.get(context.relations.flatMap(item => item.evidence)[0]?.sourceSymbolId);
    assert.equal(sourceMethod?.kind, "Method", "Relation evidence must reference a method instead of its containing class.");
    assert.ok(sourceMethod?.filePath && (sourceMethod.location?.startLine ?? 0) > 0, "Relation evidence methods must carry a navigable source location.");
    console.log(JSON.stringify({ ok: true, memberFiles: filePaths.length, classifiers: classifiers.length, classStartLine: webSocket.symbols[0].location?.startLine, relations: context.relations.length, evidenceMethodStartLine: sourceMethod.location?.startLine }));
  } finally { await client.close(); }
}

/** Calls one successful MCP tool and extracts its structured payload. */
async function call<T>(client: Client, name: string, args: Record<string, unknown>): Promise<T> {
  const result = await client.callTool({ name, arguments: args }) as { structuredContent?: ToolEnvelope<T> };
  assert.equal(result.structuredContent?.ok, true);
  return result.structuredContent!.data;
}

main().catch(error => { console.error(error); process.exitCode = 1; });
