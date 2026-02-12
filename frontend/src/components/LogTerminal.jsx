import React, { useEffect, useRef } from 'react';

const LogTerminal = ({ logs, onClose }) => {
    const endRef = useRef(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div
            className="glass-panel"
            style={{
                position: 'absolute',
                left: '50%',
                bottom: '20px',
                transform: 'translateX(-50%)',
                width: 'min(760px, 72vw)',
                height: '220px',
                zIndex: 18,
                display: 'flex',
                flexDirection: 'column',
                padding: '0',
                overflow: 'hidden',
            }}
        >
            <div
                style={{
                    padding: '8px 16px',
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                    background: 'rgba(0,0,0,0.2)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}
            >
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8' }}>SYSTEM LOGS</span>
                <span onClick={onClose} style={{ cursor: 'pointer', color: '#ef4444' }}>
                    x
                </span>
            </div>
            <div
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '12px',
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    color: '#e2e8f0',
                }}
            >
                {logs.map((log, index) => (
                    <div key={index} style={{ marginBottom: '4px' }}>
                        <span style={{ color: '#38bdf8', marginRight: '8px' }}>&gt;</span>
                        {log}
                    </div>
                ))}
                <div ref={endRef} />
            </div>
        </div>
    );
};

export default LogTerminal;
