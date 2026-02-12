import React from 'react';

const InsightsPanel = ({
    insights,
    entityOptions,
    pathStart,
    pathEnd,
    onPathStartChange,
    onPathEndChange,
    onFindPath,
    shortestPathTitles,
}) => {
    const bridgeNodes = insights?.top_bridge_nodes || [];
    const communities = insights?.top_communities || [];
    const relations = insights?.relation_distribution || [];

    return (
        <div
            className="glass-panel"
            style={{
                position: 'absolute',
                top: '20px',
                right: '20px',
                width: '360px',
                zIndex: 15,
                maxHeight: '90vh',
                overflowY: 'auto',
            }}
        >
            <h2 style={{ marginTop: 0, marginBottom: '12px', fontSize: '1rem' }}>Insights</h2>

            <div style={{ marginBottom: '16px' }}>
                <label style={{ marginBottom: '6px', display: 'block' }}>Top Bridge Nodes</label>
                {bridgeNodes.length === 0 ? (
                    <div style={{ color: '#94a3b8', fontSize: '0.82rem' }}>No bridge metrics available.</div>
                ) : (
                    <div style={{ fontSize: '0.82rem', color: '#cbd5e1' }}>
                        {bridgeNodes.slice(0, 6).map((node) => (
                            <div key={node.id} style={{ marginBottom: '5px' }}>
                                {node.title} ({node.type}) - {Number(node.score || 0).toFixed(3)}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ marginBottom: '16px' }}>
                <label style={{ marginBottom: '6px', display: 'block' }}>Communities</label>
                {communities.length === 0 ? (
                    <div style={{ color: '#94a3b8', fontSize: '0.82rem' }}>No communities detected yet.</div>
                ) : (
                    <div style={{ fontSize: '0.82rem', color: '#cbd5e1' }}>
                        {communities.slice(0, 5).map((community) => (
                            <div key={community.id} style={{ marginBottom: '6px' }}>
                                Group {community.id} - {community.size} nodes
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ marginBottom: '16px' }}>
                <label style={{ marginBottom: '6px', display: 'block' }}>Edge Types</label>
                {relations.length === 0 ? (
                    <div style={{ color: '#94a3b8', fontSize: '0.82rem' }}>No edge distribution available.</div>
                ) : (
                    <div style={{ fontSize: '0.82rem', color: '#cbd5e1' }}>
                        {relations.slice(0, 8).map((relation) => (
                            <div key={relation.relation_type} style={{ marginBottom: '5px' }}>
                                {relation.relation_type}: {relation.count}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div>
                <label style={{ marginBottom: '6px', display: 'block' }}>Shortest Path (Entities)</label>
                <select
                    value={pathStart}
                    onChange={(event) => onPathStartChange(event.target.value)}
                    style={{
                        width: '100%',
                        marginBottom: '8px',
                        background: 'rgba(15, 23, 42, 0.6)',
                        color: '#e2e8f0',
                        border: '1px solid rgba(255,255,255,0.15)',
                        borderRadius: '8px',
                        padding: '10px',
                    }}
                >
                    <option value="">Start entity</option>
                    {entityOptions.map((entity) => (
                        <option key={entity.id} value={entity.id}>
                            {entity.title}
                        </option>
                    ))}
                </select>
                <select
                    value={pathEnd}
                    onChange={(event) => onPathEndChange(event.target.value)}
                    style={{
                        width: '100%',
                        marginBottom: '8px',
                        background: 'rgba(15, 23, 42, 0.6)',
                        color: '#e2e8f0',
                        border: '1px solid rgba(255,255,255,0.15)',
                        borderRadius: '8px',
                        padding: '10px',
                    }}
                >
                    <option value="">End entity</option>
                    {entityOptions.map((entity) => (
                        <option key={`${entity.id}-target`} value={entity.id}>
                            {entity.title}
                        </option>
                    ))}
                </select>
                <button
                    onClick={onFindPath}
                    disabled={!pathStart || !pathEnd || pathStart === pathEnd}
                    style={{ fontSize: '0.85rem', marginBottom: '8px' }}
                >
                    FIND PATH
                </button>
                <div style={{ fontSize: '0.82rem', color: '#cbd5e1', lineHeight: 1.4 }}>
                    {shortestPathTitles.length > 0
                        ? shortestPathTitles.join(' -> ')
                        : 'Select two entities to highlight the shortest route.'}
                </div>
            </div>
        </div>
    );
};

export default InsightsPanel;
