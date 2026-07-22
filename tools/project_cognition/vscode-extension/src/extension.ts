import * as vscode from "vscode";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

interface Domain { id: string; name: string; summary: string; parentId?: string; status: string; }
interface SymbolRecord { id: string; qualifiedName: string; filePath: string; summary?: string; status?: string; }
interface Membership { domainId: string; symbolId: string; type: string; status: string; }
interface Overview { snapshotId: string; codeRevision: string; domains: Domain[]; memberships: Membership[]; symbols: SymbolRecord[]; }
interface Relation { id: string; sourceSymbolId: string; targetSymbolId: string; summary: string; status: string; source: string; evidenceIds: string[]; importance?: number; }

class CognitionClient {
  private client?: Client;

  /** Starts the configured Project Cognition MCP server. */
  public async connect(): Promise<Client> {
    if (this.client) return this.client;
    const config = vscode.workspace.getConfiguration("projectCognition");
    const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "";
    const command = config.get<string>("serverCommand", "node");
    const args = config.get<string[]>("serverArgs", []).map(value => value.replace("${workspaceFolder}", root));
    this.client = new Client({ name: "project-cognition-vscode", version: "0.1.0" });
    await this.client.connect(new StdioClientTransport({ command, args, cwd: root }));
    return this.client;
  }

  /** Calls one MCP tool and returns its structured data payload. */
  public async call<T>(name: string, args: Record<string, unknown>): Promise<T> {
    const result = await (await this.connect()).callTool({ name, arguments: args });
    const structured = (result as { structuredContent?: { ok?: boolean; data?: T; error?: { code: string; message: string } } }).structuredContent;
    if (!structured?.ok) throw new Error(`${structured?.error?.code ?? "MCP_ERROR"}: ${structured?.error?.message ?? "Unknown MCP failure"}`);
    return structured.data as T;
  }

  /** Closes the MCP child process. */
  public async close(): Promise<void> { await this.client?.close(); this.client = undefined; }
}

class CognitionTreeItem extends vscode.TreeItem {
  /** Creates a stable functional-domain or symbol tree node. */
  public constructor(public readonly kind: "domain" | "symbol", public readonly record: Domain | SymbolRecord, state: vscode.TreeItemCollapsibleState) {
    super(kind === "domain" ? (record as Domain).name : shortName((record as SymbolRecord).qualifiedName), state);
    this.id = `${kind}:${record.id}`;
    this.contextValue = `projectCognition.${kind}`;
    this.description = kind === "domain" ? (record as Domain).status : (record as SymbolRecord).status ?? "analyzer";
    this.tooltip = kind === "domain" ? (record as Domain).summary : `${(record as SymbolRecord).qualifiedName}\n${(record as SymbolRecord).filePath}`;
    this.iconPath = new vscode.ThemeIcon(kind === "domain" ? "folder-library" : "symbol-class");
    if (kind === "symbol") this.command = { command: "projectCognition.showRelations", title: "Show Relations", arguments: [this] };
  }
}

class DomainProvider implements vscode.TreeDataProvider<CognitionTreeItem> {
  private readonly changed = new vscode.EventEmitter<void>();
  private overview?: Overview;
  public readonly onDidChangeTreeData = this.changed.event;
  public constructor(private readonly client: CognitionClient) {}
  /** Refreshes the domain tree from the MCP snapshot. */
  public refresh(): void { this.overview = undefined; this.changed.fire(); }
  /** Returns the supplied tree item unchanged. */
  public getTreeItem(item: CognitionTreeItem): vscode.TreeItem { return item; }

  /** Loads domain hierarchy and shared symbol identities on demand. */
  public async getChildren(element?: CognitionTreeItem): Promise<CognitionTreeItem[]> {
    const overview = await this.load();
    if (!element) return overview.domains.filter(item => !item.parentId).map(item => this.domainItem(item, overview));
    if (element.kind === "symbol") return [];
    const domain = element.record as Domain;
    const children = overview.domains.filter(item => item.parentId === domain.id).map(item => this.domainItem(item, overview));
    const symbolIds = new Set(overview.memberships.filter(item => item.domainId === domain.id).map(item => item.symbolId));
    return [...children, ...overview.symbols.filter(item => symbolIds.has(item.id)).map(item => new CognitionTreeItem("symbol", item, vscode.TreeItemCollapsibleState.None))];
  }

  private async load(): Promise<Overview> {
    if (!this.overview) this.overview = await this.client.call<Overview>("get_domain_overview", { projectId: projectId() });
    return this.overview;
  }

  private domainItem(domain: Domain, overview: Overview): CognitionTreeItem {
    const expandable = overview.domains.some(item => item.parentId === domain.id) || overview.memberships.some(item => item.domainId === domain.id);
    return new CognitionTreeItem("domain", domain, expandable ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
  }
}

/** Activates the Project Cognition VS Code adapter. */
export function activate(context: vscode.ExtensionContext): void {
  const client = new CognitionClient();
  const provider = new DomainProvider(client);
  context.subscriptions.push(vscode.window.registerTreeDataProvider("projectCognition.domains", provider));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.refresh", () => provider.refresh()));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.findSymbol", () => findSymbol(client)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.openSymbol", (item?: CognitionTreeItem) => openSymbol(item)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.showRelations", (item?: CognitionTreeItem) => showRelations(client, item)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.updateCurrent", () => updateCurrent(client, provider)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.fullUpdate", () => requestFullUpdate(client)));
  context.subscriptions.push({ dispose: () => void client.close() });
}

/** Finds a symbol and opens its relation view or source file. */
async function findSymbol(client: CognitionClient): Promise<void> {
  const query = await vscode.window.showInputBox({ prompt: "Symbol or responsibility" });
  if (!query) return;
  const data = await client.call<{ symbols: SymbolRecord[] }>("find_symbol", { projectId: projectId(), query, limit: 30 });
  const picked = await vscode.window.showQuickPick(data.symbols.map(symbol => ({ label: symbol.qualifiedName, description: symbol.filePath, symbol })), { matchOnDescription: true });
  if (picked) await openPath(picked.symbol.filePath);
}

/** Opens a stored symbol in the workspace. */
async function openSymbol(item?: CognitionTreeItem): Promise<void> {
  if (item?.kind === "symbol") await openPath((item.record as SymbolRecord).filePath);
}

/** Displays bounded primary relations and expands evidence on explicit clicks. */
async function showRelations(client: CognitionClient, item?: CognitionTreeItem): Promise<void> {
  if (!item) return;
  const nodeId = item.record.id;
  const relations = await client.call<Relation[]>("get_primary_relations", { projectId: projectId(), nodeId, limit: 50 });
  const panel = vscode.window.createWebviewPanel("projectCognition.relations", `Relations: ${item.label}`, vscode.ViewColumn.One, { enableScripts: true });
  panel.webview.html = relationHtml(item, relations);
  panel.webview.onDidReceiveMessage(async message => {
    if (message.command !== "evidence") return;
    const expanded = await client.call<{ evidence: Array<{ id: string; type: string; sourceSymbolId: string; targetSymbolId: string }>; missingEvidenceIds: string[] } | undefined>("expand_relation_evidence", { projectId: projectId(), relationId: message.relationId, limit: 100 });
    const rows = expanded?.evidence.map(evidence => `${evidence.type}: ${evidence.sourceSymbolId} -> ${evidence.targetSymbolId}`) ?? [];
    await vscode.window.showQuickPick([...rows, ...(expanded?.missingEvidenceIds ?? []).map(id => `stale: ${id}`)], { title: "Relation evidence", canPickMany: false });
  });
}

/** Resolves, previews, and explicitly applies a local update from IDE context. */
async function updateCurrent(client: CognitionClient, provider: DomainProvider): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const selected = editor.document.getText(editor.selection).trim();
  const query = selected || vscode.workspace.asRelativePath(editor.document.uri);
  const scope = await client.call<{ scopeId: string; resolvedScope: string[]; evidenceScope: string[]; mutationScope: string[]; excluded: string[]; warnings: string[] }>("resolve_update_scope", { projectId: projectId(), query, maxFiles: 20, maxSymbols: 30, maxRelations: 100 });
  const preview = await client.call<{ id: string; changeIds: string[]; requestedScope: string[]; mutationScope: string[]; evidenceScope: string[]; excluded: string[]; warnings: string[] }>("preview_scoped_update", { projectId: projectId(), scopeId: scope.scopeId, query });
  const detail = [`Mutable: ${preview.mutationScope.length}`, `Read-only evidence: ${preview.evidenceScope.length - preview.mutationScope.length}`, `Excluded: ${preview.excluded.length}`, `Changes: ${preview.changeIds.length}`, ...preview.warnings].join("\n");
  const action = await vscode.window.showInformationMessage("Apply scoped cognition update?", { modal: true, detail }, "Apply");
  if (action !== "Apply") return;
  await client.call("apply_scoped_update", { projectId: projectId(), scopeId: scope.scopeId, previewId: preview.id, acceptedChangeIds: preview.changeIds });
  provider.refresh();
}

/** Requests the separately confirmed full-update authorization. */
async function requestFullUpdate(client: CognitionClient): Promise<void> {
  const confirmation = `FULL UPDATE ${projectId()}`;
  const entered = await vscode.window.showInputBox({ prompt: `Type ${confirmation}`, ignoreFocusOut: true });
  if (entered !== confirmation) return;
  const scope = await client.call<{ resolvedScope: string[]; excluded: string[] }>("request_full_update", { projectId: projectId(), explicitConfirmation: entered, query: "class function method", maxFiles: 200, maxSymbols: 2000 });
  await vscode.window.showInformationMessage(`Full update scope authorized: ${scope.resolvedScope.length} symbols, ${scope.excluded.length} excluded.`);
}

/** Builds the bounded central relation view. */
function relationHtml(item: CognitionTreeItem, relations: Relation[]): string {
  const rows = relations.map(relation => `<tr><td>${escapeHtml(relation.summary)}</td><td>${escapeHtml(relation.status)}</td><td>${escapeHtml(relation.source)}</td><td>${relation.evidenceIds.length}</td><td><button data-id="${escapeHtml(relation.id)}">Evidence</button></td></tr>`).join("");
  return `<!doctype html><html><head><meta charset="UTF-8"><style>body{font-family:var(--vscode-font-family);color:var(--vscode-foreground);padding:16px}h1{font-size:18px}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid var(--vscode-panel-border);padding:8px;text-align:left}button{color:var(--vscode-button-foreground);background:var(--vscode-button-background);border:0;padding:6px 10px}</style></head><body><h1>${escapeHtml(String(item.label))}</h1><table><thead><tr><th>Relation</th><th>Status</th><th>Source</th><th>Evidence</th><th></th></tr></thead><tbody>${rows}</tbody></table><script>const vscode=acquireVsCodeApi();document.querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>vscode.postMessage({command:'evidence',relationId:button.dataset.id})));</script></body></html>`;
}

/** Escapes untrusted cognition text before rendering webview HTML. */
function escapeHtml(value: string): string { return value.replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[char]!); }
/** Returns the configured project identity. */
function projectId(): string { return vscode.workspace.getConfiguration("projectCognition").get<string>("projectId", "AISc"); }
/** Returns a compact display name for a qualified symbol. */
function shortName(qualifiedName: string): string { return qualifiedName.split(/[.:]/).filter(Boolean).at(-1) ?? qualifiedName; }
/** Opens one repository-relative source path. */
async function openPath(filePath: string): Promise<void> { const root = vscode.workspace.workspaceFolders?.[0]?.uri; if (root) await vscode.commands.executeCommand("vscode.open", vscode.Uri.joinPath(root, ...filePath.replaceAll("\\", "/").split("/"))); }

/** Deactivates the extension; resources are owned by subscriptions. */
export function deactivate(): void {}
