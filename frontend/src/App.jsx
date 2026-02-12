import React, { useState, useEffect, useRef } from 'react';
import InputPanel from './components/InputPanel';
import GraphVisualizer from './components/GraphVisualizer';
import LogTerminal from './components/LogTerminal';

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const [activeFilters, setActiveFilters] = useState([]);
  const ws = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    // Use localhost:8000 for dev. In prod/docker, this should be configurable.
    const wsUrl = 'ws://localhost:8000/ws/logs';

    const connectWs = () => {
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setLogs(prev => [...prev, 'System connected. Ready.']);
        // Auto-show logs on connect so user knows it's working
        setShowLogs(true);
      };

      ws.current.onmessage = (event) => {
        const message = event.data;
        setLogs(prev => [...prev, message]);
        setShowLogs(true);
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected, retrying...');
        setTimeout(connectWs, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connectWs();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const handleProcess = async ({ urls, files, depth }) => {
    setLoading(true);
    setLogs(['Request sent. Waiting for server response...']);
    setShowLogs(true);

    const formData = new FormData();

    if (urls.length > 0) {
      formData.append('urls', JSON.stringify(urls));
    }
    formData.append('depth', depth);

    if (files.length > 0) {
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
    }

    try {
      const response = await fetch('http://localhost:8000/process', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();

      if (!data.nodes) data.nodes = [];
      if (!data.links) data.links = [];

      console.log("Graph Data received:", data);
      setGraphData(data);
      setActiveFilters([]); // Reset filters on new data
    } catch (error) {
      console.error('Error processing:', error);
      setLogs(prev => [...prev, `Error: ${error.message}`]);
      alert('Error processing data. Check logs for details.');
    } finally {
      setLoading(false);
    }
  };

  // --- Export / Import ---
  const handleExport = () => {
    if (!graphData.nodes.length) return;
    // Sanitize data before export:
    // react-force-graph mutates links to be objects {source: Node, target: Node...}
    // We need to convert them back to IDs {source: "id", target: "id"} to avoid issues on reload or circular refs.
    const sanitizedData = {
      nodes: graphData.nodes.map(n => {
        // Create clean copy of node, removing internal visualization props if needed
        // But primarily we just need to preserve the ID and data.
        // Let's just clone it to be safe.
        const { index, x, y, z, vx, vy, vz, ...rest } = n;
        return rest;
      }),
      links: graphData.links.map(l => ({
        source: l.source.id || l.source,
        target: l.target.id || l.target
      }))
    };

    const jsonString = JSON.stringify(sanitizedData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const href = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = href;
    link.download = `graph_network_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(href);
  };

  const handleImport = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target.result);
        if (data.nodes && data.links) {
          setGraphData(data);
          setActiveFilters([]);
          setLogs(prev => [...prev, `Loaded graph from ${file.name}`]);
        } else {
          alert("Invalid graph JSON format");
        }
      } catch (err) {
        console.error(err);
        alert("Failed to parse JSON");
      }
    };
    reader.readAsText(file);
  };

  // --- Filtering ---
  // Identify possible root nodes (URLs and Files)
  const rootNodes = graphData.nodes.filter(n => n.type === 'web' || n.type === 'file');

  const getFilteredGraph = () => {
    if (activeFilters.length === 0) return graphData;

    const selectedSet = new Set(activeFilters);

    // 1. Keep selected root nodes
    const validNodes = new Set(activeFilters);

    // 2. Keep direct neighbors of selected roots
    // Links might be objects (processed by visualizer) or raw IDs. Handle both.
    graphData.links.forEach(link => {
      const sourceId = link.source.id || link.source;
      const targetId = link.target.id || link.target;

      if (selectedSet.has(sourceId)) {
        validNodes.add(targetId);
      } else if (selectedSet.has(targetId)) {
        validNodes.add(sourceId);
      }
    });

    // 3. Filter nodes and links
    const filteredNodes = graphData.nodes.filter(n => validNodes.has(n.id));
    const filteredLinks = graphData.links.filter(link => {
      const sourceId = link.source.id || link.source;
      const targetId = link.target.id || link.target;
      return validNodes.has(sourceId) && validNodes.has(targetId);
    });

    return { nodes: filteredNodes, links: filteredLinks };
  };

  const displayData = getFilteredGraph();

  return (
    <div className="App">
      <GraphVisualizer graphData={displayData} />
      <InputPanel
        onProcess={handleProcess}
        loading={loading}
        onToggleLogs={() => setShowLogs(!showLogs)}
        onExport={handleExport}
        onImport={handleImport}
        rootNodes={rootNodes}
        selectedFilters={activeFilters}
        onFilterChange={setActiveFilters}
      />
      {showLogs && <LogTerminal logs={logs} onClose={() => setShowLogs(false)} />}
    </div>
  );
}

export default App;
