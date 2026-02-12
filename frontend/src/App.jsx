import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DetailsPanel from './components/DetailsPanel';
import GraphVisualizer from './components/GraphVisualizer';
import InputPanel from './components/InputPanel';
import InsightsPanel from './components/InsightsPanel';
import LogTerminal from './components/LogTerminal';

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const WS_URL = import.meta.env.VITE_WS_URL || `${API_BASE.replace(/^http/, 'ws')}/ws/logs`;

const getEndpointId = (value) => {
    if (value && typeof value === 'object') {
        return value.id || '';
    }
    return value || '';
};

const getLinkKey = (link) => {
    const source = getEndpointId(link.source);
    const target = getEndpointId(link.target);
    const relationType = link.relation_type || 'RELATED_TO';
    const predicate = link.predicate || '';
    return `${source}->${target}|${relationType}|${predicate}`;
};

const findShortestPath = (graph, startId, endId) => {
    if (!startId || !endId || startId === endId) return [];

    const adjacency = new Map();
    const nodes = graph?.nodes || [];
    const links = graph?.links || [];

    nodes.forEach((node) => adjacency.set(node.id, new Set()));

    links.forEach((link) => {
        const sourceId = getEndpointId(link.source);
        const targetId = getEndpointId(link.target);
        if (!sourceId || !targetId) return;

        if (!adjacency.has(sourceId)) adjacency.set(sourceId, new Set());
        if (!adjacency.has(targetId)) adjacency.set(targetId, new Set());
        adjacency.get(sourceId).add(targetId);
        adjacency.get(targetId).add(sourceId);
    });

    const queue = [startId];
    const visited = new Set([startId]);
    const previous = new Map();

    while (queue.length > 0) {
        const current = queue.shift();
        if (current === endId) break;

        for (const neighbor of adjacency.get(current) || []) {
            if (visited.has(neighbor)) continue;
            visited.add(neighbor);
            previous.set(neighbor, current);
            queue.push(neighbor);
        }
    }

    if (!visited.has(endId)) return [];

    const path = [];
    let current = endId;
    while (current !== undefined) {
        path.push(current);
        current = previous.get(current);
    }

    return path.reverse();
};

function App() {
    const [graphData, setGraphData] = useState({ nodes: [], links: [], insights: {}, meta: {} });
    const [loading, setLoading] = useState(false);
    const [loadingMore, setLoadingMore] = useState(false);
    const [resetToken, setResetToken] = useState(0);
    const [logs, setLogs] = useState([]);
    const [showLogs, setShowLogs] = useState(false);
    const [unreadLogs, setUnreadLogs] = useState(0);
    const [activeFilters, setActiveFilters] = useState([]);
    const [selectedNode, setSelectedNode] = useState(null);
    const [selectedLink, setSelectedLink] = useState(null);
    const [pathStart, setPathStart] = useState('');
    const [pathEnd, setPathEnd] = useState('');
    const [shortestPath, setShortestPath] = useState([]);
    const ws = useRef(null);
    const showLogsRef = useRef(showLogs);
    const reconnectTimerRef = useRef(null);
    const shouldReconnectRef = useRef(true);
    const lastLogRef = useRef({ message: '', timestamp: 0 });

    useEffect(() => {
        showLogsRef.current = showLogs;
    }, [showLogs]);

    const appendLog = useCallback((message, { forceOpen = false } = {}) => {
        const now = Date.now();
        if (lastLogRef.current.message === message && now - lastLogRef.current.timestamp < 1500) {
            return;
        }

        lastLogRef.current = { message, timestamp: now };
        setLogs((prev) => [...prev, message]);

        if (forceOpen) {
            setShowLogs(true);
            setUnreadLogs(0);
            return;
        }

        if (!showLogsRef.current) {
            setUnreadLogs((prev) => prev + 1);
        }
    }, []);

    const toggleLogs = useCallback(() => {
        setShowLogs((prev) => {
            const next = !prev;
            if (next) {
                setUnreadLogs(0);
            }
            return next;
        });
    }, []);

    const openLogs = useCallback(() => {
        setShowLogs(true);
        setUnreadLogs(0);
    }, []);

    useEffect(() => {
        shouldReconnectRef.current = true;

        const connectWs = () => {
            if (!shouldReconnectRef.current) return;

            const socket = new WebSocket(WS_URL);
            ws.current = socket;

            socket.onopen = () => {
                appendLog('System connected. Ready.');
            };

            socket.onmessage = (event) => {
                const message = event.data;
                appendLog(message);
            };

            socket.onclose = () => {
                if (!shouldReconnectRef.current) return;
                reconnectTimerRef.current = setTimeout(connectWs, 3000);
            };

            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        };

        connectWs();
        return () => {
            shouldReconnectRef.current = false;

            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }

            if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
                ws.current.close();
            }

            ws.current = null;
        };
    }, [appendLog]);

    const handleProcess = async ({ urls, files, depth }) => {
        setLoading(true);
        setLoadingMore(false);
        setLogs(['Request sent. Waiting for server response...']);
        setShowLogs(true);
        setUnreadLogs(0);

        const formData = new FormData();
        if (urls.length > 0) {
            formData.append('urls', JSON.stringify(urls));
        }
        formData.append('depth', depth);
        formData.append('node_limit', 700);
        formData.append('link_limit', 2600);

        if (files.length > 0) {
            files.forEach((file) => formData.append('files', file));
        }

        try {
            const response = await fetch(`${API_BASE}/process`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            const normalized = {
                nodes: data.nodes || [],
                links: data.links || [],
                insights: data.insights || {},
                meta: data.meta || {},
            };

            setGraphData(normalized);
            setActiveFilters([]);
            setSelectedNode(null);
            setSelectedLink(null);
            setShortestPath([]);
            setPathStart('');
            setPathEnd('');
        } catch (error) {
            console.error('Error processing:', error);
            appendLog(`Error: ${error.message}`, { forceOpen: true });
            alert('Error processing data. Check logs for details.');
        } finally {
            setLoading(false);
        }
    };

    const handleExport = () => {
        if (!graphData.nodes.length) return;

        const sanitizedData = {
            nodes: graphData.nodes.map((node) => {
                const cleaned = { ...node };
                ['index', 'x', 'y', 'z', 'vx', 'vy', 'vz'].forEach((key) => delete cleaned[key]);
                return cleaned;
            }),
            links: graphData.links.map((link) => {
                const source = getEndpointId(link.source);
                const target = getEndpointId(link.target);
                const cleaned = { ...link };
                delete cleaned.index;
                return { ...cleaned, source, target };
            }),
            insights: graphData.insights || {},
            meta: graphData.meta || {},
        };

        const jsonString = JSON.stringify(sanitizedData, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const href = URL.createObjectURL(blob);
        const downloadLink = document.createElement('a');
        downloadLink.href = href;
        downloadLink.download = `graph_network_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(href);
    };

    const handleImport = (file) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const data = JSON.parse(event.target.result);
                if (!data.nodes || !data.links) {
                    alert('Invalid graph JSON format');
                    return;
                }

                setGraphData({
                    nodes: data.nodes,
                    links: data.links,
                    insights: data.insights || {},
                    meta: data.meta || {},
                });
                setActiveFilters([]);
                setSelectedNode(null);
                setSelectedLink(null);
                setShortestPath([]);
                appendLog(`Loaded graph from ${file.name}`);
            } catch (error) {
                console.error(error);
                alert('Failed to parse JSON');
            }
        };

        reader.readAsText(file);
    };

    const rootNodes = graphData.nodes.filter((node) => node.type === 'web' || node.type === 'file');

    const getFilteredGraph = () => {
        if (activeFilters.length === 0) return graphData;

        const selectedSet = new Set(activeFilters);
        const validNodes = new Set(activeFilters);

        graphData.links.forEach((link) => {
            const sourceId = getEndpointId(link.source);
            const targetId = getEndpointId(link.target);

            if (selectedSet.has(sourceId)) {
                validNodes.add(targetId);
            } else if (selectedSet.has(targetId)) {
                validNodes.add(sourceId);
            }
        });

        const filteredNodes = graphData.nodes.filter((node) => validNodes.has(node.id));
        const filteredLinks = graphData.links.filter((link) => {
            const sourceId = getEndpointId(link.source);
            const targetId = getEndpointId(link.target);
            return validNodes.has(sourceId) && validNodes.has(targetId);
        });

        return {
            nodes: filteredNodes,
            links: filteredLinks,
            insights: graphData.insights || {},
        };
    };

    const displayData = getFilteredGraph();

    const entityOptions = useMemo(
        () =>
            displayData.nodes
                .filter((node) => String(node.id).startsWith('entity:'))
                .map((node) => ({ id: node.id, title: node.title || node.id }))
                .sort((left, right) => left.title.localeCompare(right.title)),
        [displayData.nodes]
    );

    const highlightedLinkKeys = useMemo(() => {
        if (shortestPath.length < 2) return [];

        const pairSet = new Set();
        for (let index = 0; index < shortestPath.length - 1; index += 1) {
            const source = shortestPath[index];
            const target = shortestPath[index + 1];
            pairSet.add(`${source}->${target}`);
            pairSet.add(`${target}->${source}`);
        }

        return displayData.links
            .filter((link) => pairSet.has(`${getEndpointId(link.source)}->${getEndpointId(link.target)}`))
            .map((link) => getLinkKey(link));
    }, [displayData.links, shortestPath]);

    const shortestPathTitles = useMemo(() => {
        if (!shortestPath.length) return [];
        const nodeById = new Map(displayData.nodes.map((node) => [node.id, node]));
        return shortestPath.map((nodeId) => nodeById.get(nodeId)?.title || nodeId);
    }, [displayData.nodes, shortestPath]);

    const handleFindPath = () => {
        const path = findShortestPath(displayData, pathStart, pathEnd);
        setShortestPath(path);
    };

    const canLoadMore = Boolean(graphData.meta?.query_id && graphData.meta?.truncated);

    const handleLoadMore = async () => {
        const meta = graphData.meta || {};
        if (!meta.query_id || !meta.truncated) return;

        const currentNodeLimit = Number(meta.node_limit || 0);
        const currentLinkLimit = Number(meta.link_limit || 0);
        const totalNodes = Number(meta.total_nodes || currentNodeLimit);
        const totalLinks = Number(meta.total_links || currentLinkLimit);
        const nextNodeLimit = Math.min(totalNodes, currentNodeLimit + Number(meta.load_more_node_step || 500));
        const nextLinkLimit = Math.min(totalLinks, currentLinkLimit + Number(meta.load_more_link_step || 2200));

        if (nextNodeLimit <= currentNodeLimit && nextLinkLimit <= currentLinkLimit) {
            return;
        }

        setLoadingMore(true);
        appendLog(`Loading more graph detail (${nextNodeLimit} nodes / ${nextLinkLimit} links target)...`);

        try {
            const response = await fetch(`${API_BASE}/graph_view`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query_id: meta.query_id,
                    node_limit: nextNodeLimit,
                    link_limit: nextLinkLimit,
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to load expanded graph.');
            }

            const data = await response.json();
            setGraphData({
                nodes: data.nodes || [],
                links: data.links || [],
                insights: data.insights || {},
                meta: data.meta || {},
            });

            appendLog(
                `Expanded graph view: ${data.meta?.visible_nodes || 0}/${data.meta?.total_nodes || 0} nodes, `
                + `${data.meta?.visible_links || 0}/${data.meta?.total_links || 0} links.`
            );
        } catch (error) {
            console.error(error);
            appendLog(`Error loading expanded graph: ${error.message}`, { forceOpen: true });
        } finally {
            setLoadingMore(false);
        }
    };

    const handleResetAll = useCallback(() => {
        setGraphData({ nodes: [], links: [], insights: {}, meta: {} });
        setLoading(false);
        setLoadingMore(false);
        setActiveFilters([]);
        setSelectedNode(null);
        setSelectedLink(null);
        setPathStart('');
        setPathEnd('');
        setShortestPath([]);
        setLogs([]);
        setShowLogs(false);
        setUnreadLogs(0);
        lastLogRef.current = { message: '', timestamp: 0 };
        setResetToken((prev) => prev + 1);
    }, []);

    return (
        <div className="App">
            <GraphVisualizer
                graphData={displayData}
                onNodeSelect={(node) => {
                    setSelectedNode(node);
                    setSelectedLink(null);
                }}
                onLinkSelect={(link) => {
                    setSelectedLink(link);
                    setSelectedNode(null);
                }}
                highlightedNodeIds={shortestPath}
                highlightedLinkKeys={highlightedLinkKeys}
            />

            <InputPanel
                key={`input-panel-${resetToken}`}
                onProcess={handleProcess}
                loading={loading}
                loadingMore={loadingMore}
                onToggleLogs={toggleLogs}
                unreadLogs={unreadLogs}
                onExport={handleExport}
                onImport={handleImport}
                onLoadMore={handleLoadMore}
                onResetAll={handleResetAll}
                canLoadMore={canLoadMore}
                graphMeta={graphData.meta}
                rootNodes={rootNodes}
                selectedFilters={activeFilters}
                onFilterChange={setActiveFilters}
            />

            <InsightsPanel
                insights={graphData.insights}
                entityOptions={entityOptions}
                pathStart={pathStart}
                pathEnd={pathEnd}
                onPathStartChange={setPathStart}
                onPathEndChange={setPathEnd}
                onFindPath={handleFindPath}
                shortestPathTitles={shortestPathTitles}
            />

            <DetailsPanel
                selectedNode={selectedNode}
                selectedLink={selectedLink}
                onClear={() => {
                    setSelectedNode(null);
                    setSelectedLink(null);
                }}
            />

            {!showLogs && logs.length > 0 && (
                <button
                    onClick={openLogs}
                    style={{
                        position: 'absolute',
                        left: '390px',
                        bottom: '20px',
                        width: 'auto',
                        padding: '8px 12px',
                        fontSize: '0.82rem',
                        zIndex: 18,
                        background: 'rgba(15,23,42,0.9)',
                        border: '1px solid rgba(56,189,248,0.45)',
                    }}
                >
                    Show Logs{unreadLogs > 0 ? ` (${unreadLogs})` : ''}
                </button>
            )}

            {showLogs && <LogTerminal logs={logs} onClose={() => setShowLogs(false)} />}
        </div>
    );
}

export default App;
