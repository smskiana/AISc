import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { CodeSymbol, FactRelation, stableHash } from "../../domain/model.js";

export interface GraphSearchResult { symbols: CodeSymbol[]; raw: unknown; }
export interface ClassifierContextRelation {
  id: string; sourceSymbolId: string; targetSymbolId: string; summary: string; status: string; source: string; evidenceIds: string[]; importance: number;
  evidence: Array<{ id: string; type: string; sourceSymbolId: string; targetSymbolId: string; sourceQualifiedName: string; targetQualifiedName: string }>;
}
export interface ClassifierContext { symbols: CodeSymbol[]; relations: ClassifierContextRelation[]; }

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
  public async resolveSymbols(projectId: string, query: string, limit = 50, pathHint?: string, exactName?: string, label?: string): Promise<GraphSearchResult> {
    await this.connect();
    const arguments_ = exactName
      ? { project: projectId, name_pattern: `^${escapeRegex(exactName)}$`, file_pattern: pathHint, label, limit }
      : { project: projectId, ...(query ? { query } : {}), file_pattern: pathHint, label, limit };
    const result = await this.client!.callTool({ name: "search_graph", arguments: arguments_ });
    const raw = (result as { structuredContent?: Record<string, unknown> }).structuredContent ?? this.parseText(result);
    const rows = Array.isArray((raw as Record<string, unknown>)?.results) ? (raw as { results: Record<string, unknown>[] }).results : [];
    const symbols = rows.map(row => toCodeSymbol(projectId, row)).filter((item): item is CodeSymbol => Boolean(item));
    await Promise.all(symbols.filter(item => isClassifier(item.kind) && !item.location).slice(0, 20).map(async symbol => {
      const snippet = await this.readSnippet(projectId, symbol.qualifiedName);
      const startLine = Number(snippet.start_line ?? snippet.startLine);
      const endLine = Number(snippet.end_line ?? snippet.endLine);
      if (Number.isInteger(startLine) && startLine > 0) symbol.location = { startLine, endLine: Number.isInteger(endLine) && endLine >= startLine ? endLine : startLine };
    }));
    return { symbols, raw };
  }

  /** Aggregates method CALLS edges into a bounded class-to-class context. */
  public async getClassifierContext(projectId: string, qualifiedName: string, limit = 40): Promise<ClassifierContext> {
    await this.connect();
    const escaped = qualifiedName.replaceAll("'", "\\'");
    const query = `MATCH (focus:Class {qualified_name: '${escaped}'})-[:DEFINES_METHOD]->(fm:Method)-[:CALLS]->(tm:Method)<-[:DEFINES_METHOD]-(target:Class) RETURN focus.qualified_name, focus.file_path, focus.start_line, focus.end_line, target.qualified_name, target.file_path, target.start_line, target.end_line, fm.qualified_name, tm.qualified_name, fm.file_path, fm.start_line, fm.end_line, tm.file_path, tm.start_line, tm.end_line LIMIT ${Math.max(1, Math.min(limit * 8, 640))}`;
    const result = await this.client!.callTool({ name: "query_graph", arguments: { project: projectId, query, max_rows: Math.max(1, Math.min(limit * 8, 640)) } });
    const raw = (result as { structuredContent?: Record<string, unknown> }).structuredContent ?? this.parseText(result) as Record<string, unknown>;
    const rows = Array.isArray(raw.rows) ? raw.rows as unknown[][] : [];
    const symbols = new Map<string, CodeSymbol>();
    const grouped = new Map<string, ClassifierContextRelation>();
    for (const row of rows) {
      const source = classSymbol(projectId, row[0], row[1], row[2], row[3]);
      const target = classSymbol(projectId, row[4], row[5], row[6], row[7]);
      if (!source || !target || source.id === target.id) continue;
      symbols.set(source.id, source); symbols.set(target.id, target);
      const sourceMethod = methodSymbol(projectId, row[8], row[10] ?? row[1], row[11], row[12]);
      const targetMethod = methodSymbol(projectId, row[9], row[13] ?? row[5], row[14], row[15]);
      if (!sourceMethod || !targetMethod) continue;
      symbols.set(sourceMethod.id, sourceMethod); symbols.set(targetMethod.id, targetMethod);
      const relationId = stableHash(`classifier-relation:${source.id}:${target.id}:CALLS`);
      const evidenceId = stableHash(`classifier-evidence:${String(row[8])}:${String(row[9])}`);
      const relation = grouped.get(relationId) ?? { id: relationId, sourceSymbolId: source.id, targetSymbolId: target.id, summary: `calls ${shortQualifiedName(target.qualifiedName)}`, status: "analyzer", source: "codebase-memory", evidenceIds: [], importance: 1, evidence: [] };
      relation.evidenceIds.push(evidenceId);
      relation.evidence.push({ id: evidenceId, type: "CALLS", sourceSymbolId: sourceMethod.id, targetSymbolId: targetMethod.id, sourceQualifiedName: sourceMethod.qualifiedName, targetQualifiedName: targetMethod.qualifiedName });
      relation.importance = relation.evidenceIds.length;
      grouped.set(relationId, relation);
    }
    return { symbols: [...symbols.values()], relations: [...grouped.values()].sort((left, right) => right.importance - left.importance).slice(0, limit) };
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

  /** Reads public snippet metadata without depending on codebase-memory private storage. */
  private async readSnippet(projectId: string, qualifiedName: string): Promise<Record<string, unknown>> {
    try {
      const result = await this.client!.callTool({ name: "get_code_snippet", arguments: { project: projectId, qualified_name: qualifiedName, include_neighbors: false } });
      return (result as { structuredContent?: Record<string, unknown> }).structuredContent ?? this.parseText(result) as Record<string, unknown>;
    } catch { return {}; }
  }

}

/** Converts one public codebase-memory result into the language-independent symbol model. */
export function toCodeSymbol(projectId: string, row: Record<string, unknown>): CodeSymbol | undefined {
  const qualifiedName = String(row.qualified_name ?? row.qualifiedName ?? "");
  if (!qualifiedName) return undefined;
  const filePath = String(row.file_path ?? row.file ?? "");
  const identity = `${projectId}:${qualifiedName}:${filePath}`;
  const startLine = Number(row.start_line ?? row.startLine);
  const endLine = Number(row.end_line ?? row.endLine);
  const location = Number.isInteger(startLine) && startLine > 0 ? { startLine, endLine: Number.isInteger(endLine) && endLine >= startLine ? endLine : startLine } : undefined;
  return { id: stableHash(identity), projectId, language: String(row.language ?? "unknown"), kind: String(row.label ?? row.type ?? "Symbol"), filePath, qualifiedName, analyzerIdentity: identity, location };
}

/** Escapes an exact symbol name before passing it to graph regex matching. */
function escapeRegex(value: string): string { return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

function isClassifier(kind: string): boolean { return ["class", "interface", "struct", "enum", "record"].includes(kind.toLowerCase()); }

/** Converts one classifier query row into the shared symbol identity. */
function classSymbol(projectId: string, qualifiedName: unknown, filePath: unknown, start: unknown, end: unknown): CodeSymbol | undefined {
  return toCodeSymbol(projectId, { qualified_name: qualifiedName, file_path: filePath, label: "Class", start_line: start, end_line: end });
}

/** Converts one method query row into a navigable evidence symbol. */
function methodSymbol(projectId: string, qualifiedName: unknown, filePath: unknown, start: unknown, end: unknown): CodeSymbol | undefined {
  return toCodeSymbol(projectId, { qualified_name: qualifiedName, file_path: filePath, label: "Method", start_line: start, end_line: end });
}

function shortQualifiedName(value: string): string { return value.split(".").at(-1) ?? value; }
