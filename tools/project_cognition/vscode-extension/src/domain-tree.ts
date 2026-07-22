import * as vscode from "vscode";
import { CognitionClient, projectId } from "./cognition-client.js";
import { Domain, Overview, shortName, SymbolRecord } from "./model.js";

export class CognitionTreeItem extends vscode.TreeItem {
  /** Creates a stable functional-domain or symbol tree node. */
  public constructor(public readonly kind: "domain" | "symbol", public readonly record: Domain | SymbolRecord, state: vscode.TreeItemCollapsibleState) {
    super(kind === "domain" ? (record as Domain).name : shortName((record as SymbolRecord).qualifiedName), state);
    this.id = `${kind}:${record.id}`;
    this.contextValue = `projectCognition.${kind}`;
    this.description = kind === "domain" ? (record as Domain).status : (record as SymbolRecord).status ?? "analyzer";
    this.tooltip = kind === "domain" ? (record as Domain).summary : `${(record as SymbolRecord).qualifiedName}\n${(record as SymbolRecord).filePath}`;
    this.iconPath = new vscode.ThemeIcon(kind === "domain" ? "folder-library" : "symbol-class");
    this.command = { command: "projectCognition.showUml", title: "Open UML", arguments: [this] };
  }
}

export class DomainProvider implements vscode.TreeDataProvider<CognitionTreeItem> {
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
    return [...children, ...overview.symbols.filter(item => symbolIds.has(item.id) && isClassifier(item)).map(item => new CognitionTreeItem("symbol", item, vscode.TreeItemCollapsibleState.None))];
  }
  /** Returns the cached overview for commands that share the tree projection. */
  public async getOverview(): Promise<Overview> { return this.load(); }
  private async load(): Promise<Overview> {
    if (!this.overview) this.overview = await this.client.call<Overview>("get_domain_overview", { projectId: projectId() });
    return this.overview;
  }
  private domainItem(domain: Domain, overview: Overview): CognitionTreeItem {
    const expandable = overview.domains.some(item => item.parentId === domain.id) || overview.memberships.some(item => item.domainId === domain.id);
    return new CognitionTreeItem("domain", domain, expandable ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
  }
}

/** Keeps methods and fields in relation evidence instead of the class navigation tree. */
function isClassifier(symbol: SymbolRecord): boolean { return ["class", "interface", "struct", "enum", "record"].includes((symbol.kind ?? "").toLowerCase()); }
