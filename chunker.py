import os
import re

# Supported code extensions and their language names for frontend formatting
SUPPORTED_EXTENSIONS = {
    '.py': 'python',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.hpp': 'cpp',
    '.java': 'java',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.html': 'html',
    '.css': 'css',
    '.md': 'markdown',
    '.json': 'json',
    '.sh': 'bash',
    '.txt': 'text'
}

# Directories to exclude from indexing
IGNORED_DIRS = {
    '.git',
    'node_modules',
    '__pycache__',
    '.venv',
    'venv',
    'env',
    '.idea',
    '.vscode',
    'dist',
    'build',
    'out',
    '.gemini',
    'artifacts'
}

def get_language(file_path):
    _, ext = os.path.splitext(file_path.lower())
    return SUPPORTED_EXTENSIONS.get(ext, 'text')

def should_index_file(file_path):
    _, ext = os.path.splitext(file_path.lower())
    return ext in SUPPORTED_EXTENSIONS

def is_ignored(path, base_dir):
    # Check if any path segment matches IGNORED_DIRS
    rel_path = os.path.relpath(path, base_dir)
    parts = rel_path.split(os.sep)
    for part in parts:
        if part in IGNORED_DIRS:
            return True
    return False

def chunk_file(file_path, base_dir, chunk_size_chars=1200, overlap_chars=200):
    """
    Reads a file and splits it into semantic or line-based chunks.
    Ensures code boundaries (like functions/classes) are respected where possible.
    """
    rel_path = os.path.relpath(file_path, base_dir).replace('\\', '/')
    language = get_language(file_path)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

    if not lines:
        return []

    chunks = []
    
    # We will build chunks based on characters, but keep track of line numbers
    current_chunk_lines = []
    current_char_count = 0
    start_line = 1
    
    # Indicators for function/class starts in popular languages
    # This helps split code at logical boundaries rather than arbitrary character limits
    boundary_regex = re.compile(r'^\s*(def\s+|class\s+|function\s+|async\s+function\s+|public\s+class\s+|public\s+void\s+|private\s+void\s+|struct\s+|#\s+)')

    for idx, line in enumerate(lines):
        line_num = idx + 1
        line_len = len(line)
        
        # Check if we should split before adding this line:
        # 1. We have enough content (at least half of chunk size) AND
        # 2. This line starts a new function, class, or markdown heading OR
        # 3. We are exceeding the absolute max chunk size
        is_boundary = boundary_regex.search(line) is not None
        
        if current_chunk_lines and (
            (current_char_count >= chunk_size_chars - overlap_chars and is_boundary) or
            (current_char_count + line_len > chunk_size_chars)
        ):
            # Save the current chunk
            content = "".join(current_chunk_lines)
            chunks.append({
                "file_path": rel_path,
                "content": content,
                "start_line": start_line,
                "end_line": line_num - 1,
                "language": language
            })
            
            # Start a new chunk, maintaining overlap
            # To overlap, we take the last few lines that sum up to overlap_chars
            overlap_lines = []
            overlap_chars_count = 0
            for l in reversed(current_chunk_lines):
                if overlap_chars_count + len(l) > overlap_chars:
                    break
                overlap_lines.insert(0, l)
                overlap_chars_count += len(l)
            
            current_chunk_lines = overlap_lines
            current_char_count = overlap_chars_count
            start_line = max(1, line_num - len(overlap_lines))

        current_chunk_lines.append(line)
        current_char_count += line_len

    # Add the last chunk
    if current_chunk_lines:
        content = "".join(current_chunk_lines)
        chunks.append({
            "file_path": rel_path,
            "content": content,
            "start_line": start_line,
            "end_line": len(lines),
            "language": language
        })

    return chunks

def scan_directory(base_dir):
    """
    Recursively scans the directory and returns all indexable files.
    """
    all_files = []
    for root, dirs, files in os.walk(base_dir):
        # Exclude ignored directories in-place so os.walk doesn't recurse into them
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        
        for file in files:
            full_path = os.path.join(root, file)
            if should_index_file(full_path) and not is_ignored(full_path, base_dir):
                all_files.append(full_path)
    return all_files
