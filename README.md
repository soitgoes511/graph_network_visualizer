# Graph Network Visualizer

An interactive graph exploration app that crawls URLs and/or ingests PDF/DOCX/XLSX/XLS/HTML/XML files, extracts entities/concepts/relationships with NLP, and visualizes results in a 3D network.

## Highlights

- Recursive web crawling with internal/external link classification.
- PDF, DOCX, XLSX/XLS, HTML, and XML parsing with extracted links and text.
- Rich edge metadata: relation type, weight, confidence, predicate, evidence, source docs.
- NLP extraction for concepts, normalized entities, sentence co-occurrence, and verb-driven relations.
- Graph insights: bridge nodes, communities, relation distribution, shortest path between entities.
- Progressive loading for large graphs: fast high-signal preview first, then `Load More Detail`.
- Real-time system logs over WebSocket with hide/show controls and unread counters.
- One-click `New Search (Clear All)` reset without page refresh.
- Docker and Podman support.

## Recent Improvements

- Added deeper node/edge intelligence and relationship evidence.
- Added details and insights side panels.
- Added shortest-path workflow between extracted entities.
- Improved NLP performance via batched processing.
- Improved graph-build performance with adaptive analytics:
  - exact metrics for small graphs,
  - approximations for medium graphs,
  - safe fallbacks for very large graphs.
- Added progressive graph view endpoint (`/graph_view`) with in-memory cache.
- Fixed duplicate log behavior from overlapping WebSocket reconnect flows.
- Improved log UX (dock positioning, recoverable hide/unhide).

## Tech Stack

- Backend: FastAPI, NetworkX, spaCy, BeautifulSoup4, requests, pypdf, python-docx
- Frontend: React + Vite, `react-force-graph-3d`
- Containers: Docker / Podman Compose

## Run Locally (Container)

### Prerequisites

- Docker Desktop or Podman
- Git

### Start

```bash
git clone https://github.com/soitgoes511/graph_network_visualizer.git
cd graph_network_visualizer

# Docker
docker-compose up --build

# Podman
podman compose up --build
```

### Access

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`

## Configuration

`docker-compose.yml` sets:

- `VITE_API_URL=http://localhost:8000`
- `VITE_WS_URL=ws://localhost:8000/ws/logs`

You can override these for remote deployments.

## Application Flow

1. Add one or more URLs and/or upload PDF/DOCX/XLSX/XLS/HTML/XML files.
2. Choose crawl depth (`1` to `4`).
3. Click `VISUALIZE NETWORK`.
4. App returns an initial high-interest graph preview quickly.
5. Use `Load More Detail` to incrementally expand nodes/edges.
6. Explore:
   - Left-click node: focus camera, open URL nodes in new tab.
   - Left-click edge: inspect relationship metadata.
   - Use Insights panel for bridge nodes, communities, edge-type counts, shortest path.
7. Click `New Search (Clear All)` to fully reset without refreshing.

## API Summary

### `POST /process`

Form fields:

- `urls` (JSON array string, optional)
- `files` (multipart files, optional, PDF/DOCX/XLSX/XLS/HTML/XML)
- `depth` (int, default `1`, max `4`)
- `node_limit` (int, initial preview cap)
- `link_limit` (int, initial preview cap)

Returns:

- `nodes`
- `links`
- `insights`
- `meta`:
  - `query_id`
  - `visible_nodes`, `visible_links`
  - `total_nodes`, `total_links`
  - `node_limit`, `link_limit`
  - `truncated`
  - `load_more_node_step`, `load_more_link_step`

### `POST /graph_view`

Expands or reshapes the view from cached processed data without re-running scrape/NLP.

JSON body:

- `query_id` (required)
- `node_limit` (optional)
- `link_limit` (optional)

Returns same structure as `/process` (`nodes`, `links`, `insights`, `meta`).

### `GET /ws/logs`

WebSocket stream for real-time processing logs.

### `POST /save_graph` and `GET /load_graph`

Save/load graph JSON snapshots.

## Performance Notes

- Initial render now prioritizes high-interest nodes/edges for faster interaction.
- NLP is batched (`nlp.pipe`) to reduce per-document overhead.
- Graph analytics are adaptive for scale:
  - bridge/community/ranking algorithms use smaller-cost paths on larger graphs.
- `Load More Detail` increases graph scope incrementally, reducing long blocking waits.

## Development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Validation Commands

```bash
python -m compileall backend
python backend/test_nlp_simple.py
cd frontend && npm run lint && npm run build
```

## Notes and Limits

- Progressive graph cache is in-memory (not persistent) and limited in size by backend constants.
- Imported JSON graphs can be explored normally, but `Load More Detail` depends on active backend cache from a `/process` run.

## License

MIT
