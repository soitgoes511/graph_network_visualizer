import React, { useRef, useState } from 'react';

const InputPanel = ({
    onProcess,
    loading,
    loadingMore = false,
    onToggleLogs,
    unreadLogs = 0,
    onExport,
    onImport,
    onLoadMore,
    onResetAll,
    canLoadMore = false,
    graphMeta = null,
    rootNodes = [],
    selectedFilters = [],
    onFilterChange,
}) => {
    const [urls, setUrls] = useState([]);
    const [currentUrl, setCurrentUrl] = useState('');
    const [depth, setDepth] = useState(1);
    const [files, setFiles] = useState([]);
    const fileInputRef = useRef(null);

    const handleAddUrl = () => {
        if (currentUrl && !urls.includes(currentUrl)) {
            setUrls([...urls, currentUrl]);
            setCurrentUrl('');
        }
    };

    const handleKeyDown = (event) => {
        if (event.key === 'Enter') {
            handleAddUrl();
        }
    };

    const removeUrl = (urlToRemove) => {
        setUrls(urls.filter((url) => url !== urlToRemove));
    };

    const handleFileChange = (event) => {
        if (event.target.files) {
            setFiles(Array.from(event.target.files));
        }
    };

    const handleSubmit = () => {
        if (urls.length === 0 && files.length === 0) return;
        onProcess({ urls, files, depth });
    };

    return (
        <div className="glass-panel overlay">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h1 style={{ fontSize: '1.2rem', margin: 0 }}>Network Xplore</h1>
                <button
                    onClick={onToggleLogs}
                    style={{
                        width: 'auto',
                        padding: '4px 8px',
                        fontSize: '0.8rem',
                        background: 'rgba(255,255,255,0.1)',
                        border: '1px solid rgba(255,255,255,0.2)',
                    }}
                    title="Toggle System Logs"
                >
                    LOGS{unreadLogs > 0 ? ` (${unreadLogs})` : ''}
                </button>
            </div>

            <div className="form-group">
                <label>Website URLs</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                        type="text"
                        value={currentUrl}
                        onChange={(event) => setCurrentUrl(event.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="https://example.com/wiki"
                    />
                    <button onClick={handleAddUrl} style={{ width: 'auto' }}>
                        +
                    </button>
                </div>

                {urls.length > 0 && (
                    <ul style={{ listStyle: 'none', padding: 0, marginTop: '8px' }}>
                        {urls.map((url, index) => (
                            <li
                                key={index}
                                style={{
                                    background: 'rgba(255,255,255,0.1)',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                    marginBottom: '4px',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    fontSize: '0.85rem',
                                }}
                            >
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '240px' }}>{url}</span>
                                <span onClick={() => removeUrl(url)} style={{ cursor: 'pointer', color: '#ef4444', marginLeft: '8px' }}>
                                    x
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="form-group">
                <label>Crawl Depth ({depth})</label>
                <input
                    type="range"
                    min="1"
                    max="4"
                    value={depth}
                    onChange={(event) => setDepth(parseInt(event.target.value, 10))}
                    style={{ width: '100%' }}
                />
            </div>

            <div className="form-group">
                <label>Documents (PDF, DOCX)</label>
                <input
                    type="file"
                    multiple
                    accept=".pdf,.docx"
                    onChange={handleFileChange}
                    ref={fileInputRef}
                    style={{ display: 'block' }}
                />
                {files.length > 0 && (
                    <div style={{ marginTop: '4px', fontSize: '0.85rem', color: '#94a3b8' }}>{files.length} file(s) selected</div>
                )}
            </div>

            <button onClick={handleSubmit} disabled={loading || (urls.length === 0 && files.length === 0)}>
                {loading ? <div className="spinner"></div> : 'VISUALIZE NETWORK'}
            </button>

            {rootNodes && rootNodes.length > 0 && (
                <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '10px' }}>
                    <label style={{ marginBottom: '8px', display: 'block' }}>Filter by Source</label>
                    <div
                        style={{
                            maxHeight: '150px',
                            overflowY: 'auto',
                            background: 'rgba(0,0,0,0.2)',
                            padding: '8px',
                            borderRadius: '4px',
                        }}
                    >
                        {Object.entries(
                            rootNodes.reduce((accumulator, node) => {
                                if (!accumulator[node.title]) accumulator[node.title] = [];
                                accumulator[node.title].push(node.id);
                                return accumulator;
                            }, {})
                        )
                            .sort((left, right) => left[0].localeCompare(right[0]))
                            .map(([title, ids], groupIndex) => {
                                const checkboxId = `filter-${groupIndex}`;
                                const isChecked = ids.every((id) => selectedFilters.includes(id));
                                return (
                                    <div key={title} style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                                        <input
                                            type="checkbox"
                                            id={checkboxId}
                                            checked={isChecked}
                                            onChange={(event) => {
                                                if (event.target.checked) {
                                                    const newIds = ids.filter((id) => !selectedFilters.includes(id));
                                                    onFilterChange([...selectedFilters, ...newIds]);
                                                } else {
                                                    onFilterChange(selectedFilters.filter((id) => !ids.includes(id)));
                                                }
                                            }}
                                            style={{ marginRight: '8px' }}
                                        />
                                        <label
                                            htmlFor={checkboxId}
                                            style={{ fontSize: '0.85rem', cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                                            title={title}
                                        >
                                            {title}
                                        </label>
                                    </div>
                                );
                            })}
                    </div>
                    {selectedFilters.length > 0 && (
                        <button
                            onClick={() => onFilterChange([])}
                            style={{
                                marginTop: '8px',
                                padding: '4px',
                                fontSize: '0.8rem',
                                background: 'transparent',
                                border: '1px solid rgba(255,255,255,0.2)',
                            }}
                        >
                            Clear Filters
                        </button>
                    )}
                </div>
            )}

            <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '10px' }}>
                <label style={{ marginBottom: '8px', display: 'block' }}>Manage Graph</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={onExport} style={{ flex: 1, fontSize: '0.85rem' }}>
                        Save JSON
                    </button>
                    <label
                        style={{
                            flex: 1,
                            fontSize: '0.85rem',
                            background: 'rgba(255,255,255,0.1)',
                            textAlign: 'center',
                            padding: '10px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            border: '1px solid rgba(255,255,255,0.1)',
                            transition: 'all 0.2s',
                        }}
                        className="file-upload-btn"
                    >
                        Load JSON
                        <input
                            type="file"
                            accept=".json"
                            onChange={(event) => {
                                if (event.target.files?.[0]) onImport(event.target.files[0]);
                            }}
                            style={{ display: 'none' }}
                        />
                    </label>
                </div>

                {graphMeta && (graphMeta.total_nodes || graphMeta.total_links) && (
                    <div style={{ marginTop: '10px', fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.4 }}>
                        <div>
                            Showing {graphMeta.visible_nodes || 0}/{graphMeta.total_nodes || 0} nodes and {graphMeta.visible_links || 0}/
                            {graphMeta.total_links || 0} links.
                        </div>
                        {canLoadMore && (
                            <button
                                onClick={onLoadMore}
                                disabled={loading || loadingMore}
                                style={{
                                    marginTop: '8px',
                                    padding: '8px',
                                    fontSize: '0.8rem',
                                    background: 'rgba(15,23,42,0.7)',
                                    border: '1px solid rgba(56,189,248,0.35)',
                                }}
                            >
                                {loadingMore ? 'Loading More...' : 'Load More Detail'}
                            </button>
                        )}
                    </div>
                )}

                {onResetAll && (
                    <button
                        onClick={() => {
                            const confirmed = window.confirm('Clear current graph, inputs, filters, and logs?');
                            if (confirmed) onResetAll();
                        }}
                        disabled={loading || loadingMore}
                        style={{
                            marginTop: '10px',
                            padding: '8px',
                            fontSize: '0.8rem',
                            background: 'rgba(239,68,68,0.15)',
                            border: '1px solid rgba(239,68,68,0.35)',
                        }}
                    >
                        New Search (Clear All)
                    </button>
                )}
            </div>

            <div style={{ marginTop: '20px', fontSize: '0.8rem', color: '#64748b' }}>
                <p>Supports: Recursive crawling, PDF/DOCX parsing.</p>
                <p>Left Click node: Focus + open URL | Left Click edge: Inspect relationship</p>
            </div>
        </div>
    );
};

export default InputPanel;
