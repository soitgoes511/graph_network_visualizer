from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import asyncio
from scraper import scrape_url
from parser import parse_pdf, parse_docx
from graph_builder import build_graph_from_data
from nlp_processor import process_text

SAVE_FILE_PATH = "saved_graph.json"

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
                        "full_text": file_data["text"], # Store for NLP
                        "val": 10 
                    })
                    
                    # Create links
                    for link in file_data["links"]:
                        all_nodes.append({"id": link, "title": link, "type": "external", "val": 5})
                        all_links.append({"source": file_node_id, "target": link})
            except Exception as e:
                 log_callback(f"Error processing file {file.filename}: {e}")
                 print(f"Error processing file {file.filename}: {e}")

    # 3. NLP Extraction (CPU bound)
    log_callback("Running NLP analysis on content...")
    nlp_nodes = []
    nlp_links = []
    
    # helper to process text and add nodes
    def extract_nlp_data(source_id, text):
        if not text: return
        analysis = process_text(text)
        
        # Add Concepts
        for concept in analysis["concepts"]:
            concept_id = f"concept:{concept['text']}"
            if concept_id not in [n["id"] for n in nlp_nodes]:
                 nlp_nodes.append({
                     "id": concept_id,
                     "title": concept["text"],
                     "type": "concept",
                     "val": 3 + (concept["count"] * 0.5) # Scale size by frequency
                 })
            nlp_links.append({"source": source_id, "target": concept_id})
            
        # Add Entities
        for ent in analysis["entities"]:
            ent_id = f"entity:{ent['text']}"
            if ent_id not in [n["id"] for n in nlp_nodes]:
                 nlp_nodes.append({
                     "id": ent_id,
                     "title": ent["text"],
                     "type": ent["type"], # PERSON, ORG, etc.
                     "val": 5
                 })
            nlp_links.append({"source": source_id, "target": ent_id})

    # Process URL nodes
    for node in all_nodes:
        if node.get("type") == "web" and "text" in node:
            # For web nodes, 'text' field currently holds the content (up to 50k chars)
            # scraper.py was modified to put content in 'text'
            await loop.run_in_executor(None, extract_nlp_data, node["id"], node["text"])
            
    # Process File nodes
    for node in all_nodes:
        if node.get("type") == "file" and "full_text" in node:
             await loop.run_in_executor(None, extract_nlp_data, node["id"], node["full_text"])
    
    all_nodes.extend(nlp_nodes)
    all_links.extend(nlp_links)

    # 4. Build Graph (Blocking)
    log_callback("Building graph network...")
    graph_data = await loop.run_in_executor(None, build_graph_from_data, all_nodes, all_links)
    
    log_callback(f"Processing complete. Graph has {len(graph_data['nodes'])} nodes and {len(graph_data['links'])} links.")
    return graph_data

class GraphData(BaseModel):
    nodes: List[dict]
    links: List[dict]

@app.post("/save_graph")
async def save_graph(data: GraphData):
    try:
        with open(SAVE_FILE_PATH, "w") as f:
            json.dump(data.model_dump(), f)
        return {"message": "Graph saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/load_graph")
async def load_graph():
    try:
        with open(SAVE_FILE_PATH, "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No saved graph found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
