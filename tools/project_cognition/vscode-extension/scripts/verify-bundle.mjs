import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

/** Verifies that the VSIX entry point contains its non-VS Code runtime dependencies. */
async function main() {
  const entry = new URL("../dist/extension.js", import.meta.url);
  const source = await readFile(entry, "utf8");
  const metadata = await stat(entry);
  assert.ok(metadata.size > 100_000, "Extension bundle is too small to contain the MCP SDK runtime.");
  assert.doesNotMatch(source, /require\(["']@modelcontextprotocol\//, "MCP SDK remains an unresolved runtime dependency.");
  assert.match(source, /require\(["']vscode["']\)/, "VS Code must remain an extension-host external.");
  assert.match(source, /Project Cognition UML/, "UML panel controller is missing from the extension bundle.");
  assert.match(source, /marker-end/, "UML relation arrow rendering is missing from the extension bundle.");
  assert.doesNotMatch(source, /full\.textContent=node\.title\+'\r?\n/, "UML webview contains an unterminated JavaScript string.");
  assert.match(source, /full\.textContent=node\.title\+'\\\\n'/, "UML tooltip newline must remain escaped in generated JavaScript.");
  assert.match(source, /uml\.show\(resolution\.focusId/, "Current-file UML command must open the class focus, not only its domain.");
  assert.match(source, /class:'edge-hit'/, "UML relations need a wide transparent pointer target.");
  assert.match(source, /group\.onclick=\(\)=>openEvidence\(edge\)/, "UML relation lines and labels must share evidence interaction.");
  assert.match(source, /edge-tooltip/, "UML relations must include a visible hover tooltip.");
  console.log(JSON.stringify({ ok: true, bytes: metadata.size, external: ["vscode"] }));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
