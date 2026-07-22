import * as vscode from "vscode";
import { CognitionClient, projectId } from "./cognition-client.js";
import { CognitionTreeItem, DomainProvider } from "./domain-tree.js";
import { firstClassifier, resolveCurrentDomain } from "./current-domain.js";
import { ScopePreview, ScopeSymbol, SymbolRecord } from "./model.js";
import { findDocumentSymbolAtCursor, findFirstDocumentClassName, openSymbolLocation } from "./symbol-navigation.js";
import { UmlPanelController } from "./uml/uml-panel.js";

/** Activates the Project Cognition VS Code adapter. */
export function activate(context: vscode.ExtensionContext): void {
  const client = new CognitionClient();
  const provider = new DomainProvider(client);
  const uml = new UmlPanelController(client);
  context.subscriptions.push(vscode.window.registerTreeDataProvider("projectCognition.domains", provider));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.refresh", () => provider.refresh()));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.findSymbol", () => findSymbol(client, provider, uml)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.openSymbol", (item?: CognitionTreeItem) => openSymbol(item)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.showUml", async (item?: CognitionTreeItem) => { if (item) await uml.show(item.record.id, await provider.getOverview()); }));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.showRelations", async (item?: CognitionTreeItem) => { if (item) await uml.show(item.record.id, await provider.getOverview()); }));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.openCurrentUml", () => openCurrentFileUml(client, provider, uml)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.updateCurrent", () => updateCurrent(client, provider)));
  context.subscriptions.push(vscode.commands.registerCommand("projectCognition.fullUpdate", () => requestFullUpdate(client)));
  context.subscriptions.push(uml, { dispose: () => void client.close() });
}

/** Opens the functional-domain UML containing the first class declared by the active file. */
async function openCurrentFileUml(client: CognitionClient, provider: DomainProvider, uml: UmlPanelController): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const className = await findFirstDocumentClassName(editor.document.uri);
  const filePath = vscode.workspace.asRelativePath(editor.document.uri).replaceAll("\\", "/");
  const found = await client.call<{ symbols: SymbolRecord[] }>("find_symbol", { projectId: projectId(), query: className ?? "", filePath, symbolName: className, kind: "Class", limit: 20 });
  const symbol = firstClassifier(found.symbols.filter(item => (item.kind ?? "").toLowerCase() === "class"));
  if (!symbol) { await vscode.window.showWarningMessage(`Project Cognition: no class was found for ${filePath}.`); return; }
  const resolution = resolveCurrentDomain(await provider.getOverview(), symbol, filePath);
  if (!resolution) { await vscode.window.showWarningMessage("Project Cognition: update this file before opening its functional-domain UML."); return; }
  await uml.show(resolution.focusId, resolution.overview, symbol);
}

/** Finds a symbol and opens its class-centered UML view. */
async function findSymbol(client: CognitionClient, provider: DomainProvider, uml: UmlPanelController): Promise<void> {
  const query = await vscode.window.showInputBox({ prompt: "Symbol or responsibility" });
  if (!query) return;
  const data = await client.call<{ symbols: SymbolRecord[] }>("find_symbol", { projectId: projectId(), query, limit: 30 });
  const picked = await vscode.window.showQuickPick(data.symbols.map(symbol => ({ label: symbol.qualifiedName, description: symbol.filePath, symbol })), { matchOnDescription: true });
  if (picked) await uml.show(picked.symbol.id, await provider.getOverview(), picked.symbol);
}

/** Opens a stored symbol in the workspace. */
async function openSymbol(item?: CognitionTreeItem): Promise<void> {
  if (item?.kind === "symbol") await openSymbolLocation(item.record as SymbolRecord);
}

/** Resolves, previews, and explicitly applies a local update from IDE context. */
async function updateCurrent(client: CognitionClient, provider: DomainProvider): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;
  const selected = editor.document.getText(editor.selection).trim();
  const relativePath = vscode.workspace.asRelativePath(editor.document.uri).replaceAll("\\", "/");
  const documentSymbol = selected ? undefined : await findDocumentSymbolAtCursor(editor.document.uri, editor.selection.active);
  const symbolName = selected || documentSymbol?.name || fileStem(relativePath);
  const query = symbolName || relativePath;
  const scope = await client.call<ScopePreview>("resolve_update_scope", { projectId: projectId(), query, filePath: relativePath, symbolName, maxFiles: 20, maxSymbols: 30, maxRelations: 100 });
  const preview = await client.call<ScopePreview>("preview_scoped_update", { projectId: projectId(), scopeId: scope.scopeId });
  const action = await vscode.window.showInformationMessage("Apply scoped cognition update?", { modal: true, detail: formatScopePreview(preview) }, "Apply");
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

/** Formats the complete signed scope for the modal confirmation. */
function formatScopePreview(preview: ScopePreview): string {
  const lines = [
    `Target domain: ${preview.targetDomain.name}${preview.targetDomain.exploration ? " (exploration)" : ""}`,
    `Included symbols (${preview.includedSymbols.length}): ${formatSymbolNames(preview.includedSymbols)}`,
    `Read-only evidence (${preview.readOnlyEvidence.length}): ${formatSymbolNames(preview.readOnlyEvidence)}`,
    `Excluded symbols (${preview.excludedSymbols.length}): ${formatSymbolNames(preview.excludedSymbols)}`,
    `Excluded domains (${preview.excludedDomains.length}): ${preview.excludedDomains.map(item => item.name).join(", ") || "none"}`,
    `Estimated cost: ${preview.estimatedCost.files} files, ${preview.estimatedCost.symbols} symbols, relation budget ${preview.estimatedCost.relationsBudget}`,
    `Changes: ${preview.changeIds.length}`
  ];
  return [...lines, ...preview.warnings].join("\n");
}

/** Formats a bounded list of qualified names without hiding overflow. */
function formatSymbolNames(symbols: ScopeSymbol[]): string { const visible = symbols.slice(0, 12).map(item => item.qualifiedName); return `${visible.join(", ") || "none"}${symbols.length > visible.length ? ` (+${symbols.length - visible.length} more)` : ""}`; }
/** Returns a repository-relative filename without its final extension. */
function fileStem(filePath: string): string { const name = filePath.split("/").at(-1) ?? filePath; return name.replace(/\.[^.]+$/, ""); }
/** Deactivates the extension; resources are owned by subscriptions. */
export function deactivate(): void {}
