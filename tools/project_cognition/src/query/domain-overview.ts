import { FunctionalDomain, Membership, ProjectSnapshot } from "../domain/model.js";

export const UNCLASSIFIED_DOMAIN_ID = "virtual:unclassified";

export interface DomainOverview {
  snapshotId: string;
  codeRevision: string;
  domains: FunctionalDomain[];
  memberships: Membership[];
  symbols: ProjectSnapshot["symbols"];
}

/** Projects persisted cognition plus a non-persistent entry for unassigned symbols. */
export function buildDomainOverview(snapshot: ProjectSnapshot, requestedDomainId?: string): DomainOverview {
  const assignedIds = new Set(snapshot.memberships.map(item => item.symbolId));
  const unassigned = snapshot.symbols.filter(item => !assignedIds.has(item.id));
  const virtualDomain: FunctionalDomain | undefined = unassigned.length ? {
    id: UNCLASSIFIED_DOMAIN_ID,
    projectId: snapshot.projectId,
    name: "待归类",
    summary: "已写入认知但尚未由人工确认功能归属的符号。",
    status: "proposed",
    source: "ai",
    locked: false
  } : undefined;
  const virtualMemberships: Membership[] = unassigned.map(symbol => ({ id: `virtual:unclassified:${symbol.id}`, domainId: UNCLASSIFIED_DOMAIN_ID, symbolId: symbol.id, type: "reference", status: "proposed", source: "ai", locked: false }));
  const domains = virtualDomain ? [...snapshot.domains, virtualDomain] : [...snapshot.domains];
  const memberships = [...snapshot.memberships, ...virtualMemberships];
  if (!requestedDomainId) return { snapshotId: snapshot.id, codeRevision: snapshot.codeRevision, domains, memberships, symbols: [...snapshot.symbols] };
  const domainIds = new Set(domains.filter(item => item.id === requestedDomainId || item.parentId === requestedDomainId).map(item => item.id));
  const visibleMemberships = memberships.filter(item => domainIds.has(item.domainId));
  const symbolIds = new Set(visibleMemberships.map(item => item.symbolId));
  return { snapshotId: snapshot.id, codeRevision: snapshot.codeRevision, domains: domains.filter(item => domainIds.has(item.id)), memberships: visibleMemberships, symbols: snapshot.symbols.filter(item => symbolIds.has(item.id)) };
}
