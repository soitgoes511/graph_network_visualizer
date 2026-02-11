import React, { useState, useEffect, useRef } from 'react';
import InputPanel from './components/InputPanel';
import GraphVisualizer from './components/GraphVisualizer';
import LogTerminal from './components/LogTerminal';

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
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
    } catch (error) {
      console.error('Error processing:', error);
      setLogs(prev => [...prev, `Error: ${error.message}`]);
      alert('Error processing data. Check logs for details.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <GraphVisualizer graphData={graphData} />
      <InputPanel
        onProcess={handleProcess}
        loading={loading}
        onToggleLogs={() => setShowLogs(!showLogs)}
      />
      {showLogs && <LogTerminal logs={logs} onClose={() => setShowLogs(false)} />}
    </div>
  );
}

export default App;
