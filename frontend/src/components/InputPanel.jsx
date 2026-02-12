import React, { useState, useRef } from 'react';

const InputPanel = ({
    onProcess,
    loading,
    onToggleLogs,
    onExport,
    onImport,
    rootNodes = [],
    selectedFilters = [],
    onFilterChange
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

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            handleAddUrl();
        }
    };

    const removeUrl = (urlToRemove) => {
        setUrls(urls.filter(u => u !== urlToRemove));
    };

    const handleFileChange = (e) => {
        if (e.target.files) {
            setFiles(Array.from(e.target.files));
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
                        border: '1px solid rgba(255,255,255,0.2)'
                    }}
                    title="Toggle System Logs"
                >
                    LOGS
                </button>
            </div>

            <div className="form-group">
                <label>Website URLs</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                        type="text"
                        value={currentUrl}
                        onChange={(e) => setCurrentUrl(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="https://example.com/wiki"
                    />
                    <button onClick={handleAddUrl} style={{ width: 'auto' }}>+</button>
                </div>

                {urls.length > 0 && (
                    <ul style={{ listStyle: 'none', padding: 0, marginTop: '8px' }}>
                        {urls.map((url, index) => (
                            <li key={index} style={{ background: 'rgba(255,255,255,0.1)', padding: '4px 8px', borderRadius: '4px', marginBottom: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem' }}>
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '240px' }}>{url}</span>
                                <span onClick={() => removeUrl(url)} style={{ cursor: 'pointer', color: '#ef4444', marginLeft: '8px' }}>×</span>
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
                    max="3"
                    value={depth}
                    onChange={(e) => setDepth(parseInt(e.target.value))}
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
                    <div style={{ marginTop: '4px', fontSize: '0.85rem', color: '#94a3b8' }}>
                        {files.length} file(s) selected
                    </div>
                )}
            </div>

            <button onClick={handleSubmit} disabled={loading || (urls.length === 0 && files.length === 0)}>
                {loading ? <div className="spinner"></div> : 'VISUALIZE NETWORK'}
            </button>

            {/* Filter Section */}
            {rootNodes && rootNodes.length > 0 && (
                <div style={{ marginTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '10px' }}>
                    <label style={{ marginBottom: '8px', display: 'block' }}>Filter by Source</label>
                    <div style={{
                        maxHeight: '150px',
                        overflowY: 'auto',
                        background: 'rgba(0,0,0,0.2)',
                        padding: '8px',
                        borderRadius: '4px'
                    }}>
                        {/* Group nodes by title and sort alphabetically */
                            Object.entries(rootNodes.reduce((acc, node) => {
                                if (!acc[node.title]) acc[node.title] = [];
                                acc[node.title].push(node.id);
                                return acc;
                            }, {}))
                                .sort((a, b) => a[0].localeCompare(b[0]))
                                .map(([title, ids]) => {
                                    const isChecked = ids.every(id => selectedFilters.includes(id));
                                    return (
                                        <div key={title} style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                                            <input
                                                type="checkbox"
                                                id={`filter-${title}`}
                                                checked={isChecked}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        const newIds = ids.filter(id => !selectedFilters.includes(id));
                                                        onFilterChange([...selectedFilters, ...newIds]);
                                                    } else {
                                                        onFilterChange(selectedFilters.filter(id => !ids.includes(id)));
                                                    }
                                                }}
                                                style={{ marginRight: '8px' }}
                                            />
                                            <label
                                                htmlFor={`filter-${title}`}
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
                                border: '1px solid rgba(255,255,255,0.2)'
                            }}
                        >
                            Clear Filters
                        </button>
                    )}
                </div>
            )}

            {/* Data Management Section */}
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
                            transition: 'all 0.2s'
                        }}
                        className="file-upload-btn"
                    >
                        Load JSON
                        <input
                            type="file"
                            accept=".json"
                            onChange={(e) => {
                                if (e.target.files?.[0]) onImport(e.target.files[0]);
                            }}
                            style={{ display: 'none' }}
                        />
                    </label>
                </div>
            </div>

            <div style={{ marginTop: '20px', fontSize: '0.8rem', color: '#64748b' }}>
                <p>Supports: Recursive crawling, PDF/DOCX parsing.</p>
                <p>Left Click: Open Link | Right Click: Focus</p>
            </div>
        </div>
    );
};

export default InputPanel;
