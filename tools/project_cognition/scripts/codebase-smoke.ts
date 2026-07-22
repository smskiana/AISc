import { CodebaseMemoryAdapter } from "../src/adapters/code-graph/codebase-memory.js";

/** Verifies the supported MCP seam against a known AISc symbol. */
async function main(): Promise<void> {
  const adapter = new CodebaseMemoryAdapter(process.env.CODEBASE_MEMORY_COMMAND ?? "C:/Users/HP/.local/bin/codebase-memory-mcp.exe");
  try { const result = await adapter.resolveSymbols("AISc", "GameManager", 5); if (!result.symbols.length) throw new Error("No known AISc symbol returned"); console.log(JSON.stringify({ ok: true, symbol: result.symbols[0] }, null, 2)); }
  finally { await adapter.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
