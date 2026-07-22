import * as vscode from "vscode";
import { DocumentSymbolLike, firstClassName } from "./current-domain.js";
import { SymbolRecord } from "./model.js";

/** Opens one symbol and selects its analyzer-provided source range. */
export async function openSymbolLocation(symbol: SymbolRecord): Promise<void> {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri;
  if (!root) return;
  const uri = vscode.Uri.joinPath(root, ...symbol.filePath.replaceAll("\\", "/").split("/"));
  const start = Math.max(0, (symbol.location?.startLine ?? 1) - 1);
  const end = Math.max(start, (symbol.location?.endLine ?? symbol.location?.startLine ?? 1) - 1);
  const editor = await vscode.window.showTextDocument(uri, { preview: false, selection: new vscode.Range(start, 0, end, 0) });
  editor.revealRange(new vscode.Range(start, 0, start, 0), vscode.TextEditorRevealType.InCenterIfOutsideViewport);
}

/** Finds the innermost document symbol containing the active cursor. */
export async function findDocumentSymbolAtCursor(uri: vscode.Uri, position: vscode.Position): Promise<vscode.DocumentSymbol | undefined> {
  const roots = await vscode.commands.executeCommand<Array<vscode.DocumentSymbol | vscode.SymbolInformation>>("vscode.executeDocumentSymbolProvider", uri) ?? [];
  const documentSymbols = roots.filter((item): item is vscode.DocumentSymbol => "range" in item && "children" in item);
  const visit = (items: vscode.DocumentSymbol[]): vscode.DocumentSymbol | undefined => {
    for (const item of items) {
      if (!item.range.contains(position)) continue;
      return visit(item.children) ?? item;
    }
    return undefined;
  };
  return visit(documentSymbols);
}

/** Returns the first class name from flat or hierarchical document symbols. */
export async function findFirstDocumentClassName(uri: vscode.Uri): Promise<string | undefined> {
  const roots = await vscode.commands.executeCommand<Array<vscode.DocumentSymbol | vscode.SymbolInformation>>("vscode.executeDocumentSymbolProvider", uri) ?? [];
  return firstClassName(roots as DocumentSymbolLike[], vscode.SymbolKind.Class);
}
