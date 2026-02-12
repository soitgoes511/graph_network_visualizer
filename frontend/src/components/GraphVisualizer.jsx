import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';

const RELATION_COLORS = {
    LINKS_TO_INTERNAL: 'rgba(125, 211, 252, 0.45)',
    LINKS_TO_EXTERNAL: 'rgba(244, 114, 182, 0.5)',
    MENTIONS_ENTITY: 'rgba(251, 146, 60, 0.55)',
    MENTIONS_CONCEPT: 'rgba(250, 204, 21, 0.55)',
    CO_OCCURS_IN_SENTENCE: 'rgba(148, 163, 184, 0.4)',
};

const getEndpointId = (value) => {
    if (value && typeof value === 'object') {
        return value.id || '';
    }
    return value || '';
};

const escapeHtml = (value) =>
    String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');

const getLinkKey = (link) => {
    const source = getEndpointId(link.source);
    const target = getEndpointId(link.target);
    const relationType = link.relation_type || 'RELATED_TO';
    const predicate = link.predicate || '';
    return `${source}->${target}|${relationType}|${predicate}`;
};

const hashString = (value) => {
    let hash = 0;
    for (let index = 0; index < value.length; index += 1) {
        hash = (hash << 5) - hash + value.charCodeAt(index);
        hash |= 0;
    }
    return Math.abs(hash);
};

const GraphVisualizer = ({
    graphData,
    onNodeSelect,
    onLinkSelect,
    highlightedNodeIds = [],
    highlightedLinkKeys = [],
}) => {
    const fgRef = useRef();
    const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

    const highlightedNodeSet = useMemo(() => new Set(highlightedNodeIds), [highlightedNodeIds]);
    const highlightedLinkSet = useMemo(() => new Set(highlightedLinkKeys), [highlightedLinkKeys]);

    useEffect(() => {
        const handleResize = () => {
            setDimensions({ width: window.innerWidth, height: window.innerHeight });
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const handleNodeClick = useCallback(
        (node) => {
            const distance = 40;
            const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);

            if (fgRef.current) {
                fgRef.current.cameraPosition(
                    { x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio },
                    node,
                    2200
                );
            }

            if (onNodeSelect) {
                onNodeSelect(node);
            }

            if (typeof node.id === 'string' && node.id.startsWith('http')) {
                window.open(node.id, '_blank', 'noopener,noreferrer');
            }
        },
        [onNodeSelect]
    );

    const handleLinkClick = useCallback(
        (link) => {
            if (onLinkSelect) {
                onLinkSelect(link);
            }
        },
        [onLinkSelect]
    );

    const getNodeColor = useCallback(
        (node) => {
            if (highlightedNodeSet.has(node.id)) {
                return '#ffffff';
            }
            if (node.type === 'concept') return '#facc15';
            if (node.type === 'PERSON') return '#fb923c';
            if (node.type === 'ORG') return '#ef4444';
            if (node.type === 'GPE') return '#22c55e';
            if (node.type === 'EVENT') return '#2dd4bf';
            if (node.type === 'LOC') return '#10b981';

            switch (node.type) {
                case 'web':
                    return '#38bdf8';
                case 'file':
                    return '#a855f7';
                case 'external':
                    return '#f472b6';
                default:
                    return '#94a3b8';
            }
        },
        [highlightedNodeSet]
    );

    const getLinkColor = useCallback(
        (link) => {
            if (highlightedLinkSet.has(getLinkKey(link))) {
                return 'rgba(248, 250, 252, 0.95)';
            }
            const relationType = link.relation_type || 'RELATED_TO';
            if (relationType.startsWith('VERB:')) {
                return 'rgba(45, 212, 191, 0.55)';
            }
            return RELATION_COLORS[relationType] || 'rgba(255,255,255,0.25)';
        },
        [highlightedLinkSet]
    );

    const getNodeLabel = useCallback((node) => {
        const rows = [
            `<b>${escapeHtml(node.title || node.id)}</b>`,
            `Type: ${escapeHtml(node.type || 'unknown')}`,
        ];

        if (node.count) rows.push(`Mentions: ${escapeHtml(node.count)}`);
        if (node.degree_centrality) rows.push(`Degree: ${escapeHtml(node.degree_centrality)}`);
        if (node.betweenness) rows.push(`Bridge score: ${escapeHtml(node.betweenness)}`);
        if (node.community !== undefined) rows.push(`Community: ${escapeHtml(node.community)}`);

        return rows.join('<br/>');
    }, []);

    const getLinkLabel = useCallback((link) => {
        const rows = [
            `<b>${escapeHtml(link.relation_type || 'RELATED_TO')}</b>`,
            `Weight: ${escapeHtml(Number(link.weight || 1).toFixed(2))}`,
            `Confidence: ${escapeHtml(Number(link.confidence || 0.5).toFixed(2))}`,
        ];
        if (link.predicate) rows.push(`Predicate: ${escapeHtml(link.predicate)}`);
        if (link.evidence_sentence) rows.push(`Evidence: ${escapeHtml(link.evidence_sentence)}`);
        return rows.join('<br/>');
    }, []);

    const getLinkCurvature = useCallback((link) => {
        const key = getLinkKey(link);
        const bucket = hashString(key) % 5;
        return (bucket - 2) * 0.04;
    }, []);

    return (
        <div style={{ width: '100vw', height: '100vh', position: 'fixed', top: 0, left: 0, zIndex: 0, overflow: 'hidden' }}>
            {graphData && graphData.nodes?.length > 0 ? (
                <ForceGraph3D
                    ref={fgRef}
                    width={dimensions.width}
                    height={dimensions.height}
                    graphData={graphData}
                    nodeLabel={getNodeLabel}
                    nodeColor={getNodeColor}
                    nodeVal={(node) => node.val || 1}
                    linkLabel={getLinkLabel}
                    linkColor={getLinkColor}
                    linkWidth={(link) => 0.6 + Math.log1p(Number(link.weight || 1)) * 1.8}
                    linkOpacity={0.55}
                    linkCurvature={getLinkCurvature}
                    linkDirectionalArrowLength={(link) => ((link.relation_type || '').startsWith('VERB:') ? 4 : 2.5)}
                    linkDirectionalArrowRelPos={1}
                    linkDirectionalParticles={(link) => ((link.relation_type || '').startsWith('VERB:') ? 2 : 0)}
                    linkDirectionalParticleWidth={1.6}
                    onNodeClick={handleNodeClick}
                    onLinkClick={handleLinkClick}
                    backgroundColor="#0f172a"
                    showNavInfo={false}
                />
            ) : (
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        height: '100%',
                        color: '#334155',
                        flexDirection: 'column',
                    }}
                >
                    <p style={{ fontSize: '2rem', fontWeight: 300 }}>Upload documents or enter URLs to begin</p>
                </div>
            )}
        </div>
    );
};

export default GraphVisualizer;
