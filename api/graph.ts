// Powiązania: indeks wskaźników, top 5 powiązanych rekordów, ego-graf i graf kampanii.

import type { Finding, Graph, GraphEdge, GraphEdgeType, GraphNode, Indicator, RelatedFinding } from '../frontend/src/api/types';
import type { World } from './real';

const round3 = (x: number) => Math.round(x * 1000) / 1000;

export const MAX_GRAPH_NODES = 300;
const STOPLIST_DF = 60;

export const indKey = (i: Indicator) => `${i.type}:${i.value}`;

export function indexFinding(world: World, f: Finding): void {
  for (const ind of f.indicators) {
    const k = indKey(ind);
    let set = world.index.get(k);
    if (!set) {
      set = new Set();
      world.index.set(k, set);
    }
    set.add(f.id);
  }
}

function indicatorDetail(ind: Indicator): string {
  switch (ind.type) {
    case 'phone':
      return `wspólny numer telefonu ${ind.value}`;
    case 'telegram':
      return `wspólny kanał Telegram ${ind.value}`;
    case 'whatsapp':
      return `wspólny kontakt WhatsApp ${ind.value}`;
    case 'domain':
      return `wspólna domena ${ind.value}`;
    case 'brand':
      return `ta sama marka: ${ind.value}`;
    case 'person':
      return `ten sam wizerunek: ${ind.value}`;
    case 'email':
      return `wspólny e-mail ${ind.value}`;
    case 'wallet':
      return `wspólny portfel ${ind.value}`;
    case 'iban':
      return `wspólny rachunek ${ind.value}`;
    default:
      return `wspólny wskaźnik ${ind.value}`;
  }
}

export function computeRelated(world: World, f: Finding): RelatedFinding[] {
  const best = new Map<string, RelatedFinding>();
  const consider = (id: string, reason: RelatedFinding['reason'], detail: string, score: number) => {
    if (id === f.id || !world.byId.has(id)) return;
    const prev = best.get(id);
    if (!prev || prev.score < score) best.set(id, { findingId: id, reason, detail, score: round3(score) });
  };

  for (const ind of f.indicators) {
    const ids = world.index.get(indKey(ind));
    if (!ids || ids.size < 2) continue;
    if (ind.type === 'author') {
      for (const id of ids) consider(id, 'SAME_AUTHOR', `ten sam autor ${ind.value}`, 0.62);
      continue;
    }
    if (ids.size > STOPLIST_DF) continue;
    const score = 0.55 + 0.4 / Math.log2(1 + ids.size);
    for (const id of ids) {
      const other = world.byId.get(id);
      if (ind.type === 'domain' && other?.kind === 'page' && f.kind !== 'page') {
        consider(id, 'REDIRECTS_TO', `link prowadzi do ${ind.value}`, Math.min(0.98, score + 0.05));
      } else {
        consider(id, 'SHARES_INDICATOR', indicatorDetail(ind), Math.min(0.95, score));
      }
    }
  }

  return [...best.values()].sort((a, b) => b.score - a.score || a.findingId.localeCompare(b.findingId)).slice(0, 5);
}

class GraphBuilder {
  nodes = new Map<string, GraphNode>();
  edges = new Map<string, GraphEdge>();

  constructor(private world: World) {}

  get full(): boolean {
    return this.nodes.size >= MAX_GRAPH_NODES;
  }

  addFinding(f: Finding): boolean {
    if (this.nodes.has(f.id)) return true;
    if (this.full) return false;
    this.nodes.set(f.id, { id: f.id, kind: 'finding', label: f.author.handle, riskScore: f.riskScore });
    return true;
  }

  addIndicator(ind: Indicator): boolean {
    const id = indKey(ind);
    if (this.nodes.has(id)) return true;
    if (this.full) return false;
    this.nodes.set(id, { id, kind: ind.type, label: ind.value });
    return true;
  }

  addEdge(source: string, target: string, type: GraphEdgeType, weight: number): void {
    if (!this.nodes.has(source) || !this.nodes.has(target) || source === target) return;
    const [a, b] = source < target ? [source, target] : [target, source];
    const key = `${a}|${b}|${type}`;
    const prev = this.edges.get(key);
    if (!prev || prev.weight < weight) this.edges.set(key, { source, target, type, weight: round3(weight) });
  }

  /** Krawędzie rekord–wskaźnik i rekord–rekord między węzłami już obecnymi w grafie. */
  connect(): void {
    for (const node of [...this.nodes.values()]) {
      if (node.kind !== 'finding') continue;
      const f = this.world.byId.get(node.id);
      if (!f) continue;
      for (const ind of f.indicators) this.addEdge(f.id, indKey(ind), 'HAS_INDICATOR', 1);
      for (const r of f.related) {
        if (r.reason === 'SHARES_INDICATOR') continue; // widać to przez węzeł wskaźnika
        this.addEdge(f.id, r.findingId, r.reason, r.score);
      }
    }
  }

  build(): Graph {
    return limitGraph({ nodes: [...this.nodes.values()], edges: [...this.edges.values()] }, MAX_GRAPH_NODES);
  }
}

/** Czy wskaźnik warto pokazać jako węzeł (autor tylko, gdy łączy kilka rekordów). */
function showIndicator(world: World, ind: Indicator): boolean {
  if (ind.type !== 'author') return true;
  return (world.index.get(indKey(ind))?.size ?? 0) > 1;
}

export function egoGraph(world: World, findingId: string, depth: 1 | 2): Graph | null {
  const root = world.byId.get(findingId);
  if (!root) return null;
  const g = new GraphBuilder(world);
  g.addFinding(root);
  let frontier: string[] = [root.id];
  for (let d = 0; d < depth && !g.full; d++) {
    const next: string[] = [];
    for (const nodeId of frontier) {
      const f = world.byId.get(nodeId);
      if (f) {
        for (const ind of f.indicators) {
          if (showIndicator(world, ind) && !g.nodes.has(indKey(ind)) && g.addIndicator(ind)) next.push(indKey(ind));
        }
        for (const r of f.related) {
          const other = world.byId.get(r.findingId);
          if (other && !g.nodes.has(other.id) && g.addFinding(other)) next.push(other.id);
        }
      } else {
        // węzeł-wskaźnik: dołącz rekordy, które go zawierają
        const ids = [...(world.index.get(nodeId) ?? [])].slice(0, 40);
        for (const id of ids) {
          const other = world.byId.get(id);
          if (other && !g.nodes.has(id) && g.addFinding(other)) next.push(id);
        }
      }
    }
    frontier = next;
  }
  g.connect();
  return g.build();
}

/**
 * Powyżej limitu węzłów: wskaźniki o stopniu 1 agregowane per typ w jeden węzeł „+N”,
 * a jeśli to nie wystarczy, odrzucane są rekordy z najniższym wynikiem ryzyka.
 */
export function limitGraph(graph: Graph, max: number): Graph {
  if (graph.nodes.length <= max) return graph;
  const degree = new Map<string, number>();
  for (const e of graph.edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  const remap = new Map<string, string>();
  const aggCount = new Map<string, number>();
  const nodes: GraphNode[] = [];
  for (const n of graph.nodes) {
    if (n.kind !== 'finding' && (degree.get(n.id) ?? 0) <= 1) {
      const aggId = `agg:${n.kind}`;
      remap.set(n.id, aggId);
      aggCount.set(aggId, (aggCount.get(aggId) ?? 0) + 1);
    } else nodes.push(n);
  }
  for (const [aggId, count] of aggCount) {
    nodes.push({ id: aggId, kind: aggId.slice(4) as GraphNode['kind'], label: `+${count}` });
  }
  const seen = new Set<string>();
  let edges: GraphEdge[] = [];
  for (const e of graph.edges) {
    const source = remap.get(e.source) ?? e.source;
    const target = remap.get(e.target) ?? e.target;
    const key = `${source}|${target}|${e.type}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ ...e, source, target });
  }
  let kept = nodes;
  if (kept.length > max) {
    const findings = kept.filter((n) => n.kind === 'finding').sort((a, b) => (b.riskScore ?? 0) - (a.riskScore ?? 0));
    const others = kept.filter((n) => n.kind !== 'finding');
    const room = Math.max(0, max - others.length);
    kept = [...findings.slice(0, room), ...others].slice(0, max);
    const ids = new Set(kept.map((n) => n.id));
    edges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  }
  return { nodes: kept, edges };
}
