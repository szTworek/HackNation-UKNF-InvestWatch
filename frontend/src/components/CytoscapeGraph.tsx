import { Box, Group, Text } from '@mantine/core';
import {
  IconAt,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBuildingBank,
  IconLink,
  IconMail,
  IconPhone,
  IconTag,
  IconUserStar,
  IconWallet,
  IconWorld,
  type Icon,
} from '@tabler/icons-react';
import cytoscape, { type Core, type ElementDefinition, type EventObject } from 'cytoscape';
import { useEffect, useRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { Graph, GraphNode, IndicatorType } from '../api/types';

const ICONS: Record<IndicatorType, Icon> = {
  domain: IconWorld,
  url: IconLink,
  phone: IconPhone,
  telegram: IconBrandTelegram,
  whatsapp: IconBrandWhatsapp,
  email: IconMail,
  wallet: IconWallet,
  iban: IconBuildingBank,
  brand: IconTag,
  person: IconUserStar,
  author: IconAt,
};

const iconCache = new Map<string, string>();
function iconUri(kind: IndicatorType): string {
  let uri = iconCache.get(kind);
  if (!uri) {
    const I = ICONS[kind];
    const svg = renderToStaticMarkup(<I size={24} stroke={1.75} color="#3d4752" />);
    uri = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
    iconCache.set(kind, uri);
  }
  return uri;
}

function scamClass(p: number | undefined): string {
  if (p === undefined) return '';
  if (p >= 0.6) return 'scam-high';
  if (p >= 0.3) return 'scam-mid';
  return 'scam-low';
}

function toElement(n: GraphNode): ElementDefinition {
  const isFinding = n.kind === 'finding';
  return {
    group: 'nodes',
    data: { id: n.id, label: n.label, kind: n.kind, ...(isFinding ? {} : { icon: iconUri(n.kind as IndicatorType) }) },
    classes: isFinding ? `finding ${scamClass(n.riskScore)}` : 'indicator',
  };
}

function toElements(graph: Graph): ElementDefinition[] {
  const ids = new Set(graph.nodes.map((n) => n.id));
  return [
    ...graph.nodes.map(toElement),
    ...graph.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({
        group: 'edges' as const,
        data: { id: `${e.source}|${e.target}|${e.type}`, source: e.source, target: e.target, type: e.type, weight: e.weight },
        classes: e.type === 'HAS_INDICATOR' ? '' : e.type.toLowerCase(),
      })),
  ];
}

const STYLE: cytoscape.StylesheetJson = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': 9,
      color: '#3d4752',
      'text-valign': 'bottom',
      'text-margin-y': 3,
      'text-max-width': '90px',
      'text-wrap': 'ellipsis',
      'min-zoomed-font-size': 7,
    },
  },
  { selector: 'node.finding', style: { width: 18, height: 18, 'background-color': '#adb5bd', 'border-width': 1, 'border-color': '#ffffff' } },
  { selector: 'node.scam-high', style: { 'background-color': '#e03131' } },
  { selector: 'node.scam-mid', style: { 'background-color': '#fd7e14' } },
  { selector: 'node.scam-low', style: { 'background-color': '#5392de' } },
  {
    selector: 'node.indicator',
    style: {
      shape: 'round-rectangle',
      width: 24,
      height: 24,
      'background-color': '#f3f5f8',
      'border-width': 1,
      'border-color': '#c9cfd6',
      'background-image': 'data(icon)',
      'background-fit': 'none',
      'background-width': '16px',
      'background-height': '16px',
    },
  },
  { selector: 'edge', style: { width: 1, 'line-color': '#d0d5dc', 'curve-style': 'haystack', opacity: 0.8 } },
  { selector: 'edge.similar_text', style: { 'line-color': '#e599f7', width: 1.5 } },
  { selector: 'edge.impersonates', style: { 'line-color': '#ff8787', width: 1.5 } },
  { selector: 'edge.redirects_to', style: { 'line-color': '#5392de', width: 1.5 } },
  { selector: 'edge.same_author', style: { 'line-color': '#adb5bd', 'line-style': 'dashed' } },
  { selector: '.faded', style: { opacity: 0.12 } },
  { selector: 'node.highlight', style: { 'border-width': 3, 'border-color': '#0f6cbd', width: 26, height: 26, 'font-weight': 'bold' } },
  { selector: 'node.fresh', style: { 'border-width': 4, 'border-color': '#fab005' } },
];

interface Props {
  graph: Graph;
  onNodeClick?: (node: GraphNode) => void;
  highlightId?: string;
  height?: number;
}

/** Cienki wrapper Cytoscape.js: layout cose przy pierwszym renderze, potem przyrostowe dodawanie węzłów z animacją. */
export function CytoscapeGraph({ graph, onNodeClick, highlightId, height = 480 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const nodesRef = useRef(new Map<string, GraphNode>());
  const clickRef = useRef(onNodeClick);
  useEffect(() => {
    clickRef.current = onNodeClick;
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      style: STYLE,
      minZoom: 0.2,
      maxZoom: 3,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;
    cy.on('mouseover', 'node', (e: EventObject) => {
      const hood = e.target.closedNeighborhood();
      cy.elements().not(hood).addClass('faded');
    });
    cy.on('mouseout', 'node', () => cy.elements().removeClass('faded'));
    cy.on('tap', 'node', (e: EventObject) => {
      const n = nodesRef.current.get(e.target.id());
      if (n) clickRef.current?.(n);
    });
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    nodesRef.current = new Map(graph.nodes.map((n) => [n.id, n]));
    const next = toElements(graph);
    const nextIds = new Set(next.map((e) => e.data.id as string));
    const initial = cy.elements().length === 0;

    cy.batch(() => {
      cy.elements().filter((el) => !nextIds.has(el.id())).remove();
    });
    const added = next.filter((e) => cy.getElementById(e.data.id as string).empty());
    const addedNodes = added.filter((e) => e.group === 'nodes');
    cy.add(added);
    // klasy węzłów mogą się zmienić (np. ryzyko po ponownej ocenie)
    for (const n of graph.nodes) {
      const el = cy.getElementById(n.id);
      if (n.kind === 'finding') el.classes(`finding ${scamClass(n.riskScore)}${n.id === highlightId ? ' highlight' : ''}`);
    }

    if (initial || addedNodes.length > 10) {
      cy.layout({ name: 'cose', animate: false, padding: 24, nodeRepulsion: () => 9000, idealEdgeLength: () => 50, randomize: true } as cytoscape.LayoutOptions).run();
      cy.fit(undefined, 24);
    } else if (addedNodes.length) {
      // nowe węzły obok sąsiadów + krótki błysk
      for (const def of addedNodes) {
        const node = cy.getElementById(def.data.id as string);
        const anchor = node
          .neighborhood()
          .nodes()
          .filter((n) => !addedNodes.some((a) => a.data.id === n.id()));
        const base = anchor.length ? anchor[0].position() : { x: cy.width() / 2, y: cy.height() / 2 };
        node.position({ x: base.x + (Math.random() - 0.5) * 80, y: base.y + (Math.random() - 0.5) * 80 });
        node.addClass('fresh');
        node.style('opacity', 0);
        node.animate({ style: { opacity: 1 } }, { duration: 500 });
        window.setTimeout(() => node.removeClass('fresh'), 4000);
      }
    }
  }, [graph, highlightId]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass('highlight');
    if (highlightId) cy.getElementById(highlightId).addClass('highlight');
  }, [highlightId, graph]);

  return (
    <Box>
      <Box
        ref={containerRef}
        h={height}
        style={{ border: '1px solid var(--iw-border)', borderRadius: 4, background: '#ffffff' }}
        role="img"
        aria-label={`Graf powiązań: ${graph.nodes.length} węzłów, ${graph.edges.length} krawędzi`}
      />
      <Group gap="md" mt={6}>
        {[
          ['#e03131', 'ryzyko ≥ 0,6'],
          ['#fd7e14', '0,3–0,6'],
          ['#5392de', '< 0,3'],
        ].map(([color, label]) => (
          <Group key={label} gap={4}>
            <Box w={10} h={10} style={{ borderRadius: '50%', background: color }} aria-hidden />
            <Text size="xs" c="dimmed">
              {label}
            </Text>
          </Group>
        ))}
        <Text size="xs" c="dimmed">
          Kwadraty: wskaźniki
        </Text>
      </Group>
    </Box>
  );
}
