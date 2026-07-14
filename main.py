import os
import time
import json
import requests
import zipfile
import io
import shutil
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

import chunker
from vector_store import VectorStore

app = FastAPI(title="DevRAG Code Chatbot")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize vector store
db_path = os.path.join(os.path.dirname(__file__), "vector_store.db")
vector_store = VectorStore(db_path=db_path)

# Global indexing status
indexing_status = {
    "status": "idle",  # idle, indexing
    "total_files": 0,
    "processed_files": 0,
    "total_chunks": 0,
    "message": ""
}

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    allowed_files: Optional[List[str]] = None  # Filter context to these files

def bg_index_folder(folder_path: str):
    global indexing_status
    indexing_status["status"] = "indexing"
    indexing_status["processed_files"] = 0
    indexing_status["total_files"] = 0
    indexing_status["total_chunks"] = 0
    
    try:
        if not os.path.exists(folder_path):
            indexing_status["status"] = "idle"
            indexing_status["message"] = f"Error: Path {folder_path} does not exist."
            return
            
        indexing_status["message"] = "Scanning workspace files..."
        all_files = chunker.scan_directory(folder_path)
        indexing_status["total_files"] = len(all_files)
        
        # Clean up database files that were deleted in the workspace
        rel_files = [os.path.relpath(f, folder_path).replace('\\', '/') for f in all_files]
        vector_store.delete_removed_files(rel_files)
        
        for idx, file_path in enumerate(all_files):
            rel_path = os.path.relpath(file_path, folder_path).replace('\\', '/')
            indexing_status["message"] = f"Indexing: {rel_path}"
            
            try:
                mtime = os.path.getmtime(file_path)
                
                # Check if file has changed
                if not vector_store.is_file_up_to_date(rel_path, mtime):
                    # Chunk the file
                    file_chunks = chunker.chunk_file(file_path, folder_path)
                    vector_store.add_file_chunks(rel_path, mtime, file_chunks)
                    indexing_status["total_chunks"] += len(file_chunks)
                    
            except Exception as e:
                print(f"Failed to index file {file_path}: {e}")
                
            indexing_status["processed_files"] = idx + 1
            
        indexing_status["status"] = "idle"
        indexing_status["message"] = "Indexing completed successfully!"
    except Exception as e:
        indexing_status["status"] = "idle"
        indexing_status["message"] = f"Error during indexing: {str(e)}"

@app.post("/api/scan")
def scan_folder(payload: dict, background_tasks: BackgroundTasks):
    folder_path = payload.get("path", "").strip()
    if not folder_path or folder_path == ".":
        folder_path = os.getcwd()
    else:
        folder_path = os.path.abspath(folder_path)
    
    # Run indexing in the background
    background_tasks.add_task(bg_index_folder, folder_path)
    return {"message": f"Indexing started for path: {folder_path}"}

@app.post("/api/github-import")
def github_import(payload: dict, background_tasks: BackgroundTasks):
    repo_url = payload.get("url", "").strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="Missing repository URL")
    
    global indexing_status
    indexing_status["status"] = "indexing"
    indexing_status["message"] = "Downloading repository from GitHub..."
    indexing_status["processed_files"] = 0
    indexing_status["total_files"] = 0
    indexing_status["total_chunks"] = 0
    
    try:
        # Clean and parse URL
        url = repo_url.strip().rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        parts = url.split("github.com/")
        if len(parts) < 2:
            raise Exception("Invalid GitHub URL. Must be like https://github.com/owner/repo")
        
        repo_path = parts[1]
        path_parts = repo_path.split("/")
        if len(path_parts) < 2:
            raise Exception("Invalid GitHub URL. Must contain owner and repository name.")
        
        owner, repo = path_parts[0], path_parts[1]
        
        # Download ZIP using redirect API
        download_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
        headers = {"User-Agent": "DevRAG-Code-Companion"}
        response = requests.get(download_url, headers=headers, timeout=60)
        if response.status_code != 200:
            raise Exception(f"Failed to download repository: HTTP {response.status_code}")
        
        # Extract to target workspace directory
        target_dir = os.path.join(os.path.dirname(__file__), "github_repos", f"{owner}_{repo}")
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)
        
        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data) as zip_ref:
            zip_ref.extractall(target_dir)
        
        # Find inner GitHub zip folder name (e.g., owner-repo-hash)
        root_folders = [f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))]
        if root_folders:
            extracted_root = os.path.join(target_dir, root_folders[0])
        else:
            extracted_root = target_dir
            
        # Trigger background indexing on the extracted repository
        background_tasks.add_task(bg_index_folder, extracted_root)
        return {"message": "GitHub Repository downloaded successfully. Indexing started.", "repo_name": f"{owner}/{repo}"}
        
    except Exception as e:
        indexing_status["status"] = "idle"
        indexing_status["message"] = f"Error during GitHub import: {str(e)}"
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
def get_status():
    return indexing_status

@app.get("/api/files")
def get_files():
    try:
        files = vector_store.get_all_files()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    message = request.message
    allowed_files = request.allowed_files
    
    # 1. Query vector store for related code snippets
    # If the user asks about specific files, we filter vector search to those files
    related_chunks = []
    try:
        related_chunks = vector_store.search_similar(message, top_k=5, allowed_files=allowed_files)
    except Exception as e:
        print(f"Error searching vector store: {e}")
        
    # 2. Build system context and prompt
    context_str = ""
    if related_chunks:
        context_str = "\n\nUse the following relevant code snippets as context to answer the query:\n"
        for chunk in related_chunks:
            context_str += f"\n---\nFile: {chunk['file_path']} (Lines {chunk['start_line']}-{chunk['end_line']})\n"
            context_str += f"```{chunk['language']}\n{chunk['content']}\n```\n"
        context_str += "---\n"
        
    system_prompt = (
        "You are 'Antigravity Code Companion', a highly skilled AI coding assistant. "
        "Your task is to explain code, answer technical questions, explain functions, and parse documentation. "
        "Use the provided code context to answer the questions accurately. "
        "When explaining, be direct, professional, and clear. Always reference the relevant files and line numbers. "
        "If the user requests a short, brief, or point-to-point explanation, provide a highly concise, direct, and simplified answer (using bullet points where appropriate) without verbose background details. "
        "If the user query is a casual greeting, small talk, or friendly conversation (such as 'hii', 'hello', 'hey', 'good to see you', 'how are you', etc.), respond in a brief, friendly, and conversational manner, and DO NOT explain, reference, or summarize the provided code context. "
        "If the user query is gibberish, a keyboard smash (such as 'hjb', 'gyhj', 'lkjsn', etc.), or completely nonsensical, do NOT explain the code context and ask them politely to clarify. "
        "If the context doesn't contain enough information to answer, state that, but still try to give a helpful explanation if possible."
    )
    
    # 3. Format history and current prompt for Ollama chat
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Append user question with context
    user_prompt = f"{message}{context_str}"
    messages.append({"role": "user", "content": user_prompt})
    
    # 4. Stream response from local Ollama or Gemini API
    def generate_gemini_stream():
        api_key = os.environ.get("GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?key={api_key}"
        
        contents = []
        system_instruction_text = ""
        for msg in messages:
            if msg["role"] == "system":
                system_instruction_text = msg["content"]
            elif msg["role"] == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })
            else:
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}]
                })
                
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2
            }
        }
        if system_instruction_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction_text}]
            }
            
        try:
            response = requests.post(url, json=payload, stream=True, timeout=60)
            if response.status_code != 200:
                yield f"data: {json.dumps({'error': f'Gemini returned status {response.status_code}'})}\n\n"
                return
                
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8').strip()
                    if decoded.startswith("["):
                        decoded = decoded[1:]
                    if decoded.startswith(","):
                        decoded = decoded[1:]
                    if decoded.endswith("]"):
                        decoded = decoded[:-1]
                    decoded = decoded.strip()
                    if not decoded:
                        continue
                    try:
                        data = json.loads(decoded)
                        text_chunk = data["candidates"][0]["content"]["parts"][0]["text"]
                        yield f"data: {json.dumps({'content': text_chunk})}\n\n"
                    except Exception as e:
                        pass
        except Exception as e:
            yield f"data: {json.dumps({'error': f'Failed to contact Gemini: {str(e)}'})}\n\n"

    def generate_ollama_stream():
        ollama_url = "http://localhost:11434/api/chat"
        payload = {
            "model": "qwen2.5-coder:1.5b",
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.2
            }
        }
        
        try:
            response = requests.post(ollama_url, json=payload, stream=True, timeout=60)
            if response.status_code != 200:
                yield f"data: {json.dumps({'error': f'Ollama returned status {response.status_code}'})}\n\n"
                return
                
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    data = json.loads(decoded)
                    chunk_content = data.get("message", {}).get("content", "")
                    yield f"data: {json.dumps({'content': chunk_content})}\n\n"
                    if data.get("done", False):
                        break
        except Exception as e:
            yield f"data: {json.dumps({'error': f'Failed to contact Ollama: {str(e)}'})}\n\n"
            
    if os.environ.get("GEMINI_API_KEY"):
        return StreamingResponse(generate_gemini_stream(), media_type="text/event-stream")
    else:
        return StreamingResponse(generate_ollama_stream(), media_type="text/event-stream")

# Serve UI static files
# Make sure static directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    # Serve index.html statically
    index_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_file):
        with open(index_file, 'r', encoding='utf-8') as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h2>index.html not found in static/ directory</h2>")
