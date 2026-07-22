#!/usr/bin/env node
import path from "node:path";
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { CodebaseMemoryAdapter } from "./adapters/code-graph/codebase-memory.js";
import { JsonSnapshotStore } from "./adapters/snapshot-store/json-store.js";
import { GitRevisionProvider } from "./adapters/revision/git-revision.js";
import { toCognitionError } from "./domain/errors.js";
import { MembershipType, ProjectSnapshot } from "./domain/model.js";
import { confirmDomainStructure, rejectProposal, setSymbolMembership, updateManualSummary } from "./governance/governance-service.js";
import { checkScopeFreshness, expandRelationEvidence, getPrimaryRelations } from "./query/query-service.js";
import { resolveScope, ScopeResolution } from "./scope/scope-engine.js";
import { applyUpdate, previewUpdate, UpdatePreview } from "./update/update-service.js";

const stateRoot = process.env.PROJECT_COGNITION_STATE_DIR ?? path.resolve(".project-cognition");
const graphCommand = process.env.CODEBASE_MEMORY_COMMAND ?? "codebase-memory-mcp";
const repositoryRoot = process.env.PROJECT_COGNITION_REPO_ROOT ?? process.cwd();
const store = new JsonSnapshotStore(stateRoot);
const graph = new CodebaseMemoryAdapter(graphCommand);
const revisions = new GitRevisionProvider(repositoryRoot);
const scopes = new Map<string, ScopeResolution>();
const previews = new Map<string, UpdatePreview>();
const server = new McpServer({ name: "aisc-project-cognition", version: "0.1.0" });

/** Formats successful MCP responses consistently for Codex and IDE clients. */
function ok(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify({ ok: true, data }, null, 2) }], structuredContent: { ok: true, data } };
}

/** Converts every tool failure to the stable public error object. */
async function respond(operation: () => unknown | Promise<unknown>) {
  try { return ok(await operation()); }
  catch (error) {
    const body = toCognitionError(error);
    return { isError: true, content: [{ type: "text" as const, text: JSON.stringify({ ok: false, error: body }, null, 2) }], structuredContent: { ok: false, error: body } };
  }
}

/** Atomically commits a manual governance mutation against the current head. */
async function commitGovernance(projectId: string, change: (snapshot: ProjectSnapshot) => ProjectSnapshot): Promise<ProjectSnapshot> {
  const current = await store.load(projectId);
  const next = change(current);
  await store.commit(next, current.id);
  return next;
}

server.registerTool("find_symbol", { description: "Find language-independent symbols through the configured code graph.", inputSchema: { projectId: z.string(), query: z.string(), limit: z.number().int().min(1).max(200).default(50) } }, args => respond(() => graph.resolveSymbols(args.projectId, args.query, args.limit)));
server.registerTool("get_domain_overview", { description: "Read the current project cognition snapshot and domain tree.", inputSchema: { projectId: z.string(), domainId: z.string().optional(), depth: z.number().int().min(0).max(10).default(3) } }, args => respond(async () => { const snapshot = await store.load(args.projectId); const domainIds = new Set(args.domainId ? snapshot.domains.filter(item => item.id === args.domainId || item.parentId === args.domainId).map(item => item.id) : snapshot.domains.map(item => item.id)); return { snapshotId: snapshot.id, codeRevision: snapshot.codeRevision, domains: snapshot.domains.filter(item => domainIds.has(item.id)), memberships: snapshot.memberships.filter(item => domainIds.has(item.domainId)), symbols: snapshot.symbols.filter(item => snapshot.memberships.some(membership => domainIds.has(membership.domainId) && membership.symbolId === item.id)) }; }));
server.registerTool("get_symbol_context", { description: "Read one stored symbol and its bounded relations.", inputSchema: { projectId: z.string(), symbolId: z.string() } }, args => respond(async () => { const snapshot = await store.load(args.projectId); return { symbol: snapshot.symbols.find(item => item.id === args.symbolId), memberships: snapshot.memberships.filter(item => item.symbolId === args.symbolId), facts: snapshot.facts.filter(item => item.sourceSymbolId === args.symbolId || item.targetSymbolId === args.symbolId), semantics: getPrimaryRelations(snapshot, args.symbolId) }; }));
server.registerTool("get_primary_relations", { description: "Read bounded semantic relations for a domain or symbol.", inputSchema: { projectId: z.string(), nodeId: z.string(), limit: z.number().int().min(1).max(200).default(30) } }, args => respond(async () => getPrimaryRelations(await store.load(args.projectId), args.nodeId).slice(0, args.limit)));
server.registerTool("expand_relation_evidence", { description: "Expand one semantic relation into method-level fact evidence.", inputSchema: { projectId: z.string(), relationId: z.string(), limit: z.number().int().min(1).max(200).default(30) } }, args => respond(async () => expandRelationEvidence(await store.load(args.projectId), args.relationId, args.limit)));
server.registerTool("check_scope_freshness", { description: "Compare stored cognition with the current code revision.", inputSchema: { projectId: z.string(), nodeId: z.string().optional(), currentCodeRevision: z.string().optional() } }, args => respond(async () => checkScopeFreshness(await store.load(args.projectId), args.currentCodeRevision ?? await revisions.getRevision(), args.nodeId)));

server.registerTool("resolve_update_scope", { description: "Resolve and sign a budget-limited local cognition update scope.", inputSchema: { projectId: z.string(), query: z.string(), domainId: z.string().optional(), maxFiles: z.number().int().min(1).max(100).default(20), maxSymbols: z.number().int().min(1).max(500).default(30), maxRelations: z.number().int().min(1).max(5000).default(100) } }, args => respond(async () => { const snapshot = await store.load(args.projectId); const found = await graph.resolveSymbols(args.projectId, args.query, args.maxSymbols); const scope = resolveScope({ projectId: args.projectId, query: args.query, seedSymbols: found.symbols, requestedDomainId: args.domainId, codeRevision: await revisions.getRevision() }, snapshot, { maxFiles: args.maxFiles, maxSymbols: args.maxSymbols, maxRelations: args.maxRelations }); scopes.set(scope.scopeId, scope); return scope; }));
server.registerTool("preview_scoped_update", { description: "Preview signed changes without writing the snapshot.", inputSchema: { projectId: z.string(), scopeId: z.string(), query: z.string() } }, args => respond(async () => { const scope = scopes.get(args.scopeId); if (!scope) throw new Error("INVALID_SCOPE_ID"); const snapshot = await store.load(args.projectId); const found = await graph.resolveSymbols(args.projectId, args.query, 200); const preview = previewUpdate(scope, snapshot, found.symbols, await revisions.getRevision()); previews.set(preview.id, preview); return { ...preview, requestedScope: scope.requestedScope, resolvedScope: scope.resolvedScope, evidenceScope: scope.evidenceScope, mutationScope: scope.mutationScope, excluded: scope.excluded, warnings: scope.warnings }; }));
server.registerTool("apply_scoped_update", { description: "Atomically apply accepted changes inside a signed scope.", inputSchema: { projectId: z.string(), scopeId: z.string(), previewId: z.string(), acceptedChangeIds: z.array(z.string()) } }, args => respond(async () => { const scope = scopes.get(args.scopeId); const preview = previews.get(args.previewId); if (!scope) throw new Error("INVALID_SCOPE_ID"); if (!preview) throw new Error("INVALID_PREVIEW_ID"); return applyUpdate(store, await store.load(args.projectId), scope, preview, args.acceptedChangeIds, await revisions.getRevision()); }));
server.registerTool("request_full_update", { description: "Issue a separately confirmed full-project scope.", inputSchema: { projectId: z.string(), explicitConfirmation: z.string(), query: z.string().default("class function method"), maxFiles: z.number().int().min(1).max(2000), maxSymbols: z.number().int().min(1).max(20000) } }, args => respond(async () => { const snapshot = await store.load(args.projectId); const found = await graph.resolveSymbols(args.projectId, args.query, args.maxSymbols); const scope = resolveScope({ projectId: args.projectId, query: args.query, seedSymbols: found.symbols, fullUpdate: true, explicitConfirmation: args.explicitConfirmation, codeRevision: await revisions.getRevision() }, snapshot, { maxFiles: args.maxFiles, maxSymbols: args.maxSymbols, maxRelations: args.maxSymbols * 5 }); scopes.set(scope.scopeId, scope); return scope; }));

server.registerTool("confirm_domain_structure", { description: "Manually confirm proposed functional domains.", inputSchema: { projectId: z.string(), domainIds: z.array(z.string()).min(1) } }, args => respond(() => commitGovernance(args.projectId, snapshot => confirmDomainStructure(snapshot, args.domainIds))));
server.registerTool("set_symbol_membership", { description: "Set a manual primary, secondary, or reference membership.", inputSchema: { projectId: z.string(), symbolId: z.string(), domainId: z.string(), membershipType: z.enum(["primary", "secondary", "reference"]), locked: z.boolean().default(true) } }, args => respond(() => commitGovernance(args.projectId, snapshot => setSymbolMembership(snapshot, args.symbolId, args.domainId, args.membershipType as MembershipType, args.locked))));
server.registerTool("update_manual_summary", { description: "Set a protected manual summary for one stored symbol.", inputSchema: { projectId: z.string(), symbolId: z.string(), summary: z.string().min(1).max(4000) } }, args => respond(() => commitGovernance(args.projectId, snapshot => updateManualSummary(snapshot, args.symbolId, args.summary))));
server.registerTool("reject_proposal", { description: "Reject one proposed domain, membership, or semantic relation.", inputSchema: { projectId: z.string(), proposalId: z.string() } }, args => respond(() => commitGovernance(args.projectId, snapshot => rejectProposal(snapshot, args.proposalId))));
server.registerTool("rollback_snapshot", { description: "Restore the previous local cognition snapshot.", inputSchema: { projectId: z.string(), explicitConfirmation: z.string() } }, args => respond(async () => { if (args.explicitConfirmation !== `ROLLBACK ${args.projectId}`) throw new Error("ROLLBACK_CONFIRMATION_REQUIRED"); return store.rollback(args.projectId); }));

/** Registers the five stable read-only cognition resource families. */
function registerResources(): void {
  server.registerResource("project-domains", new ResourceTemplate("project-cognition://projects/{projectId}/domains", { list: undefined }), { mimeType: "application/json" }, async (uri, vars) => { const snapshot = await store.load(String(vars.projectId)); return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(snapshot.domains) }] }; });
  server.registerResource("project-domain", new ResourceTemplate("project-cognition://projects/{projectId}/domains/{domainId}", { list: undefined }), { mimeType: "application/json" }, async (uri, vars) => { const snapshot = await store.load(String(vars.projectId)); const domainId = String(vars.domainId); return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify({ domain: snapshot.domains.find(item => item.id === domainId), memberships: snapshot.memberships.filter(item => item.domainId === domainId) }) }] }; });
  server.registerResource("project-symbol", new ResourceTemplate("project-cognition://projects/{projectId}/symbols/{symbolId}", { list: undefined }), { mimeType: "application/json" }, async (uri, vars) => { const snapshot = await store.load(String(vars.projectId)); const symbolId = String(vars.symbolId); return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify({ symbol: snapshot.symbols.find(item => item.id === symbolId), relations: getPrimaryRelations(snapshot, symbolId) }) }] }; });
  server.registerResource("project-relation", new ResourceTemplate("project-cognition://projects/{projectId}/relations/{relationId}", { list: undefined }), { mimeType: "application/json" }, async (uri, vars) => { const snapshot = await store.load(String(vars.projectId)); return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(expandRelationEvidence(snapshot, String(vars.relationId), 100)) }] }; });
  server.registerResource("project-current-snapshot", new ResourceTemplate("project-cognition://projects/{projectId}/snapshots/current", { list: undefined }), { mimeType: "application/json" }, async (uri, vars) => { const snapshot = await store.load(String(vars.projectId)); return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(snapshot) }] }; });
}

registerResources();

/** Runs the Project Cognition MCP server over stdio. */
async function main(): Promise<void> { await server.connect(new StdioServerTransport()); }
main().catch(error => { console.error(error); process.exitCode = 1; });
