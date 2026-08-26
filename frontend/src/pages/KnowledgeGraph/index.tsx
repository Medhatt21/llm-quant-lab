import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import ForceGraph2D from 'react-force-graph-2d';
import {
  Search,
  Filter,
  ZoomIn,
  ZoomOut,
  Maximize2,
  X,
  Loader2,
  Database,
  Cpu,
  Layers,
  BookOpen,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  Info,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import clsx from 'clsx';
import Header from '../../components/Layout/Header';
import { getKnowledgeGraph, getKnowledgeGraphSeedStatus, seedKnowledgeGraph } from '../../api/client';

// ─── Color mapping for node types ────────────────────────────────────
const NODE_COLORS: Record<string, string> = {
  algorithm: '#3b82f6',   // blue-500
  scheme: '#10b981',      // emerald-500
  data_type: '#f59e0b',   // amber-500
  hardware: '#ef4444',    // red-500
};

const NODE_BG_COLORS: Record<string, string> = {
  algorithm: '#eff6ff',
  scheme: '#ecfdf5',
  data_type: '#fffbeb',
  hardware: '#fef2f2',
};

const NODE_TYPE_LABELS: Record<string, string> = {
  algorithm: 'Algorithms',
  scheme: 'Quant Schemes',
  data_type: 'Data Types',
  hardware: 'Hardware',
};

const NODE_TYPE_ICONS: Record<string, typeof Cpu> = {
  algorithm: BookOpen,
  scheme: Layers,
  data_type: Database,
  hardware: Cpu,
};

const EDGE_TYPE_LABELS: Record<string, { label: string; desc: string }> = {
  implements: { label: 'implements', desc: 'Algorithm implements a quantization scheme' },
  uses: { label: 'uses', desc: 'Algorithm/Scheme uses a data type' },
  supports: { label: 'supports', desc: 'Hardware natively supports a data type or scheme' },
};

const EDGE_COLORS: Record<string, string> = {
  implements: '#93c5fd',
  uses: '#fcd34d',
  supports: '#fca5a5',
};

// ─── Hierarchical sub-categories for drill-through filtering ────────
// Maps node_type -> { groupLabel -> list of category values }
const HARDWARE_GROUPS: Record<string, { label: string; categories: string[] }> = {
  nvidia_blackwell: { label: 'NVIDIA Blackwell', categories: ['nvidia_dc'] },
  nvidia_hopper: { label: 'NVIDIA Hopper', categories: ['nvidia_dc'] },
  nvidia_ampere: { label: 'NVIDIA Ampere', categories: ['nvidia_dc'] },
  nvidia_ada: { label: 'NVIDIA Ada Lovelace', categories: ['nvidia_dc'] },
  nvidia_consumer: { label: 'NVIDIA Consumer', categories: ['nvidia_consumer'] },
  amd_dc: { label: 'AMD Datacenter (CDNA)', categories: ['amd_dc'] },
  amd_consumer: { label: 'AMD Consumer (RDNA)', categories: ['amd_consumer'] },
  apple: { label: 'Apple Silicon', categories: ['apple'] },
  npu: { label: 'NPU / Edge', categories: ['npu'] },
  other_accel: { label: 'Other Accelerators', categories: ['tpu', 'intel_dc'] },
};

// Arch tag to group ID mapping — used to match individual hardware nodes to groups
const ARCH_TO_GROUP: Record<string, string> = {
  'Blackwell': 'nvidia_blackwell',
  'Hopper': 'nvidia_hopper',
  'Ampere': 'nvidia_ampere',
  'Ada Lovelace': 'nvidia_ada',
  'CDNA3': 'amd_dc',
  'CDNA4': 'amd_dc',
  'RDNA3': 'amd_consumer',
  'M4': 'apple',
  'Hexagon': 'npu',
  'Meteor Lake': 'npu',
  'APU': 'npu',
  'TPU v5e': 'other_accel',
  'Gaudi 3': 'other_accel',
};

const ALGO_GROUPS: Record<string, { label: string; categories: string[] }> = {
  ptq_weight: { label: 'PTQ Weight-only', categories: ['ptq_weight'] },
  ptq_wa: { label: 'PTQ W+A', categories: ['ptq_wa'] },
  ptq_mixed: { label: 'PTQ Mixed/Advanced', categories: ['ptq_mixed'] },
  qat: { label: 'QAT', categories: ['qat'] },
};

const SCHEME_GROUPS: Record<string, { label: string; categories: string[] }> = {
  weight_only: { label: 'Weight-only', categories: ['weight_only'] },
  w_a: { label: 'Weight + Activation', categories: ['w_a'] },
  fp8_scheme: { label: 'FP8 Schemes', categories: ['fp8_scheme'] },
  mixed: { label: 'Mixed / Special', categories: ['mixed'] },
};

const DATATYPE_GROUPS: Record<string, { label: string; categories: string[] }> = {
  traditional: { label: 'Traditional (FP32/16, INT8)', categories: ['traditional'] },
  fp8: { label: 'FP8 Variants', categories: ['fp8'] },
  low_precision: { label: 'Low Precision (FP4/6)', categories: ['low_precision'] },
  special: { label: 'Special (NF4, Ternary)', categories: ['special'] },
  mx: { label: 'MX Formats', categories: ['mx'] },
};

type SubGroupMap = Record<string, { label: string; categories: string[] }>;

// ─── Pre-defined subgraph views ──────────────────────────────────────
const PRESET_VIEWS = [
  { label: 'Full Graph', filter: null, category: 'general' },
  { label: 'What runs on MI300X?', filter: 'hw_mi300x', category: 'hardware' },
  { label: 'NVIDIA H100 ecosystem', filter: 'hw_h100', category: 'hardware' },
  { label: 'Blackwell B200', filter: 'hw_b200', category: 'hardware' },
  { label: 'GPTQ ecosystem', filter: 'algo_gptq', category: 'algorithm' },
  { label: 'AWQ ecosystem', filter: 'algo_awq', category: 'algorithm' },
  { label: 'SmoothQuant flow', filter: 'algo_smoothquant', category: 'algorithm' },
  { label: '4-bit landscape', filter: '4bit', category: 'precision' },
  { label: '8-bit landscape', filter: '8bit', category: 'precision' },
  { label: '2-bit / ternary', filter: '2bit', category: 'precision' },
  { label: 'MX formats', filter: 'mx', category: 'format' },
  { label: 'FP8 ecosystem', filter: 'fp8', category: 'format' },
  { label: 'Weight-only schemes', filter: 'weight_only', category: 'scheme' },
  { label: 'W+A quantization', filter: 'w_a', category: 'scheme' },
];

interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  category: string;
  metadata_json: Record<string, unknown>;
  color: string;
  val: number;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  edge_type: string;
  strength: number;
}

export default function KnowledgeGraph() {
  const graphRef = useRef<any>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(['algorithm', 'scheme', 'data_type', 'hardware'])
  );
  const [activeEdgeFilters, setActiveEdgeFilters] = useState<Set<string>>(
    new Set(['implements', 'uses', 'supports'])
  );
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<string>>(new Set());
  const [presetView, setPresetView] = useState<string | null>(null);
  const [legendExpanded, setLegendExpanded] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarSection, setSidebarSection] = useState<Record<string, boolean>>({
    types: true, edges: false, views: true,
  });
  // Track which node type's sub-group drill-through is expanded
  const [expandedType, setExpandedType] = useState<string | null>(null);
  // Track excluded sub-groups (e.g. { hardware: Set(['nvidia_blackwell']) })
  const [excludedSubGroups, setExcludedSubGroups] = useState<Record<string, Set<string>>>({});
  // Smart filter: when a node is selected, show its reachable subgraph
  const [smartFilter, setSmartFilter] = useState<string | null>(null);

  // Sub-group map for each node type
  const getSubGroupMap = useCallback((nodeType: string): SubGroupMap | null => {
    switch (nodeType) {
      case 'hardware': return HARDWARE_GROUPS;
      case 'algorithm': return ALGO_GROUPS;
      case 'scheme': return SCHEME_GROUPS;
      case 'data_type': return DATATYPE_GROUPS;
      default: return null;
    }
  }, []);

  // Determine which sub-group ID a node belongs to
  const getNodeSubGroup = useCallback((node: { node_type: string; category: string; metadata_json?: Record<string, unknown> }): string | null => {
    if (node.node_type === 'hardware') {
      // Use arch field from metadata to get precise group
      const arch = node.metadata_json?.arch as string | undefined;
      if (arch && ARCH_TO_GROUP[arch]) return ARCH_TO_GROUP[arch];
      // Fallback to category matching
      for (const [gid, g] of Object.entries(HARDWARE_GROUPS)) {
        if (g.categories.includes(node.category)) return gid;
      }
    } else {
      const groups = getSubGroupMap(node.node_type);
      if (groups) {
        for (const [gid, g] of Object.entries(groups)) {
          if (g.categories.includes(node.category)) return gid;
        }
      }
    }
    return null;
  }, [getSubGroupMap]);

  const toggleSubGroup = useCallback((nodeType: string, groupId: string) => {
    setExcludedSubGroups((prev) => {
      const next = { ...prev };
      const set = new Set(next[nodeType] || []);
      if (set.has(groupId)) set.delete(groupId);
      else set.add(groupId);
      next[nodeType] = set;
      return next;
    });
  }, []);

  // Check seed status
  const { data: seedStatus } = useQuery({
    queryKey: ['knowledge-graph-seed-status'],
    queryFn: getKnowledgeGraphSeedStatus,
  });

  // Seed mutation
  const seedMutation = useMutation({
    mutationFn: seedKnowledgeGraph,
    onSuccess: () => { graphQuery.refetch(); },
  });

  // Fetch graph data
  const graphQuery = useQuery({
    queryKey: ['knowledge-graph'],
    queryFn: () => getKnowledgeGraph(),
    enabled: seedStatus?.seeded !== false,
  });

  // Build adjacency for neighborhood highlighting
  const adjacencyMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    if (!graphQuery.data) return map;
    for (const edge of graphQuery.data.edges) {
      if (!map.has(edge.source_id)) map.set(edge.source_id, new Set());
      if (!map.has(edge.target_id)) map.set(edge.target_id, new Set());
      map.get(edge.source_id)!.add(edge.target_id);
      map.get(edge.target_id)!.add(edge.source_id);
    }
    return map;
  }, [graphQuery.data]);

  // Edge type map: nodeA-nodeB -> edge_type
  const edgeTypeMap = useMemo(() => {
    const map = new Map<string, string>();
    if (!graphQuery.data) return map;
    for (const edge of graphQuery.data.edges) {
      map.set(`${edge.source_id}-${edge.target_id}`, edge.edge_type);
      map.set(`${edge.target_id}-${edge.source_id}`, edge.edge_type);
    }
    return map;
  }, [graphQuery.data]);

  // Connection count per node
  const connectionCount = useMemo(() => {
    const counts = new Map<string, number>();
    if (!graphQuery.data) return counts;
    for (const edge of graphQuery.data.edges) {
      counts.set(edge.source_id, (counts.get(edge.source_id) || 0) + 1);
      counts.set(edge.target_id, (counts.get(edge.target_id) || 0) + 1);
    }
    return counts;
  }, [graphQuery.data]);

  // Smart filter: BFS from a selected node across all edge types,
  // collecting reachable nodes up to depth 3
  const smartFilterIds = useMemo(() => {
    if (!smartFilter || !graphQuery.data) return null;
    const visited = new Set<string>([smartFilter]);
    let frontier = [smartFilter];
    for (let depth = 0; depth < 3 && frontier.length > 0; depth++) {
      const next: string[] = [];
      for (const nid of frontier) {
        const neighbors = adjacencyMap.get(nid);
        if (neighbors) {
          for (const neighbor of neighbors) {
            if (!visited.has(neighbor)) {
              visited.add(neighbor);
              next.push(neighbor);
            }
          }
        }
      }
      frontier = next;
    }
    return visited;
  }, [smartFilter, adjacencyMap, graphQuery.data]);

  // Transform data for react-force-graph
  const graphData = useMemo(() => {
    if (!graphQuery.data) return { nodes: [], links: [] };
    const { nodes: rawNodes, edges: rawEdges } = graphQuery.data;

    // Apply type filter
    let filteredNodes = rawNodes.filter((n) => activeFilters.has(n.node_type));

    // Apply sub-group drill-through filter
    filteredNodes = filteredNodes.filter((n) => {
      const excluded = excludedSubGroups[n.node_type];
      if (!excluded || excluded.size === 0) return true;
      const sg = getNodeSubGroup(n);
      return sg ? !excluded.has(sg) : true;
    });

    // Apply smart filter (overrides preset)
    if (smartFilterIds) {
      filteredNodes = filteredNodes.filter((n) => smartFilterIds.has(n.id));
    } else if (presetView) {
      // Apply preset view
      if (presetView === 'mx') {
        const seedIds = new Set(rawNodes.filter((n) => n.category === 'mx').map((n) => n.id));
        const neighborIds = new Set<string>();
        for (const id of seedIds) {
          const nb = adjacencyMap.get(id);
          if (nb) nb.forEach((nid) => neighborIds.add(nid));
        }
        filteredNodes = filteredNodes.filter((n) => seedIds.has(n.id) || neighborIds.has(n.id));
      } else if (presetView === 'fp8') {
        const seedIds = new Set(rawNodes.filter((n) => n.label.includes('FP8') || n.label.includes('MXFP8')).map((n) => n.id));
        const neighborIds = new Set<string>();
        for (const id of seedIds) {
          const nb = adjacencyMap.get(id);
          if (nb) nb.forEach((nid) => neighborIds.add(nid));
        }
        filteredNodes = filteredNodes.filter((n) => seedIds.has(n.id) || neighborIds.has(n.id));
      } else if (presetView === '4bit' || presetView === '8bit' || presetView === '2bit') {
        const targetBits = presetView === '4bit' ? [4] : presetView === '8bit' ? [8] : [1, 1.58, 2];
        const seedIds = new Set(
          rawNodes.filter((n) => {
            const bits = n.metadata_json?.bits;
            if (typeof bits === 'number' && targetBits.includes(bits)) return true;
            if (presetView === '4bit' && (n.label.includes('W4') || n.label.includes('4-bit') || n.label.includes('INT4'))) return true;
            if (presetView === '8bit' && (n.label.includes('W8') || n.label.includes('8-bit') || n.label.includes('INT8'))) return true;
            if (presetView === '2bit' && (n.label.includes('W2') || n.label.includes('2-bit') || n.label.includes('ternary') || n.label.includes('Ternary') || n.label.includes('binary') || n.label.includes('Binary'))) return true;
            return false;
          }).map((n) => n.id)
        );
        const neighborIds = new Set<string>();
        for (const id of seedIds) {
          const nb = adjacencyMap.get(id);
          if (nb) nb.forEach((nid) => neighborIds.add(nid));
        }
        filteredNodes = filteredNodes.filter((n) => seedIds.has(n.id) || neighborIds.has(n.id));
      } else if (presetView === 'weight_only') {
        const seedIds = new Set(rawNodes.filter((n) => n.category === 'weight_only' || n.category === 'ptq_weight').map((n) => n.id));
        const neighborIds = new Set<string>();
        for (const id of seedIds) {
          const nb = adjacencyMap.get(id);
          if (nb) nb.forEach((nid) => neighborIds.add(nid));
        }
        filteredNodes = filteredNodes.filter((n) => seedIds.has(n.id) || neighborIds.has(n.id));
      } else if (presetView === 'w_a') {
        const seedIds = new Set(rawNodes.filter((n) => n.category === 'w_a' || n.category === 'ptq_wa').map((n) => n.id));
        const neighborIds = new Set<string>();
        for (const id of seedIds) {
          const nb = adjacencyMap.get(id);
          if (nb) nb.forEach((nid) => neighborIds.add(nid));
        }
        filteredNodes = filteredNodes.filter((n) => seedIds.has(n.id) || neighborIds.has(n.id));
      } else if (presetView.startsWith('hw_') || presetView.startsWith('algo_')) {
        // For hardware/algorithm presets: 2-hop BFS to find related nodes
        // but only through data_type/scheme intermediaries (not other hw/algo at hop 1)
        const rootNode = rawNodes.find((n) => n.id === presetView);
        const rootType = rootNode?.node_type;
        const visited = new Set<string>([presetView]);

        // Hop 1: direct neighbors (data types, schemes)
        const hop1 = new Set<string>();
        const nb1 = adjacencyMap.get(presetView);
        if (nb1) {
          for (const nid of nb1) {
            visited.add(nid);
            hop1.add(nid);
          }
        }

        // Hop 2: from hop-1 intermediaries, reach nodes of other types
        // For hw_ root: hop1 = data_types + schemes, hop2 = algorithms (+ same-type hw we skip)
        // For algo_ root: hop1 = data_types + schemes, hop2 = hardware
        for (const nid of hop1) {
          const intermediary = rawNodes.find((n) => n.id === nid);
          if (!intermediary) continue;
          // Only traverse through intermediary node types (data_type, scheme)
          if (intermediary.node_type === 'data_type' || intermediary.node_type === 'scheme') {
            const nb2 = adjacencyMap.get(nid);
            if (nb2) {
              for (const neighbor of nb2) {
                const neighborNode = rawNodes.find((n) => n.id === neighbor);
                // Don't pull in more nodes of same type as root (e.g., don't show all hardware for hw_ root)
                if (neighborNode && neighborNode.node_type !== rootType) {
                  visited.add(neighbor);
                }
              }
            }
          }
        }
        filteredNodes = filteredNodes.filter((n) => visited.has(n.id));
      } else {
        // Generic single node + neighborhood (1-hop)
        const neighbors = adjacencyMap.get(presetView) || new Set<string>();
        const allIds = new Set([presetView, ...neighbors]);
        filteredNodes = filteredNodes.filter((n) => allIds.has(n.id));
      }
    }

    // Apply search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchIds = new Set(
        filteredNodes.filter((n) => n.label.toLowerCase().includes(term) || n.id.toLowerCase().includes(term)).map((n) => n.id)
      );
      const neighborIds = new Set<string>();
      for (const id of matchIds) {
        const nb = adjacencyMap.get(id);
        if (nb) nb.forEach((nid) => neighborIds.add(nid));
      }
      filteredNodes = filteredNodes.filter((n) => matchIds.has(n.id) || neighborIds.has(n.id));
    }

    const nodeIds = new Set(filteredNodes.map((n) => n.id));

    const nodes: GraphNode[] = filteredNodes.map((n) => ({
      id: n.id,
      label: n.label,
      node_type: n.node_type,
      category: n.category,
      metadata_json: n.metadata_json,
      color: NODE_COLORS[n.node_type] || '#9ca3af',
      val: Math.max(5, Math.min(14, 4 + (connectionCount.get(n.id) || 1) * 0.8)),
    }));

    const links: GraphLink[] = rawEdges
      .filter((e) =>
        nodeIds.has(e.source_id) &&
        nodeIds.has(e.target_id) &&
        activeEdgeFilters.has(e.edge_type)
      )
      .map((e) => ({
        source: e.source_id,
        target: e.target_id,
        edge_type: e.edge_type,
        strength: e.strength,
      }));

    return { nodes, links };
  }, [graphQuery.data, activeFilters, activeEdgeFilters, searchTerm, presetView, adjacencyMap, connectionCount, smartFilterIds, excludedSubGroups, getNodeSubGroup]);

  const toggleFilter = useCallback((nodeType: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(nodeType)) next.delete(nodeType);
      else next.add(nodeType);
      return next;
    });
  }, []);

  const toggleEdgeFilter = useCallback((edgeType: string) => {
    setActiveEdgeFilters((prev) => {
      const next = new Set(prev);
      if (next.has(edgeType)) next.delete(edgeType);
      else next.add(edgeType);
      return next;
    });
  }, []);

  // 2-hop highlight: from a node, traverse through intermediary data_type/scheme
  // nodes to reach hardware/algorithms on the other side
  const getHighlight2Hop = useCallback((nodeId: string) => {
    const rawNodes = graphQuery.data?.nodes;
    if (!rawNodes) return { nodes: new Set<string>([nodeId]), links: new Set<string>() };

    const rootNode = rawNodes.find((n) => n.id === nodeId);
    const rootType = rootNode?.node_type;
    const visited = new Set<string>([nodeId]);
    const linkKeys = new Set<string>();

    // Hop 1: direct neighbors
    const hop1 = adjacencyMap.get(nodeId) || new Set<string>();
    for (const nid of hop1) {
      visited.add(nid);
      linkKeys.add(`${nodeId}-${nid}`);
      linkKeys.add(`${nid}-${nodeId}`);
    }

    // Hop 2: from intermediary nodes (data_type, scheme), reach the other side
    for (const nid of hop1) {
      const intermediary = rawNodes.find((n) => n.id === nid);
      if (!intermediary) continue;
      if (intermediary.node_type === 'data_type' || intermediary.node_type === 'scheme') {
        const hop2 = adjacencyMap.get(nid) || new Set<string>();
        for (const nb of hop2) {
          const nbNode = rawNodes.find((n) => n.id === nb);
          if (nbNode && nbNode.node_type !== rootType) {
            visited.add(nb);
            linkKeys.add(`${nid}-${nb}`);
            linkKeys.add(`${nb}-${nid}`);
          }
        }
      }
    }

    return { nodes: visited, links: linkKeys };
  }, [adjacencyMap, graphQuery.data]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node as GraphNode);
    // Apply 2-hop highlight on click so hardware lights up for algo nodes etc.
    const { nodes, links } = getHighlight2Hop(node.id);
    setHighlightNodes(nodes);
    setHighlightLinks(links);
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 400);
      graphRef.current.zoom(3, 400);
    }
  }, [getHighlight2Hop]);

  const handleNodeHover = useCallback(
    (node: any) => {
      if (node) {
        const { nodes, links } = getHighlight2Hop(node.id);
        setHighlightNodes(nodes);
        setHighlightLinks(links);
      } else if (!searchTerm) {
        setHighlightNodes(new Set());
        setHighlightLinks(new Set());
      }
    },
    [getHighlight2Hop, searchTerm]
  );

  // Apply smart filter on a selected node
  const applySmartFilter = useCallback((nodeId: string) => {
    setSmartFilter(nodeId);
    setPresetView(null);
    setSearchTerm('');
    // Enable all node types so the reachable graph is fully shown
    setActiveFilters(new Set(['algorithm', 'scheme', 'data_type', 'hardware']));
    setActiveEdgeFilters(new Set(['implements', 'uses', 'supports']));
  }, []);

  const clearAllFilters = useCallback(() => {
    setSmartFilter(null);
    setPresetView(null);
    setSearchTerm('');
    setSelectedNode(null);
    setActiveFilters(new Set(['algorithm', 'scheme', 'data_type', 'hardware']));
    setActiveEdgeFilters(new Set(['implements', 'uses', 'supports']));
    setExcludedSubGroups({});
    setExpandedType(null);
    if (graphRef.current) graphRef.current.zoomToFit(400, 40);
  }, []);

  // Configure d3 forces for better spacing
  const configureForces = useCallback(() => {
    if (!graphRef.current) return;
    const fg = graphRef.current;
    fg.d3Force('charge')?.strength(-450).distanceMax(700);
    fg.d3Force('link')?.distance(110);
    fg.d3Force('center')?.strength(0.025);
    // Reheat so forces apply
    fg.d3ReheatSimulation?.();
  }, []);

  useEffect(() => {
    // Try immediately and also after a short delay (graph may not be ready)
    configureForces();
    const t = setTimeout(configureForces, 200);
    return () => clearTimeout(t);
  }, [configureForces]);

  // Re-apply forces when data changes (e.g. filter applied)
  useEffect(() => {
    if (graphData.nodes.length > 0) {
      const t1 = setTimeout(configureForces, 100);
      const t2 = setTimeout(() => graphRef.current?.zoomToFit(400, 60), 1200);
      return () => { clearTimeout(t1); clearTimeout(t2); };
    }
  }, [graphData.nodes.length, configureForces]);

  // Shared radius calculation used by both render and hit-area
  const getNodeRadius = useCallback((val: number) => Math.sqrt(val) * 2.8, []);

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const n = node as GraphNode & { x: number; y: number };
      if (!isFinite(n.x) || !isFinite(n.y)) return;

      const label = n.label;
      const fontSize = Math.max(11 / globalScale, 2.5);
      const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(n.id);
      const isSmartFiltered = smartFilter === n.id;
      const opacity = isHighlighted ? 1 : 0.12;

      const radius = getNodeRadius(n.val);

      // Node circle
      ctx.beginPath();
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, false);
      ctx.globalAlpha = opacity;
      ctx.fillStyle = n.color;
      ctx.fill();

      // Ring for highlighted or smart-filter root
      if (highlightNodes.has(n.id) || isSmartFiltered) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, radius + 1.5, 0, 2 * Math.PI, false);
        ctx.strokeStyle = isSmartFiltered ? '#1d4ed8' : n.color;
        ctx.lineWidth = isSmartFiltered ? 3 / globalScale : 1.5 / globalScale;
        ctx.globalAlpha = isSmartFiltered ? 1 : 0.6;
        ctx.stroke();
      }

      // Label
      if (globalScale > 0.4 || highlightNodes.has(n.id) || isSmartFiltered) {
        ctx.font = `${isSmartFiltered ? 'bold ' : ''}${fontSize}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.globalAlpha = opacity;
        ctx.fillStyle = '#1f2937';
        ctx.fillText(label, n.x, n.y + radius + 2);
      }

      ctx.globalAlpha = 1;
    },
    [highlightNodes, smartFilter, getNodeRadius]
  );

  // Paint the pointer hit area so ALL nodes are interactive
  const nodePointerAreaPaint = useCallback(
    (node: any, color: string, ctx: CanvasRenderingContext2D) => {
      const n = node as GraphNode & { x: number; y: number };
      if (!isFinite(n.x) || !isFinite(n.y)) return;
      // Generous hit area — at least 8px radius so even the smallest nodes are easy to click
      const radius = Math.max(getNodeRadius(n.val) + 6, 8);
      ctx.beginPath();
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI, false);
      ctx.fillStyle = color;
      ctx.fill();
    },
    [getNodeRadius]
  );

  const linkCanvasObject = useCallback(
    (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const source = link.source as any;
      const target = link.target as any;
      if (!source?.x || !target?.x || !isFinite(source.x) || !isFinite(target.x)) return;

      const linkKey = `${source.id}-${target.id}`;
      const isHighlighted = highlightLinks.size === 0 || highlightLinks.has(linkKey) || highlightLinks.has(`${target.id}-${source.id}`);
      const edgeColor = EDGE_COLORS[link.edge_type] || '#d1d5db';

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.lineTo(target.x, target.y);
      ctx.strokeStyle = edgeColor;
      ctx.lineWidth = isHighlighted ? Math.max(1.5 / globalScale, 0.5) : Math.max(0.5 / globalScale, 0.2);
      ctx.globalAlpha = isHighlighted ? 0.8 : 0.15;
      ctx.stroke();

      // Arrow
      if (isHighlighted && globalScale > 1) {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len > 0) {
          const arrowLen = 6 / globalScale;
          const targetRadius = getNodeRadius((target as any).val || 4);
          const endX = target.x - (dx / len) * (targetRadius + 2);
          const endY = target.y - (dy / len) * (targetRadius + 2);
          const angle = Math.atan2(dy, dx);
          ctx.beginPath();
          ctx.moveTo(endX, endY);
          ctx.lineTo(endX - arrowLen * Math.cos(angle - Math.PI / 6), endY - arrowLen * Math.sin(angle - Math.PI / 6));
          ctx.lineTo(endX - arrowLen * Math.cos(angle + Math.PI / 6), endY - arrowLen * Math.sin(angle + Math.PI / 6));
          ctx.closePath();
          ctx.fillStyle = edgeColor;
          ctx.globalAlpha = 0.8;
          ctx.fill();
        }
      }

      ctx.globalAlpha = 1;
    },
    [highlightLinks, getNodeRadius]
  );

  // ─── Empty / seeding state ─────────────────────────────────────────
  if (seedStatus && !seedStatus.seeded) {
    return (
      <div className="min-h-screen">
        <Header title="Quantization Knowledge Graph" subtitle="Interactive visual guide to the quantization space" />
        <div className="p-6 flex items-center justify-center" style={{ height: 'calc(100vh - 8rem)' }}>
          <div className="text-center">
            <Database className="w-16 h-16 text-[#999] mx-auto mb-4" />
            <h2 className="text-xl font-display font-bold text-black mb-2">Knowledge Graph Not Seeded</h2>
            <p className="text-[#999] mb-6 max-w-md">
              Populate with quantization algorithms, hardware, data types, and their relationships.
            </p>
            <button
              onClick={() => seedMutation.mutate()}
              disabled={seedMutation.isPending}
              className="px-6 py-3 bg-black hover:bg-[#333] text-white font-medium tracking-wide uppercase transition-colors disabled:opacity-50"
            >
              {seedMutation.isPending ? (
                <><Loader2 className="w-4 h-4 animate-spin inline mr-2" />Seeding...</>
              ) : 'Seed Knowledge Graph'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (graphQuery.isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="Quantization Knowledge Graph" subtitle="Loading..." />
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 8rem)' }}>
          <Loader2 className="w-8 h-8 animate-spin text-black" />
        </div>
      </div>
    );
  }

  // Group connected nodes for the detail panel
  const getConnectedByType = (nodeId: string) => {
    const neighbors = adjacencyMap.get(nodeId) || new Set<string>();
    const grouped: Record<string, Array<{ id: string; label: string; edgeType: string }>> = {
      algorithm: [], scheme: [], data_type: [], hardware: [],
    };
    for (const nid of neighbors) {
      const node = graphQuery.data?.nodes.find((n) => n.id === nid);
      if (!node) continue;
      const et = edgeTypeMap.get(`${nodeId}-${nid}`) || edgeTypeMap.get(`${nid}-${nodeId}`) || 'related';
      grouped[node.node_type]?.push({ id: nid, label: node.label, edgeType: et });
    }
    return grouped;
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header title="Quantization Knowledge Graph" subtitle={`${graphData.nodes.length} nodes \u00b7 ${graphData.links.length} edges`} />

      <div className="flex flex-1 overflow-hidden" style={{ height: 'calc(100vh - 4rem)' }}>
        {/* ─── Left panel ──────────────────────────────────── */}
        <div
          className={clsx(
            'shrink-0 border-r border-[#e5e5e5] bg-white flex flex-col transition-all duration-200 overflow-hidden',
            sidebarOpen ? 'w-72' : 'w-10'
          )}
        >
          {/* Collapse / expand toggle */}
          <div className={clsx('flex items-center border-b border-[#f0f0f0]', sidebarOpen ? 'px-3 py-2 justify-between' : 'justify-center py-2')}>
            {sidebarOpen && <span className="text-xs font-semibold text-[#999] uppercase tracking-wider">Filters</span>}
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="p-1 rounded hover:bg-[#f5f5f5] text-[#999] hover:text-[#333] transition-colors"
              title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {sidebarOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
            </button>
          </div>

          {/* Sidebar content (hidden when collapsed) */}
          {sidebarOpen && (
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#999]" />
                <input
                  type="text"
                  placeholder="Search nodes..."
                  value={searchTerm}
                  onChange={(e) => { setSearchTerm(e.target.value); setPresetView(null); setSmartFilter(null); }}
                  className="w-full pl-10 pr-4 py-2 bg-[#fafafa] border border-[#e5e5e5] rounded-none text-sm text-black placeholder-gray-400 focus:outline-none focus:border-black"
                />
              </div>

              {/* Active filter indicator */}
              {(smartFilter || presetView || searchTerm) && (
                <button
                  onClick={clearAllFilters}
                  className="flex items-center gap-2 px-3 py-2 bg-[#fafafa] border border-black text-black text-sm rounded-none hover:bg-[#f5f5f5] transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span className="flex-1 text-left truncate">
                    {smartFilter
                      ? `Exploring: ${graphQuery.data?.nodes.find((n) => n.id === smartFilter)?.label || smartFilter}`
                      : presetView
                        ? PRESET_VIEWS.find((v) => v.filter === presetView)?.label
                        : `Search: "${searchTerm}"`}
                  </span>
                  <X className="w-3.5 h-3.5" />
                </button>
              )}

              {/* Node type toggles with drill-through sub-groups */}
              <div>
                <button
                  onClick={() => setSidebarSection((s) => ({ ...s, types: !s.types }))}
                  className="w-full flex items-center gap-2 text-xs font-semibold text-[#999] uppercase tracking-wider mb-1"
                >
                  {sidebarSection.types ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  <Filter className="w-3 h-3" />
                  Node Types
                </button>
                {sidebarSection.types && (
                  <div className="space-y-0.5">
                    {Object.entries(NODE_TYPE_LABELS).map(([type, label]) => {
                      const Icon = NODE_TYPE_ICONS[type];
                      const count = graphData.nodes.filter((n) => n.node_type === type).length;
                      const total = graphQuery.data?.nodes.filter((n) => n.node_type === type).length || 0;
                      const subGroups = getSubGroupMap(type);
                      const isExpanded = expandedType === type;
                      const hasExclusions = (excludedSubGroups[type]?.size || 0) > 0;
                      return (
                        <div key={type}>
                          <div className="flex items-center gap-0.5">
                            {/* Expand/collapse sub-groups arrow */}
                            {subGroups && (
                              <button
                                onClick={() => setExpandedType(isExpanded ? null : type)}
                                className="p-0.5 rounded hover:bg-[#f5f5f5] text-[#999] shrink-0"
                              >
                                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                              </button>
                            )}
                            <button
                              onClick={() => toggleFilter(type)}
                              className={clsx(
                                'flex-1 flex items-center gap-2 px-2 py-1.5 rounded-none text-sm transition-all',
                                activeFilters.has(type)
                                  ? 'text-black hover:bg-[#fafafa]'
                                  : 'text-[#999] hover:text-[#666] line-through'
                              )}
                            >
                              <div
                                className="w-3 h-3 rounded-full shrink-0 border-2"
                                style={{
                                  backgroundColor: activeFilters.has(type) ? NODE_COLORS[type] : 'transparent',
                                  borderColor: NODE_COLORS[type],
                                }}
                              />
                              <Icon className="w-3.5 h-3.5 shrink-0" />
                              <span className="flex-1 text-left">{label}</span>
                              {hasExclusions && <span className="w-1.5 h-1.5 rounded-full bg-[#C5A47E] shrink-0" title="Some sub-groups hidden" />}
                              <span className="text-xs text-[#999]">{count}/{total}</span>
                            </button>
                          </div>
                          {/* Sub-group drill-through list */}
                          {isExpanded && subGroups && activeFilters.has(type) && (
                            <div className="ml-5 mt-0.5 mb-1 space-y-0 border-l-2 border-[#f0f0f0] pl-2">
                              {Object.entries(subGroups).map(([gid, { label: gLabel }]) => {
                                const excluded = excludedSubGroups[type]?.has(gid);
                                // Count nodes in this sub-group visible in graph
                                const sgCount = graphData.nodes.filter((n) => {
                                  if (n.node_type !== type) return false;
                                  return getNodeSubGroup(n) === gid;
                                }).length;
                                const sgTotal = graphQuery.data?.nodes.filter((n) => {
                                  if (n.node_type !== type) return false;
                                  return getNodeSubGroup(n) === gid;
                                }).length || 0;
                                if (sgTotal === 0) return null;
                                return (
                                  <button
                                    key={gid}
                                    onClick={() => toggleSubGroup(type, gid)}
                                    className={clsx(
                                      'w-full flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-all',
                                      excluded
                                        ? 'text-[#999] line-through hover:text-[#999]'
                                        : 'text-[#333] hover:bg-[#fafafa]'
                                    )}
                                  >
                                    <div
                                      className="w-2 h-2 rounded-sm shrink-0 border"
                                      style={{
                                        backgroundColor: excluded ? 'transparent' : NODE_COLORS[type],
                                        borderColor: NODE_COLORS[type],
                                        opacity: excluded ? 0.4 : 0.7,
                                      }}
                                    />
                                    <span className="flex-1 text-left truncate">{gLabel}</span>
                                    <span className="text-[#999]">{sgCount}/{sgTotal}</span>
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

          {/* Edge type toggles */}
          <div>
            <button
              onClick={() => setSidebarSection((s) => ({ ...s, edges: !s.edges }))}
              className="w-full flex items-center gap-2 text-xs font-semibold text-[#999] uppercase tracking-wider mb-1"
            >
              {sidebarSection.edges ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Edge Types
            </button>
            {sidebarSection.edges && (
              <div className="space-y-0.5">
                {Object.entries(EDGE_TYPE_LABELS).map(([type, { label, desc }]) => (
                  <button
                    key={type}
                    onClick={() => toggleEdgeFilter(type)}
                    className={clsx(
                      'w-full flex items-center gap-2 px-3 py-1.5 rounded-none text-sm transition-all',
                      activeEdgeFilters.has(type) ? 'text-black hover:bg-[#fafafa]' : 'text-[#999] line-through'
                    )}
                    title={desc}
                  >
                    <div className="w-6 h-0.5 shrink-0 rounded" style={{ backgroundColor: activeEdgeFilters.has(type) ? EDGE_COLORS[type] : '#d1d5db' }} />
                    <span className="flex-1 text-left">{label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Preset views */}
          <div>
            <button
              onClick={() => setSidebarSection((s) => ({ ...s, views: !s.views }))}
              className="w-full flex items-center gap-2 text-xs font-semibold text-[#999] uppercase tracking-wider mb-1"
            >
              {sidebarSection.views ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Quick Views
            </button>
            {sidebarSection.views && (
              <div className="space-y-0.5">
                {PRESET_VIEWS.map((view) => (
                  <button
                    key={view.label}
                    onClick={() => {
                      setPresetView(view.filter);
                      setSmartFilter(null);
                      setSearchTerm('');
                      if (!view.filter) clearAllFilters();
                    }}
                    className={clsx(
                      'w-full text-left px-3 py-1.5 rounded-none text-sm transition-all',
                      presetView === view.filter
                        ? 'bg-[#f5f5f5] text-black font-medium'
                        : 'text-[#666] hover:text-black hover:bg-[#fafafa]'
                    )}
                  >
                    {view.label}
                  </button>
                ))}
              </div>
            )}
          </div>
            </div>
          )}
        </div>

        {/* ─── Main graph area ──────────────────────────────────── */}
        <div className="flex-1 relative bg-[#fafafa]">
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeId="id"
            nodeLabel=""
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={nodePointerAreaPaint}
            linkCanvasObject={linkCanvasObject}
            linkSource="source"
            linkTarget="target"
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            backgroundColor="#fafafa"
            cooldownTicks={200}
            d3AlphaDecay={0.015}
            d3VelocityDecay={0.3}
            d3AlphaMin={0.001}
          />

          {/* Legend overlay */}
          <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-sm border border-[#e5e5e5] rounded-none shadow-lg overflow-hidden transition-all duration-200">
            <button
              onClick={() => setLegendExpanded((v) => !v)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-[#fafafa] transition-colors"
            >
              <span className="text-sm font-semibold text-black flex items-center gap-1.5">
                <Info className="w-4 h-4 text-[#C5A47E]" />
                Legend
              </span>
              <span className="flex items-center gap-1">
                {!legendExpanded && (
                  <span className="flex items-center gap-0.5">
                    {Object.values(NODE_COLORS).map((c, i) => (
                      <span key={i} className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />
                    ))}
                  </span>
                )}
                {legendExpanded ? <ChevronDown className="w-3.5 h-3.5 text-[#999]" /> : <ChevronRight className="w-3.5 h-3.5 text-[#999]" />}
              </span>
            </button>
            {legendExpanded && (
              <div className="px-3 pb-3 space-y-2">
                <div className="text-xs text-[#999] font-medium uppercase tracking-wider">Nodes</div>
                {Object.entries(NODE_TYPE_LABELS).map(([type, label]) => (
                  <div key={type} className="flex items-center gap-2 text-sm">
                    <div className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: NODE_COLORS[type] }} />
                    <span className="text-[#333]">{label}</span>
                  </div>
                ))}
                <div className="text-xs text-[#999] font-medium uppercase tracking-wider mt-2">Edges</div>
                {Object.entries(EDGE_TYPE_LABELS).map(([type, { label, desc }]) => (
                  <div key={type} className="flex items-center gap-2 text-sm">
                    <div className="w-5 h-1 rounded" style={{ backgroundColor: EDGE_COLORS[type] }} />
                    <span className="text-[#333]">{label}</span>
                    <span className="text-[#999] text-xs ml-auto">{desc.split(' ').slice(0, 3).join(' ')}</span>
                  </div>
                ))}
                <div className="text-xs text-[#999] mt-2 pt-2 border-t border-[#f0f0f0]">
                  Click a node to inspect. Use "Explore" for full subgraph.
                </div>
              </div>
            )}
          </div>

          {/* Zoom controls */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1.5">
            <button
              onClick={() => graphRef.current?.zoom(graphRef.current.zoom() * 1.5, 300)}
              className="w-9 h-9 bg-white border border-[#e5e5e5] rounded-none flex items-center justify-center text-[#666] hover:text-black hover:border-gray-300 shadow-sm transition-colors"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={() => graphRef.current?.zoom(graphRef.current.zoom() / 1.5, 300)}
              className="w-9 h-9 bg-white border border-[#e5e5e5] rounded-none flex items-center justify-center text-[#666] hover:text-black hover:border-gray-300 shadow-sm transition-colors"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={() => graphRef.current?.zoomToFit(400, 40)}
              className="w-9 h-9 bg-white border border-[#e5e5e5] rounded-none flex items-center justify-center text-[#666] hover:text-black hover:border-gray-300 shadow-sm transition-colors"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ─── Right panel: selected node detail ────────────────── */}
        {selectedNode && (
          <div className="w-80 shrink-0 border-l border-[#e5e5e5] bg-white p-4 overflow-y-auto">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-4 h-4 rounded-full shrink-0" style={{ backgroundColor: NODE_COLORS[selectedNode.node_type] }} />
                <h3 className="font-display font-bold text-black truncate">{selectedNode.label}</h3>
              </div>
              <button onClick={() => setSelectedNode(null)} className="text-[#999] hover:text-[#666] shrink-0">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Explore button */}
            <button
              onClick={() => applySmartFilter(selectedNode.id)}
              className={clsx(
                'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-none text-sm font-medium transition-colors mb-4',
                smartFilter === selectedNode.id
                  ? 'bg-[#f5f5f5] text-black border border-black'
                  : 'bg-black text-white hover:bg-[#333]'
              )}
            >
              <Maximize2 className="w-4 h-4" />
              {smartFilter === selectedNode.id ? 'Currently Exploring' : 'Explore Connected Graph'}
            </button>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="px-3 py-2 rounded-none" style={{ backgroundColor: NODE_BG_COLORS[selectedNode.node_type] }}>
                  <label className="text-xs text-[#999] uppercase tracking-wider">Type</label>
                  <p className="text-sm font-medium text-black">{NODE_TYPE_LABELS[selectedNode.node_type]}</p>
                </div>
                <div className="px-3 py-2 bg-[#fafafa] rounded-none">
                  <label className="text-xs text-[#999] uppercase tracking-wider">Category</label>
                  <p className="text-sm font-medium text-black">{selectedNode.category}</p>
                </div>
              </div>

              {/* Metadata */}
              {selectedNode.metadata_json && Object.keys(selectedNode.metadata_json).length > 0 && (
                <div>
                  <label className="text-xs text-[#999] uppercase tracking-wider">Properties</label>
                  <div className="mt-1.5 bg-[#fafafa] rounded-none p-3 space-y-1.5">
                    {Object.entries(selectedNode.metadata_json).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between text-sm">
                        <span className="text-[#999]">{key}</span>
                        <span className="text-black font-mono text-xs">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Connected nodes grouped by type */}
              {(() => {
                const connected = getConnectedByType(selectedNode.id);
                return Object.entries(connected).map(([type, nodes]) => {
                  if (nodes.length === 0) return null;
                  const Icon = NODE_TYPE_ICONS[type];
                  return (
                    <div key={type}>
                      <label className="text-xs text-[#999] uppercase tracking-wider flex items-center gap-1.5">
                        <Icon className="w-3 h-3" />
                        {NODE_TYPE_LABELS[type]} ({nodes.length})
                      </label>
                      <div className="mt-1 space-y-0.5 max-h-40 overflow-y-auto">
                        {nodes.map((n) => (
                          <button
                            key={n.id}
                            onClick={() => {
                              const gn = graphData.nodes.find((x) => x.id === n.id);
                              if (gn) handleNodeClick(gn);
                            }}
                            className="w-full flex items-center gap-2 px-2 py-1 rounded text-sm text-[#333] hover:text-black hover:bg-[#fafafa] transition-colors"
                          >
                            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: NODE_COLORS[type] }} />
                            <span className="flex-1 text-left truncate">{n.label}</span>
                            <span className="text-xs text-[#999] shrink-0">{n.edgeType}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                });
              })()}

              <div className="pt-3 border-t border-[#f0f0f0]">
                <p className="text-xs text-[#999] font-mono">{selectedNode.id}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
