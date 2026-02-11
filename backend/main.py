from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import asyncio
from scraper import scrape_url
from parser import parse_pdf, parse_docx
from graph_builder import build_graph_from_data

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Broadcast to all connected clients
        # Use copy of list to avoid modification during iteration issues if disconnect happens
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception:
                # Handle dead connections
                pass

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"message": "Graph Network Visualizer API"}

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/process")
async def process_data(
    urls: Optional[str] = Form(None), # JSON string of URLs
    depth: int = Form(1),
    files: List[UploadFile] = File(None)
):
    loop = asyncio.get_running_loop()
    
    # Thread-safe logger
    def log_callback(msg):
        asyncio.run_coroutine_threadsafe(manager.broadcast(msg), loop)

    log_callback("Starting data processing...")

    all_nodes = []
    all_links = []
    
    # 1. Process URLs (Blocking, CPU bound-ish due to network wait but requests is sync)
    if urls:
        try:
            url_list = json.loads(urls)
            for url in url_list:
                if not url.startswith("http"):
                    continue
                
                # Run sync scraper in thread pool
                log_callback(f"Queuing scrape for {url}...")
                data = await loop.run_in_executor(None, scrape_url, url, depth, log_callback)
                all_nodes.extend(data["nodes"])
                all_links.extend(data["links"])
        except Exception as e:
            log_callback(f"Error processing URLs: {e}")
            print(f"Error processing URLs: {e}")

    # 2. Process Files
    # File reading is async, parsing is sync/cpu bound
    if files:
        for file in files:
            try:
                log_callback(f"Reading file: {file.filename}")
                content = await file.read()
                filename = file.filename.lower()
                
                file_data = None
                if filename.endswith(".pdf"):
                    file_data = await loop.run_in_executor(None, parse_pdf, content, log_callback)
                elif filename.endswith(".docx"):
                    file_data = await loop.run_in_executor(None, parse_docx, content, log_callback)
                
                if file_data:
                    # Create a node for the file
                    file_node_id = file.filename
                    # Add file node
                    all_nodes.append({
                        "id": file_node_id, 
                        "title": file.filename, 
                        "type": "file", 
                        "text": file_data["text"][:200] + "...",
                        "val": 10 
                    })
                    
                    # Create links
                    for link in file_data["links"]:
                        all_nodes.append({"id": link, "title": link, "type": "external", "val": 5})
                        all_links.append({"source": file_node_id, "target": link})
            except Exception as e:
                 log_callback(f"Error processing file {file.filename}: {e}")
                 print(f"Error processing file {file.filename}: {e}")

    # 3. Build Graph (Blocking)
    log_callback("Building graph network...")
    graph_data = await loop.run_in_executor(None, build_graph_from_data, all_nodes, all_links)
    
    log_callback(f"Processing complete. Graph has {len(graph_data['nodes'])} nodes and {len(graph_data['links'])} links.")
    return graph_data
