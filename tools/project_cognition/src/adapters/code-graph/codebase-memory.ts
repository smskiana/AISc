import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { CodeSymbol, FactRelation, stableHash } from "../../domain/model.js";

export interface GraphSearchResult { symbols: CodeSymbol[]; raw: unknown; }

export class CodebaseMemoryAdapter {
  private client?: Client;
  public constructor(private readonly command: string, private readonly args: string[] = []) {}

  /** Starts the supported MCP client seam to codebase-memory. */
  public async connect(): Promise<void> {
    if (this.client) return;
    this.client = new Client({ name: "project-cognition", version: "0.1.0" });
    await this.client.connect(new StdioClientTransport({ command: this.command, args: this.args }));
  }

  /** Resolves code symbols through codebase-memory search_graph. */
  public async resolveSymbols(projectId: string, query: string, limit = 50): Promise<GraphSearchResult> {
    await this.connect();
    const result = await this.client!.callTool({ name: "search_graph", arguments: { project: projectId, query, limit } });
    const raw = (result as { structuredContent?: Record<string, unknown> }).structuredContent ?? this.parseText(result);
    const rows = Array.isArray((raw as Record<string, unknown>)?.results) ? (raw as { results: Record<string, unknown>[] }).results : [];
    const symbols = rows.map(row => this.toSymbol(projectId, row)).filter((item): item is CodeSymbol => Boolean(item));
    return { symbols, raw };
  }

  /** Reads bounded one-hop relations through trace_path. */
  public async getDirectRelations(projectId: string, qualifiedName: string): Promise<{ facts: FactRelation[]; raw: unknown }> {
    await this.connect();
    const result = await this.client!.callTool({ name: "trace_path", arguments: { project: projectId, function_name: qualifiedName, direction: "both", depth: 1, mode: "calls" } });
    return { facts: [], raw: (result as { structuredContent?: unknown }).structuredContent ?? this.parseText(result) };
  }

  /** Closes the child MCP transport. */
  public async close(): Promise<void> { await this.client?.close(); this.client = undefined; }

  private parseText(result: unknown): unknown {
    const blocks = (result as { content?: Array<{ type: string; text?: string }> }).content ?? [];
    const text = blocks.find(block => block.type === "text")?.text;
    try { return text ? JSON.parse(text) : {}; } catch { return { text }; }
  }

  private toSymbol(projectId: string, row: Record<string, unknown>): CodeSymbol | undefined {
    const qualifiedName = String(row.qualified_name ?? row.qualifiedName ?? "");
    if (!qualifiedName) return undefined;
    const filePath = String(row.file_path ?? row.file ?? "");
    const identity = `${projectId}:${qualifiedName}:${filePath}`;
    return { id: stableHash(identity), projectId, language: String(row.language ?? "unknown"), kind: String(row.label ?? row.type ?? "Symbol"), filePath, qualifiedName, analyzerIdentity: identity };
  }
}
