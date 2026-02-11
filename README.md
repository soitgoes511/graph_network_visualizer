# Graph Network Visualizer

A single-page data application that visualizes relationships between website links and documents (PDFs, DOCX) as an interactive 3D graph network.

## Features

- **Recursive URL Scraping**: Crawl a website starting from a URL up to a specified depth.
- **Document Analysis**: Upload PDF and DOCX files to extract text and links.
- **Interactive Visualization**: Explore the network using a 3D force-directed graph.
- **Real-time Logging**: Monitor the scraping and parsing process with live logs.
- **Containerized**: Fully Dockerized for easy deployment.

## Tech Stack

- **Backend**: Python (FastAPI), BeautifulSoup4, NetworkX, PyPDF, Python-Docx
- **Frontend**: React (Vite), React Force Graph 3D, Glassmorphism UI
- **Infrastructure**: Docker, Docker Compose

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) or [Podman](https://podman.io/)

### Running the Application

1. Clone the repository:
   ```bash
   git clone https://github.com/soitgoes511/graph_network_visualizer.git
   cd graph_network_visualizer
   ```

2. Start the application using Docker Compose:
   ```bash
   docker-compose up --build
   # OR with Podman
   podman compose up --build
   ```

3. Access the application:
   - Frontend: [http://localhost:5173](http://localhost:5173)
   - Backend API: [http://localhost:8000](http://localhost:8000)

## Usage

1. Open the frontend in your browser.
2. **Web Crawling**: Enter a URL (e.g., a Wikipedia page) and click `+` to add it. Set the crawl depth (1-3).
3. **Document Parsing**: Click "Choose Files" to upload PDFs or DOCX files.
4. Click **VISUALIZE NETWORK** to start processing.
5. Watch the **LOGS** window for progress updates.
6. Interact with the 3D graph:
   - **Left Click**: Open the node's URL.
   - **Right Click**: Focus on the node.
   - **Drag/Scroll**: Rotate and zoom the camera.

## License

MIT
