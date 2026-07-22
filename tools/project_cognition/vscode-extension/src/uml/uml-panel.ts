import * as vscode from "vscode";
import { CognitionClient, projectId } from "../cognition-client.js";
import { ClassifierContext, Domain, Overview, Relation, RelationEvidence, shortName, SymbolRecord } from "../model.js";
import { openSymbolLocation } from "../symbol-navigation.js";
import { layoutUmlGraph, relationKind, UmlEdgeInput, UmlGraph, UmlNodeInput } from "./graph-layout.js";
import { buildEvidencePicks } from "./evidence-navigation.js";

const MAX_NODES = 40;
const MAX_RELATIONS = 80;

interface GraphPayload { graph: UmlGraph; title: string; breadcrumbs: Array<{ id: string; label: string }>; revision: string; notice?: string; }

export class UmlPanelController implements vscode.Disposable {
  private panel?: vscode.WebviewPanel;
  private overview?: Overview;
  private focusId?: string;
  private readonly history: string[] = [];
  private readonly transientEvidence = new Map<string, RelationEvidence>();

  public constructor(private readonly client: CognitionClient) {}

  /** Opens or navigates the shared UML cognition panel. */
  public async show(recordId: string, overview?: Overview, seedSymbol?: SymbolRecord): Promise<void> {
    this.overview = overview ?? await this.client.call<Overview>("get_domain_overview", { projectId: projectId() });
    if (seedSymbol && !this.overview.symbols.some(item => item.id === seedSymbol.id)) {
      this.overview = { ...this.overview, symbols: [...this.overview.symbols, seedSymbol] };
    }
    if (this.focusId && this.focusId !== recordId) this.history.push(this.focusId);
    this.focusId = recordId;
    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel("projectCognition.uml", "Project Cognition UML", vscode.ViewColumn.One, { enableScripts: true, retainContextWhenHidden: true });
      this.panel.onDidDispose(() => { this.panel = undefined; });
      this.panel.webview.onDidReceiveMessage(message => void this.receive(message));
    }
    this.panel.reveal(vscode.ViewColumn.One, true);
    await this.render();
  }

  /** Releases the UML panel owned by this controller. */
  public dispose(): void { this.panel?.dispose(); this.panel = undefined; }

  /** Handles only known graph interactions and validates IDs against the current overview. */
  private async receive(message: { command?: string; id?: string }): Promise<void> {
    if (!this.overview || !message.command) return;
    if (message.command === "back") {
      const previous = this.history.pop();
      if (previous) { this.focusId = previous; await this.render(); }
      return;
    }
    if (!message.id) return;
    const domain = this.overview.domains.find(item => item.id === message.id);
    const symbol = this.overview.symbols.find(item => item.id === message.id);
    if (message.command === "navigate" && (domain || symbol)) await this.show(message.id, this.overview);
    if (message.command === "open" && symbol) await openSymbolLocation(symbol);
    if (message.command === "evidence") await this.showEvidence(message.id);
  }

  /** Rebuilds the bounded graph from the latest selected domain or class. */
  private async render(): Promise<void> {
    if (!this.panel || !this.overview || !this.focusId) return;
    const payload = await this.buildPayload(this.focusId);
    this.panel.title = `UML: ${payload.title}`;
    this.panel.webview.html = umlHtml(payload);
  }

  /** Builds a one-level domain graph or a one-hop class-centered graph. */
  private async buildPayload(focusId: string): Promise<GraphPayload> {
    let overview = this.overview!;
    let focusDomain = overview.domains.find(item => item.id === focusId);
    if (focusDomain) {
      const domainIds = [focusDomain.id, ...overview.domains.filter(item => item.parentId === focusDomain!.id).map(item => item.id)];
      overview = await this.hydrateDomainClassifiers(overview, domainIds);
      this.overview = overview;
      focusDomain = overview.domains.find(item => item.id === focusId);
    }
    const focusSymbol = overview.symbols.find(item => item.id === focusId);
    let classifierContext: ClassifierContext | undefined;
    if (focusSymbol && isClassifier(focusSymbol)) {
      classifierContext = await this.client.call<ClassifierContext>("get_classifier_context", { projectId: projectId(), qualifiedName: focusSymbol.qualifiedName, limit: MAX_RELATIONS });
      overview = { ...overview, symbols: [...new Map([...overview.symbols, ...classifierContext.symbols].map(item => [item.id, item])).values()] };
      this.overview = overview;
    }
    const relationScopes = focusDomain ? [focusDomain.id, ...overview.domains.filter(item => item.parentId === focusDomain.id).map(item => item.id)] : [focusId];
    const relationGroups = await Promise.all(relationScopes.map(nodeId => this.client.call<Relation[]>("get_primary_relations", { projectId: projectId(), nodeId, limit: MAX_RELATIONS })));
    const relations = [...new Map([...relationGroups.flat(), ...(classifierContext?.relations ?? [])].map(item => [item.id, item])).values()].slice(0, MAX_RELATIONS);
    const evidence = new Map<string, RelationEvidence>((classifierContext?.relations ?? []).map(relation => [relation.id, { evidence: relation.evidence, missingEvidenceIds: [] }]));
    await Promise.all(relations.filter(relation => !evidence.has(relation.id)).map(async relation => {
      try { evidence.set(relation.id, await this.client.call<RelationEvidence>("expand_relation_evidence", { projectId: projectId(), relationId: relation.id, limit: 100 })); }
      catch { evidence.set(relation.id, { evidence: [], missingEvidenceIds: relation.evidenceIds }); }
    }));
    this.transientEvidence.clear();
    for (const [id, value] of evidence) this.transientEvidence.set(id, value);
    const selected = selectNodes(overview, focusDomain, focusSymbol, relations);
    const projected = projectEdges(overview, selected, relations, evidence);
    const nodes = selected.map<UmlNodeInput>(record => recordToNode(record));
    const notice = selected.length >= MAX_NODES ? `节点预算已限制为 ${MAX_NODES}，请下钻功能域或选择类查看一跳关系。` : undefined;
    return {
      graph: layoutUmlGraph(nodes, projected.slice(0, MAX_RELATIONS)),
      title: focusDomain?.name ?? shortName(focusSymbol?.qualifiedName ?? focusId),
      breadcrumbs: focusDomain ? domainBreadcrumbs(overview, focusDomain) : symbolBreadcrumbs(overview, focusSymbol),
      revision: overview.codeRevision,
      notice
    };
  }

  /** Projects classifier nodes from member file paths when older snapshots contain only methods. */
  private async hydrateDomainClassifiers(overview: Overview, domainIds: string[]): Promise<Overview> {
    const domainSet = new Set(domainIds);
    const symbolsById = new Map(overview.symbols.map(item => [item.id, item]));
    const requests = new Map<string, { domainId: string; filePath: string }>();
    for (const membership of overview.memberships) {
      if (!domainSet.has(membership.domainId)) continue;
      const member = symbolsById.get(membership.symbolId);
      if (!member?.filePath || isClassifier(member)) continue;
      requests.set(`${membership.domainId}:${member.filePath.toLowerCase()}`, { domainId: membership.domainId, filePath: member.filePath });
      if (requests.size >= MAX_NODES) break;
    }
    if (!requests.size) return overview;
    const resolved = await Promise.all([...requests.values()].map(async request => ({
      request,
      result: await this.client.call<{ symbols: SymbolRecord[] }>("find_symbol", { projectId: projectId(), query: "", filePath: request.filePath, kind: "Class", limit: 10 })
    })));
    const symbols = [...overview.symbols];
    const memberships = [...overview.memberships];
    for (const { request, result } of resolved) {
      for (const symbol of result.symbols.filter(isClassifier)) {
        if (!symbols.some(item => item.id === symbol.id)) symbols.push(symbol);
        if (!memberships.some(item => item.domainId === request.domainId && item.symbolId === symbol.id)) {
          memberships.push({ domainId: request.domainId, symbolId: symbol.id, type: "reference", status: "analyzer" });
        }
      }
    }
    return { ...overview, symbols, memberships };
  }

  /** Expands method-level fact evidence and opens the selected known symbol. */
  private async showEvidence(relationId: string): Promise<void> {
    if (!this.overview) return;
    const expanded = this.transientEvidence.get(relationId) ?? await this.client.call<RelationEvidence>("expand_relation_evidence", { projectId: projectId(), relationId, limit: 100 });
    const picks = buildEvidencePicks(expanded, this.overview.symbols);
    const stale = expanded.missingEvidenceIds.map(id => ({ label: `stale: ${id}`, symbol: undefined as SymbolRecord | undefined }));
    const picked = await vscode.window.showQuickPick([...picks, ...stale], { title: "Relation evidence" });
    if (picked?.symbol) await openSymbolLocation(picked.symbol);
  }
}

/** Selects only the current layer or one-hop class neighborhood. */
function selectNodes(overview: Overview, domain: Domain | undefined, symbol: SymbolRecord | undefined, relations: Relation[]): Array<Domain | SymbolRecord> {
  if (symbol) {
    const ids = new Set([symbol.id]);
    for (const relation of relations) { ids.add(relation.sourceSymbolId); ids.add(relation.targetSymbolId); }
    return overview.symbols.filter(item => ids.has(item.id)).slice(0, MAX_NODES);
  }
  if (!domain) return [];
  const children = overview.domains.filter(item => item.parentId === domain.id);
  const directIds = new Set(overview.memberships.filter(item => item.domainId === domain.id).map(item => item.symbolId));
  return [...children, ...overview.symbols.filter(item => directIds.has(item.id) && isClassifier(item))].slice(0, MAX_NODES);
}

/** Aggregates symbol relations onto the visible current-layer domain or class nodes. */
function projectEdges(overview: Overview, nodes: Array<Domain | SymbolRecord>, relations: Relation[], evidence: Map<string, RelationEvidence>): UmlEdgeInput[] {
  const nodeIds = new Set(nodes.map(item => item.id));
  const childDomains = new Set(nodes.filter(isDomain).map(item => item.id));
  const symbolProjection = new Map<string, string>();
  for (const membership of overview.memberships) if (childDomains.has(membership.domainId)) symbolProjection.set(membership.symbolId, membership.domainId);
  const resolve = (id: string) => nodeIds.has(id) ? id : symbolProjection.get(id);
  return relations.flatMap(relation => {
    const sourceId = resolve(relation.sourceSymbolId);
    const targetId = resolve(relation.targetSymbolId);
    if (!sourceId || !targetId || sourceId === targetId) return [];
    const facts = evidence.get(relation.id)?.evidence ?? [];
    return [{ id: relation.id, sourceId, targetId, label: relation.summary, kind: relationKind(facts.map(item => item.type)), status: relation.status, evidenceCount: relation.evidenceIds.length }];
  });
}

/** Converts a domain or class record to the intentionally compact UML classifier shape. */
function recordToNode(record: Domain | SymbolRecord): UmlNodeInput {
  if (isDomain(record)) return { id: record.id, kind: "domain", title: record.name, subtitle: "功能域", summary: record.summary, status: record.status };
  return { id: record.id, kind: "class", title: shortName(record.qualifiedName), subtitle: record.kind ?? "Class", summary: record.summary ?? "暂无职责摘要", status: record.status ?? "analyzer" };
}

function isDomain(record: Domain | SymbolRecord): record is Domain { return "name" in record; }

/** Keeps method-level symbols available for evidence but out of UML classifier nodes. */
function isClassifier(symbol: SymbolRecord): boolean { return ["class", "interface", "struct", "enum", "record"].includes((symbol.kind ?? "").toLowerCase()); }

/** Builds root-to-current breadcrumbs without mixing hierarchy with UML edges. */
function domainBreadcrumbs(overview: Overview, domain: Domain): Array<{ id: string; label: string }> {
  const byId = new Map(overview.domains.map(item => [item.id, item]));
  const path: Domain[] = [];
  for (let current: Domain | undefined = domain; current; current = current.parentId ? byId.get(current.parentId) : undefined) path.unshift(current);
  return path.map(item => ({ id: item.id, label: item.name }));
}

function symbolBreadcrumbs(overview: Overview, symbol?: SymbolRecord): Array<{ id: string; label: string }> {
  if (!symbol) return [];
  const membership = overview.memberships.find(item => item.symbolId === symbol.id && item.type === "primary") ?? overview.memberships.find(item => item.symbolId === symbol.id);
  const domain = overview.domains.find(item => item.id === membership?.domainId);
  return [...(domain ? domainBreadcrumbs(overview, domain) : []), { id: symbol.id, label: shortName(symbol.qualifiedName) }];
}

/** Renders the interactive SVG UML surface with CSP-safe inline data. */
function umlHtml(payload: GraphPayload): string {
  const data = JSON.stringify(payload).replaceAll("<", "\\u003c");
  return `<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  :root{color-scheme:light dark}*{box-sizing:border-box}body{margin:0;color:var(--vscode-foreground);background:var(--vscode-editor-background);font-family:var(--vscode-font-family);overflow:hidden}header{height:46px;display:flex;align-items:center;gap:8px;padding:0 12px;border-bottom:1px solid var(--vscode-panel-border);background:var(--vscode-sideBar-background)}button{border:0;color:var(--vscode-button-foreground);background:var(--vscode-button-background);height:30px;min-width:30px;padding:0 9px;cursor:pointer}button:hover{background:var(--vscode-button-hoverBackground)}nav{display:flex;align-items:center;gap:5px;min-width:0;overflow:hidden}.crumb{background:transparent;color:var(--vscode-textLink-foreground);padding:0 3px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{margin-left:auto;color:var(--vscode-descriptionForeground);font-size:12px;white-space:nowrap}.notice{position:absolute;z-index:3;top:56px;left:12px;max-width:520px;padding:7px 10px;background:var(--vscode-inputValidation-warningBackground);border:1px solid var(--vscode-inputValidation-warningBorder)}#viewport{height:calc(100vh - 46px);overflow:auto}svg{display:block;min-width:100%;min-height:100%}.node{cursor:pointer}.node rect{fill:var(--vscode-editorWidget-background);stroke:var(--vscode-panel-border);stroke-width:1.5}.node.domain rect{fill:var(--vscode-sideBar-background);stroke:var(--vscode-textLink-foreground)}.node:hover rect,.node:focus rect{stroke:var(--vscode-focusBorder);stroke-width:2.5}.title{fill:var(--vscode-foreground);font-size:14px;font-weight:600}.subtitle,.summary,.edge-label{fill:var(--vscode-descriptionForeground);font-size:11px}.summary{font-size:12px}.edge{fill:none;stroke:var(--vscode-foreground);stroke-width:1.5}.edge.implementation,.edge.dependency{stroke-dasharray:7 5}.edge-group{cursor:pointer}.edge-group:hover .edge,.edge-group:focus .edge{stroke:var(--vscode-focusBorder);stroke-width:3}.edge-hit{fill:none;stroke:transparent;stroke-width:14;pointer-events:stroke}.edge-label{paint-order:stroke;stroke:var(--vscode-editor-background);stroke-width:5;stroke-linejoin:round;cursor:pointer}.empty{fill:var(--vscode-descriptionForeground);font-size:14px}#edge-tooltip{position:fixed;z-index:10;max-width:360px;padding:7px 9px;border:1px solid var(--vscode-widget-border);background:var(--vscode-editorHoverWidget-background);color:var(--vscode-editorHoverWidget-foreground);box-shadow:0 2px 8px var(--vscode-widget-shadow);font-size:12px;line-height:1.4;pointer-events:none;white-space:pre-wrap}
  </style></head><body><header><button id="back" title="返回上一视图" aria-label="返回上一视图">&#8592;</button><nav id="breadcrumbs"></nav><span class="meta"></span></header><div id="notice" class="notice" hidden></div><div id="viewport"><svg id="graph" role="img" aria-label="分层类 UML 认知图"></svg></div><div id="edge-tooltip" role="tooltip" hidden></div><script>
  const vscode=acquireVsCodeApi(),payload=${data},svg=document.getElementById('graph'),NS='http://www.w3.org/2000/svg';
  const make=(name,attrs,parent=svg)=>{const el=document.createElementNS(NS,name);for(const [key,value] of Object.entries(attrs||{}))el.setAttribute(key,String(value));parent.appendChild(el);return el};
  document.querySelector('.meta').textContent='revision '+payload.revision.slice(0,10);document.getElementById('back').onclick=()=>vscode.postMessage({command:'back'});
  const nav=document.getElementById('breadcrumbs');payload.breadcrumbs.forEach((crumb,index)=>{if(index)nav.append(' / ');const button=document.createElement('button');button.className='crumb';button.textContent=crumb.label;button.title=crumb.label;button.onclick=()=>vscode.postMessage({command:'navigate',id:crumb.id});nav.append(button)});
  if(payload.notice){const notice=document.getElementById('notice');notice.hidden=false;notice.textContent=payload.notice}svg.setAttribute('viewBox','0 0 '+payload.graph.width+' '+payload.graph.height);svg.setAttribute('width',payload.graph.width);svg.setAttribute('height',payload.graph.height);
  const defs=make('defs',{});for(const [id,filled] of [['arrow',true],['triangle',false]]){const marker=make('marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:8,markerHeight:8,orient:'auto-start-reverse'},defs);make('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:filled?'context-stroke':'var(--vscode-editor-background)',stroke:'context-stroke'},marker)}
  const tooltip=document.getElementById('edge-tooltip');const showEdgeTooltip=(edge,event)=>{tooltip.textContent=(edge.label||edge.kind)+'\\n'+edge.kind+' · '+edge.status+' · '+edge.evidenceCount+' evidence';tooltip.hidden=false;tooltip.style.left=Math.min(event.clientX+12,window.innerWidth-370)+'px';tooltip.style.top=Math.min(event.clientY+12,window.innerHeight-90)+'px'};const hideEdgeTooltip=()=>{tooltip.hidden=true};const openEvidence=edge=>vscode.postMessage({command:'evidence',id:edge.id});
  for(const edge of payload.graph.edges){if(edge.points.length<2)continue;const d=edge.points.map((point,index)=>(index?'L':'M')+' '+point.x+' '+point.y).join(' '),group=make('g',{class:'edge-group',tabindex:0,'data-id':edge.id,'aria-label':(edge.label||edge.kind)+', '+edge.evidenceCount+' evidence'});make('path',{d,class:'edge '+edge.kind,'marker-end':edge.kind==='inheritance'||edge.kind==='implementation'?'url(#triangle)':'url(#arrow)'},group);make('path',{d,class:'edge-hit'},group);const middle=edge.points[Math.floor(edge.points.length/2)];const label=make('text',{x:middle.x,y:middle.y-7,class:'edge-label','text-anchor':'middle'},group);label.textContent=(edge.label||edge.kind).slice(0,42);group.onclick=()=>openEvidence(edge);group.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openEvidence(edge)}};group.onpointerenter=event=>showEdgeTooltip(edge,event);group.onpointermove=event=>showEdgeTooltip(edge,event);group.onpointerleave=hideEdgeTooltip;}
  for(const node of payload.graph.nodes){const group=make('g',{class:'node '+node.kind,transform:'translate('+(node.x-node.width/2)+' '+(node.y-node.height/2)+')',tabindex:0,'data-id':node.id});make('rect',{width:node.width,height:node.height,rx:node.kind==='domain'?3:0},group);const title=make('text',{x:12,y:24,class:'title'},group);title.textContent=node.title.length>28?node.title.slice(0,27)+'…':node.title;const subtitle=make('text',{x:12,y:43,class:'subtitle'},group);subtitle.textContent='«'+node.subtitle+'» · '+node.status;const summary=make('text',{x:12,y:66,class:'summary'},group);summary.textContent=node.summary.length>31?node.summary.slice(0,30)+'…':node.summary;const full=make('title',{},group);full.textContent=node.title+'\\n'+node.summary;group.onclick=()=>vscode.postMessage({command:'navigate',id:node.id});group.ondblclick=event=>{event.stopPropagation();vscode.postMessage({command:node.kind==='class'?'open':'navigate',id:node.id})};}
  if(!payload.graph.nodes.length){const empty=make('text',{x:32,y:48,class:'empty'});empty.textContent='当前层级没有可展示的认知节点。'}
  </script></body></html>`;
}
