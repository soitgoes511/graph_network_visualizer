import React, { useRef, useEffect, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';

const GraphVisualizer = ({ graphData }) => {
    const fgRef = useRef();
    const [dimensions, setDimensions] = React.useState({ width: window.innerWidth, height: window.innerHeight });

    useEffect(() => {
        const handleResize = () => {
            setDimensions({ width: window.innerWidth, height: window.innerHeight });
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const handleNodeClick = useCallback(node => {
        // ... (existing click handler)
        const distance = 40;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

        if (fgRef.current) {
            fgRef.current.cameraPosition(
                { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
                node,
                3000
            );
        }

        if (node.id.startsWith('http')) {
            window.open(node.id, '_blank');
        }
    }, [fgRef]);

    const getNodeColor = (node) => {
        if (node.type === 'concept') return '#facc15'; // Yellow
        if (node.type === 'PERSON') return '#fb923c'; // Orange
        if (node.type === 'ORG') return '#ef4444'; // Red
        if (node.type === 'GPE') return '#22c55e'; // Green

        switch (node.type) {
            case 'web': return '#38bdf8';
            case 'file': return '#a855f7';
            case 'external': return '#f472b6';
            default: return '#94a3b8'; // gray for others
        }
    };

    return (
        <div style={{ width: '100vw', height: '100vh', position: 'fixed', top: 0, left: 0, zIndex: 0, overflow: 'hidden' }}>
            {graphData && graphData.nodes.length > 0 ? (
                <ForceGraph3D
                    ref={fgRef}
                    width={dimensions.width}
                    height={dimensions.height}
                    graphData={graphData}
                    nodeLabel="title"
                    nodeColor={getNodeColor}
                    nodeVal={node => node.val || 1}
                    linkColor={() => 'rgba(255,255,255,0.2)'}
                    onNodeClick={handleNodeClick}
                    backgroundColor="#0f172a"
                    showNavInfo={false}
                />
            ) : (
                <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                    color: '#334155',
                    flexDirection: 'column'
                }}>
                    <p style={{ fontSize: '2rem', fontWeight: 300 }}>Upload documents or enter URLs to begin</p>
                </div>
            )}
        </div>
    );
};

export default GraphVisualizer;
