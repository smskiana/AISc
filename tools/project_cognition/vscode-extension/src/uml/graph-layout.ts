import dagre from "@dagrejs/dagre";

export type UmlNodeKind = "domain" | "class";
export type UmlRelationKind = "inheritance" | "implementation" | "call" | "dependency";

export interface UmlNodeInput { id: string; kind: UmlNodeKind; title: string; subtitle: string; summary: string; status: string; }
export interface UmlEdgeInput { id: string; sourceId: string; targetId: string; label: string; kind: UmlRelationKind; status: string; evidenceCount: number; }
export interface UmlNode extends UmlNodeInput { x: number; y: number; width: number; height: number; }
export interface UmlEdge extends UmlEdgeInput { points: Array<{ x: number; y: number }>; }
export interface UmlGraph { width: number; height: number; nodes: UmlNode[]; edges: UmlEdge[]; }

const NODE_WIDTH = 224;
const NODE_HEIGHT = 96;

/** Uses Dagre to produce stable bounded coordinates for the UML webview. */
export function layoutUmlGraph(nodes: UmlNodeInput[], edges: UmlEdgeInput[]): UmlGraph {
  const graph = new dagre.graphlib.Graph({ multigraph: true });
  graph.setGraph({ rankdir: "LR", nodesep: 44, ranksep: 92, marginx: 32, marginy: 32 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const edge of edges) graph.setEdge(edge.sourceId, edge.targetId, {}, edge.id);
  dagre.layout(graph);
  const dimensions = graph.graph() as { width?: number; height?: number };
  return {
    width: Math.max(dimensions.width ?? 0, 320),
    height: Math.max(dimensions.height ?? 0, 220),
    nodes: nodes.map(node => ({ ...node, ...(graph.node(node.id) as { x: number; y: number }), width: NODE_WIDTH, height: NODE_HEIGHT })),
    edges: edges.map(edge => ({ ...edge, points: ((graph.edge({ v: edge.sourceId, w: edge.targetId, name: edge.id }) as { points: Array<{ x: number; y: number }> })?.points ?? []) }))
  };
}

/** Maps analyzer fact types to a small extensible UML relation vocabulary. */
export function relationKind(types: string[]): UmlRelationKind {
  const normalized = types.map(type => type.toUpperCase());
  if (normalized.some(type => type.includes("INHERIT") || type === "EXTENDS")) return "inheritance";
  if (normalized.some(type => type.includes("IMPLEMENT"))) return "implementation";
  if (normalized.some(type => type.includes("CALL"))) return "call";
  return "dependency";
}
