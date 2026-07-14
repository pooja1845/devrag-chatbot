# 🤖 DevRAG Code Companion

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Google%20Gemini-8E75C2?style=for-the-badge&logo=googlegemini&logoColor=white" alt="Google Gemini" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5" />
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3" />
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript" />
</p>

<p align="center">
  <a href="https://devrag-chatbot.onrender.com" target="_blank">
    <img src="https://img.shields.io/badge/⚡%20Live%20Demo-Click%20Here%20to%20Try-success?style=for-the-badge&logo=render&logoColor=white&color=d4af37" alt="Live Demo" />
  </a>
</p>

DevRAG Code Companion is a premium, full-stack, RAG-powered coding assistant that lets you chat with any code repository. It features a luxury dark UI with smooth micro-animations, semantic search, and dual-mode execution (using local **Ollama** or cloud-hosted **Google Gemini API**).

---

## 📸 Application Screenshots
<img width="1917" height="867" alt="Screenshot 2026-07-14 152208" src="https://github.com/user-attachments/assets/0af74589-2cf0-450d-bde6-5593695984c5" />
<img width="1917" height="867" alt="Screenshot 2026-07-14 151127" src="https://github.com/user-attachments/assets/aaecc9a7-dfad-410f-ac36-4146cb662c4b" />



---

## 💡 Why DevRAG Code Companion? (How It Helps Coders)

When working with new or large codebases, developers often spend hours reading files line-by-line just to understand the architecture, API routes, or data models. 

**DevRAG Code Companion solves this by providing:**
- **🚀 Accelerated Code Onboarding**: Instantly chat with any project to understand its structure, main entry points, and module interfaces in seconds.
- **🔍 Semantic Code Search**: Instead of searching by exact text match (like `Ctrl+F`), query your codebase concepts semantically (e.g., *"How do we handle file downloads?"* or *"Where is the auth logic?"*).
- **🔒 Privacy & Offline Capability**: Support for local Ollama models ensures you can scan proprietary or private enterprise source code offline without uploading it to external cloud servers.
- **📂 Interactive File Isolation**: The sidebar file tree allows developers to isolate specific folders or files, reducing noise and focusing the AI's answers directly on the target modules.

---

## ⚡ Quick Start Guide (Try It in 30 Seconds!)

If you are viewing the live deployed app, follow these steps to see it in action:

1. **Select "GitHub Repo"**: Click the **GitHub Repo** tab in the sidebar on the left.
2. **Paste a Repository URL**: Paste any public repository link (e.g., `https://github.com/octocat/Spoon-Knife`).
3. **Click "Import"**: The app will download and index the entire repository into our RAG system.
4. **Chat**: Once ready, ask questions about the repository!

### 💡 Try Asking These Questions:
* *"Give me a brief summary of how this project works."*
* *"What are the key files and functions in this repository?"*
* *"Explain the structure of this code in points."*

---

## ✨ Features

* **Dual-Mode AI Engine**: Seamless hybrid architecture. Runs completely locally on Ollama (`qwen2.5-coder` + `nomic-embed`), but automatically switches to cloud-hosted **Google Gemini** (`gemini-1.5-flash` + `text-embedding-004`) when deployed to Render.
* **On-the-Fly GitHub Indexing**: Downloads any public repository ZIP, extracts it, and dynamically vectorizes it into SQLite.
* **Luxury AMOLED Dark UI**: Designed with true pitch-black backgrounds, Champagne Gold accents, bouncing loading animations, and slide-in bubble reveal transitions.
* **Targeted File Focus**: Select or deselect specific files from the workspace tree to limit the AI's search focus.

---

## 🛠️ Tech Stack & Architecture

| Layer | Technology | Role / Purpose |
| :--- | :--- | :--- |
| **Backend** | Python, FastAPI, Uvicorn | High-performance asynchronous API router & file-system utility servers. |
| **Frontend** | Vanilla HTML5, CSS3, ES6+ JS | Premium AMOLED Black & Gold responsive chat interface with custom slide-up reveals. |
| **Vector DB** | SQLite3 | Local serverless database storage for chunk records and 768-dimensional embeddings. |
| **Local LLM** | Ollama (`qwen2.5-coder:1.5b`, `nomic-embed-text`) | Offline models for private semantic search and code explaining. |
| **Cloud LLM** | Google Gemini (`gemini-1.5-flash`, `text-embedding-004`) | High-speed cloud model streaming and embedding generation for production hosting. |

---

## 🚀 How to Run Locally

### 1. Prerequisites
- Python 3.8+
- [Ollama](https://ollama.com/) (for local offline mode)
  ```bash
  ollama pull qwen2.5-coder:1.5b
  ollama pull nomic-embed-text
  ```

### 2. Install & Start
```bash
# Clone the repository
git clone https://github.com/your-username/devrag-chatbot.git
cd devrag-chatbot

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # On macOS/Linux: source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run the server (Local Ollama mode)
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

To run locally with **Gemini Mode**, set your key before starting:
```bash
# PowerShell
$env:GEMINI_API_KEY="your_api_key"
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

---

## ☁️ Free Cloud Deployment (Render)

1. Create a free account on [Render.com](https://render.com/).
2. Create a new **Web Service** and connect this repository.
3. Configure the settings:
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Under **Advanced**, add an Environment Variable:
   - **Key**: `GEMINI_API_KEY`
   - **Value**: `[Your Gemini API Key]` (Get a free key from [Google AI Studio](https://aistudio.google.com/))
5. Click **Deploy Web Service**!
