import os
import sqlite3
import json
import urllib.request
import math
import time

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

def get_embedding(text):
    """
    Generates embeddings. Uses Gemini API if GEMINI_API_KEY is in env, otherwise falls back to local Ollama.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {
                "parts": [{"text": text}]
            }
        }
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    return res_data.get("embedding", {}).get("values")
            except Exception as e:
                if attempt == 2:
                    print(f"Gemini embedding error: {e}")
                    raise e
                time.sleep(2)
        return None

    # Fallback to local Ollama
    payload = {
        "model": EMBEDDING_MODEL,
        "prompt": text
    }
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                OLLAMA_EMBED_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data.get("embedding")
        except Exception as e:
            if attempt == 2:
                print(f"Ollama embedding error: {e}")
                raise e
            time.sleep(2)
    return None

class VectorStore:
    def __init__(self, db_path="vector_store.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Create files table to cache modification times
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indexed_files (
                    file_path TEXT PRIMARY KEY,
                    last_modified REAL
                )
            """)
            # Create chunks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    content TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    language TEXT,
                    embedding TEXT,
                    FOREIGN KEY(file_path) REFERENCES indexed_files(file_path) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def is_file_up_to_date(self, file_path, current_mtime):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_modified FROM indexed_files WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            if not row:
                return False
            db_mtime = row[0]
            
            # Ensure we actually have chunks for this file
            cursor.execute("SELECT COUNT(*) FROM chunks WHERE file_path = ?", (file_path,))
            chunk_count = cursor.fetchone()[0]
            if chunk_count == 0:
                return False
                
            return db_mtime == current_mtime

    def add_file_chunks(self, file_path, mtime, chunks):
        """
        Saves chunks and their embeddings, updating the last modified timestamp.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Delete old chunks for this file first
            cursor.execute("DELETE FROM chunks WHERE file_path = ?", (file_path,))
            
            # Insert file mtime
            cursor.execute(
                "INSERT OR REPLACE INTO indexed_files (file_path, last_modified) VALUES (?, ?)",
                (file_path, mtime)
            )
            
            # Embed and insert chunks
            for chunk in chunks:
                try:
                    embedding = get_embedding(chunk["content"])
                    if embedding:
                        cursor.execute(
                            """
                            INSERT INTO chunks (file_path, content, start_line, end_line, language, embedding)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                chunk["file_path"],
                                chunk["content"],
                                chunk["start_line"],
                                chunk["end_line"],
                                chunk["language"],
                                json.dumps(embedding)
                            )
                        )
                except Exception as e:
                    print(f"Skipping chunk insertion due to embedding failure: {e}")
                    continue
            conn.commit()

    def get_all_files(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM indexed_files")
            return [row[0] for row in cursor.fetchall()]

    def delete_removed_files(self, existing_files):
        """
        Deletes files from database that no longer exist in directory.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM indexed_files")
            db_files = [row[0] for row in cursor.fetchall()]
            
            files_to_delete = [f for f in db_files if f not in existing_files]
            for f in files_to_delete:
                cursor.execute("DELETE FROM chunks WHERE file_path = ?", (f,))
                cursor.execute("DELETE FROM indexed_files WHERE file_path = ?", (f,))
            conn.commit()

    def search_similar(self, query_text, top_k=5, allowed_files=None):
        """
        Retrieves the top_k most similar chunks for a query.
        Optional parameter `allowed_files` lets the user search only selected files.
        """
        query_emb = get_embedding(query_text)
        if not query_emb:
            return []

        # Fetch candidate chunks
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if allowed_files:
                placeholders = ','.join('?' for _ in allowed_files)
                cursor.execute(
                    f"SELECT file_path, content, start_line, end_line, language, embedding FROM chunks WHERE file_path IN ({placeholders})",
                    allowed_files
                )
            else:
                cursor.execute("SELECT file_path, content, start_line, end_line, language, embedding FROM chunks")
            
            rows = cursor.fetchall()

        if not rows:
            return []

        # Cosine similarity calculations
        results = []
        for file_path, content, start_line, end_line, language, emb_str in rows:
            try:
                emb = json.loads(emb_str)
                sim = self._cosine_similarity(query_emb, emb)
                results.append({
                    "file_path": file_path,
                    "content": content,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": language,
                    "similarity": sim
                })
            except Exception as e:
                print(f"Error calculating similarity for {file_path}: {e}")
                continue

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, v1, v2):
        dot_product = sum(x * y for x, y in zip(v1, v2))
        mag1 = math.sqrt(sum(x * x for x in v1))
        mag2 = math.sqrt(sum(x * x for x in v2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product / (mag1 * mag2)
