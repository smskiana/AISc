import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

test("stdio server exposes the complete tool and resource contract", async () => {
  const stateDir = await mkdtemp(path.join(os.tmpdir(), "cognition-mcp-"));
  const client = new Client({ name: "contract-test", version: "0.1.0" });
  const transport = new StdioClientTransport({ command: process.execPath, args: [path.resolve("dist/src/server.js")], env: { ...process.env, PROJECT_COGNITION_STATE_DIR: stateDir } as Record<string, string> });
  await client.connect(transport);
  try {
    const tools = await client.listTools();
    const names = new Set(tools.tools.map(item => item.name));
    for (const name of ["get_primary_relations", "expand_relation_evidence", "get_classifier_context", "check_scope_freshness", "confirm_domain_structure", "set_symbol_membership", "update_manual_summary", "reject_proposal"]) assert.ok(names.has(name), name);
    const templates = await client.listResourceTemplates();
    assert.equal(templates.resourceTemplates.length, 5);
    const overview = await client.callTool({ name: "get_domain_overview", arguments: { projectId: "AISc" } }) as { structuredContent?: { ok?: boolean } };
    assert.equal(overview.structuredContent?.ok, true);
    const invalid = await client.callTool({ name: "preview_scoped_update", arguments: { projectId: "AISc", scopeId: "missing", query: "x" } }) as { structuredContent?: { error?: { code?: string } } };
    assert.equal(invalid.structuredContent?.error?.code, "INVALID_SCOPE_ID");
    const missingRelation = await client.callTool({ name: "expand_relation_evidence", arguments: { projectId: "AISc", relationId: "missing", limit: 10 } }) as { structuredContent?: { error?: { code?: string } } };
    assert.equal(missingRelation.structuredContent?.error?.code, "RELATION_NOT_FOUND");
  } finally { await client.close(); }
});
