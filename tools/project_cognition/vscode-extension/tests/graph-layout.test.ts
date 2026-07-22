import assert from "node:assert/strict";
import test from "node:test";
import { layoutUmlGraph, relationKind } from "../src/uml/graph-layout.js";

test("Dagre lays out bounded UML nodes without overlap", () => {
  const graph = layoutUmlGraph([
    { id: "a", kind: "class", title: "A", subtitle: "Class", summary: "source", status: "confirmed" },
    { id: "b", kind: "class", title: "B", subtitle: "Class", summary: "target", status: "confirmed" }
  ], [{ id: "edge", sourceId: "a", targetId: "b", label: "calls", kind: "call", status: "confirmed", evidenceCount: 1 }]);
  assert.equal(graph.nodes.length, 2);
  assert.equal(graph.edges[0]?.points.length > 1, true);
  assert.notEqual(graph.nodes[0]?.x, graph.nodes[1]?.x);
  assert.ok(graph.width >= 320 && graph.height >= 220);
});

test("fact types map to distinguishable UML edge families", () => {
  assert.equal(relationKind(["INHERITS"]), "inheritance");
  assert.equal(relationKind(["IMPLEMENTS"]), "implementation");
  assert.equal(relationKind(["CALLS"]), "call");
  assert.equal(relationKind(["REFERENCES"]), "dependency");
});
