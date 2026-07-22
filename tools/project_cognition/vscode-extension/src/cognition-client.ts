import * as vscode from "vscode";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export class CognitionClient {
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

/** Returns the configured project identity. */
export function projectId(): string { return vscode.workspace.getConfiguration("projectCognition").get<string>("projectId", "AISc"); }
