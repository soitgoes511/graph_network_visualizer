import React, { useRef, useEffect, useCallback } from 'react';
import ForceGraph3D from 'react-force-graph-3d';

const GraphVisualizer = ({ graphData }) => {
    const fgRef = useRef();

    // Resize handler? ForceGraph3D handles full screen by default if no width/height prop

    const handleNodeClick = useCallback(node => {
        // Aim at node from outside it
        const distance = 40;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);

        if (fgRef.current) {
            fgRef.current.cameraPosition(
                { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, // new position
                node, // lookAt ({ x, y, z })
                3000  // ms transition duration
            );
        }

        // Also try to open URL if it's a web/external type
        if (node.id.startsWith('http')) {
            window.open(node.id, '_blank');
        }
    }, [fgRef]);

    // Custom node color
    const getNodeColor = (node) => {
        switch (node.type) {
            case 'web': return '#38bdf8'; // Sky blue
            case 'file': return '#a855f7'; // Purple
            case 'external': return '#f472b6'; // Pink
            default: return '#94a3b8'; // Slate
        }
    };

    return (
        <div style={{ width: '100%', height: '100vh', position: 'fixed', top: 0, left: 0, zIndex: 0 }}>
            {graphData && graphData.nodes.length > 0 ? (
                <ForceGraph3D
                    ref={fgRef}
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
