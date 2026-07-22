import assert from "node:assert/strict";
import test from "node:test";
import { firstClassName, firstClassifier, resolveCurrentDomain } from "../src/current-domain.js";
import { Overview, SymbolRecord } from "../src/model.js";

const currentClass: SymbolRecord = { id: "class", qualifiedName: "Project.WebSocketClient", filePath: "Assets/Scripts/Core/WebSocketClient.cs", kind: "Class" };

test("current file class prefers a primary file membership and adds only a transient reference", () => {
  const overview: Overview = {
    snapshotId: "snapshot", codeRevision: "revision",
    domains: [{ id: "protocol", name: "Protocol", summary: "", status: "confirmed" }],
    symbols: [{ id: "method", qualifiedName: "Project.WebSocketClient.Start", filePath: currentClass.filePath, kind: "Method" }],
    memberships: [{ domainId: "protocol", symbolId: "method", type: "primary", status: "confirmed" }]
  };
  const resolved = resolveCurrentDomain(overview, currentClass, currentClass.filePath)!;
  assert.equal(resolved.domainId, "protocol");
  assert.equal(resolved.focusId, "class");
  assert.ok(resolved.overview.symbols.some(item => item.id === "class"));
  assert.ok(resolved.overview.memberships.some(item => item.symbolId === "class" && item.domainId === "protocol" && item.type === "reference"));
  assert.equal(overview.symbols.some(item => item.id === "class"), false);
});

test("current file class falls back to the virtual unclassified domain", () => {
  const overview: Overview = {
    snapshotId: "snapshot", codeRevision: "revision",
    domains: [{ id: "virtual:unclassified", name: "待归类", summary: "", status: "proposed" }],
    symbols: [], memberships: []
  };
  const resolved = resolveCurrentDomain(overview, currentClass, currentClass.filePath);
  assert.equal(resolved?.domainId, "virtual:unclassified");
  assert.equal(resolved?.focusId, "class");
});

test("first class detection supports flat SymbolInformation results", () => {
  assert.equal(firstClassName([{ name: "WebSocketClient", kind: 4 }], 4), "WebSocketClient");
});

test("first class detection preserves nested document traversal order", () => {
  const symbols = [{ name: "Namespace", kind: 2, children: [{ name: "First", kind: 4 }, { name: "Second", kind: 4 }] }];
  assert.equal(firstClassName(symbols, 4), "First");
});

test("code graph fallback selects the earliest class in the current file", () => {
  const later = { ...currentClass, id: "later", qualifiedName: "Project.Later", location: { startLine: 80, endLine: 100 } };
  const first = { ...currentClass, id: "first", qualifiedName: "Project.First", location: { startLine: 12, endLine: 40 } };
  assert.equal(firstClassifier([later, first])?.id, "first");
});
