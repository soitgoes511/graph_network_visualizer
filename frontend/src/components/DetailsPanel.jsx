import React from 'react';

const getEndpointId = (value) => {
    if (value && typeof value === 'object') {
        return value.id || '';
    }
    return value || '';
};

const Row = ({ label, value }) => {
    if (value === undefined || value === null || value === '') return null;
    return (
        <div style={{ marginBottom: '6px' }}>
            <strong style={{ color: '#cbd5e1' }}>{label}: </strong>
            <span style={{ color: '#e2e8f0' }}>{value}</span>
        </div>
    );
};

const DetailsPanel = ({ selectedNode, selectedLink, onClear }) => {
    const content = selectedLink
        ? {
              title: selectedLink.relation_type || 'RELATED_TO',
              rows: [
                  ['Source', getEndpointId(selectedLink.source)],
                  ['Target', getEndpointId(selectedLink.target)],
                  ['Weight', Number(selectedLink.weight || 1).toFixed(2)],
                  ['Confidence', Number(selectedLink.confidence || 0.5).toFixed(2)],
                  ['Predicate', selectedLink.predicate],
                  ['Primary evidence', selectedLink.evidence_sentence],
                  ['Source docs', (selectedLink.source_docs || []).join(', ')],
              ],
              evidenceList: selectedLink.evidence_sentences || [],
          }
        : selectedNode
          ? {
                title: selectedNode.title || selectedNode.id,
                rows: [
                    ['ID', selectedNode.id],
                    ['Type', selectedNode.type],
                    ['Mentions', selectedNode.count],
                    ['Confidence', selectedNode.confidence],
                    ['Degree centrality', selectedNode.degree_centrality],
                    ['Bridge score', selectedNode.betweenness],
                    ['PageRank', selectedNode.pagerank],
                    ['Community', selectedNode.community],
                    ['Aliases', (selectedNode.aliases || []).join(', ')],
                    ['Text preview', selectedNode.text_preview],
                ],
                evidenceList: [],
            }
          : null;

    if (!content) return null;

    return (
        <div
            className="glass-panel"
            style={{
                position: 'absolute',
                right: '20px',
                bottom: '20px',
                width: '380px',
                zIndex: 25,
                maxHeight: '42vh',
                overflowY: 'auto',
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h2 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc' }}>{content.title}</h2>
                <button
                    onClick={onClear}
                    style={{
                        width: 'auto',
                        padding: '4px 10px',
                        fontSize: '0.75rem',
                        background: 'rgba(239,68,68,0.18)',
                        border: '1px solid rgba(239,68,68,0.35)',
                    }}
                >
                    CLOSE
                </button>
            </div>

            {content.rows.map(([label, value]) => (
                <Row key={label} label={label} value={value} />
            ))}

            {content.evidenceList.length > 0 && (
                <div style={{ marginTop: '12px' }}>
                    <strong style={{ color: '#cbd5e1' }}>Evidence snippets:</strong>
                    <ul style={{ margin: '8px 0 0 18px', padding: 0, color: '#cbd5e1' }}>
                        {content.evidenceList.slice(0, 4).map((entry, index) => (
                            <li key={`${entry}-${index}`} style={{ marginBottom: '6px', lineHeight: 1.35 }}>
                                {entry}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default DetailsPanel;
