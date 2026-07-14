document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const workspacePathInput = document.getElementById('workspace-path');
    const btnScan = document.getElementById('btn-scan');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const statusMessage = document.getElementById('status-message');
    const progressBarContainer = document.getElementById('progress-bar-container');
    const progressBar = document.getElementById('progress-bar');
    const filesCountBadge = document.getElementById('files-count');
    const fileSearchInput = document.getElementById('file-search');
    const filesTree = document.getElementById('files-tree');
    const btnSelectAll = document.getElementById('btn-select-all');
    const btnDeselectAll = document.getElementById('btn-deselect-all');
    const chatFocusIndicator = document.getElementById('chat-focus-indicator');
    const btnClear = document.getElementById('btn-clear');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const btnSend = document.getElementById('btn-send');

    // GitHub Import Elements
    const tabLocal = document.getElementById('tab-local');
    const tabGithub = document.getElementById('tab-github');
    const containerLocal = document.getElementById('container-local');
    const containerGithub = document.getElementById('container-github');
    const btnGithubImport = document.getElementById('btn-github-import');
    const githubUrlInput = document.getElementById('github-url');

    // State Variables
    let chatHistory = [];
    let indexedFiles = [];
    let selectedFiles = new Set();
    let isIndexing = false;
    let pollIntervalId = null;

    // Fetch default workspace path on startup
    fetchDefaultPath();

    // Event Listeners
    if (tabLocal && tabGithub && containerLocal && containerGithub) {
        tabLocal.addEventListener('click', () => {
            tabLocal.classList.add('active');
            tabLocal.style.background = 'var(--btn-primary-bg)';
            tabLocal.style.color = '#fff';
            
            tabGithub.classList.remove('active');
            tabGithub.style.background = 'transparent';
            tabGithub.style.color = 'var(--text-muted)';
            
            containerLocal.style.display = 'block';
            containerGithub.style.display = 'none';
        });
        
        tabGithub.addEventListener('click', () => {
            tabGithub.classList.add('active');
            tabGithub.style.background = 'var(--btn-primary-bg)';
            tabGithub.style.color = '#fff';
            
            tabLocal.classList.remove('active');
            tabLocal.style.background = 'transparent';
            tabLocal.style.color = 'var(--text-muted)';
            
            containerGithub.style.display = 'block';
            containerLocal.style.display = 'none';
        });
    }

    if (btnGithubImport) {
        btnGithubImport.addEventListener('click', startGithubImport);
    }

    btnScan.addEventListener('click', startIndexing);
    fileSearchInput.addEventListener('input', renderFileList);
    btnSelectAll.addEventListener('click', selectAllFiles);
    btnDeselectAll.addEventListener('click', deselectAllFiles);
    btnClear.addEventListener('click', clearChatHistory);
    btnSend.addEventListener('click', handleSendMessage);
    chatInput.addEventListener('keydown', handleKeyDown);
    chatInput.addEventListener('input', adjustTextareaHeight);

    // How to Use Modal Selectors & Event Listeners
    const btnHowToUse = document.getElementById('btn-how-to-use');
    const instructionsModal = document.getElementById('instructions-modal');
    const btnCloseModal = document.getElementById('close-modal');

    if (btnHowToUse && instructionsModal && btnCloseModal) {
        btnHowToUse.addEventListener('click', () => {
            instructionsModal.classList.add('open');
        });
        
        btnCloseModal.addEventListener('click', () => {
            instructionsModal.classList.remove('open');
        });
        
        window.addEventListener('click', (e) => {
            if (e.target === instructionsModal) {
                instructionsModal.classList.remove('open');
            }
        });
    }

    // Initial state setup
    btnSend.disabled = true;

    // Functions

    async function fetchDefaultPath() {
        try {
            // We'll call status to see if there's any path already set
            const res = await fetch('/api/status');
            const data = await res.json();
            // If the server doesn't have a path, we'll try to get one or use a placeholder
            // Let's ask server for current path using a quick fetch or just use dot as default
            workspacePathInput.value = window.location.pathname === '/' ? '.' : '';

            // Check status to see if it's already indexing
            handleStatusResponse(data);
            if (data.status === 'indexing') {
                startIndexingPoll();
            } else {
                fetchIndexedFiles();
            }
        } catch (e) {
            console.error("Startup error:", e);
        }
    }

    async function startIndexing() {
        const path = workspacePathInput.value.trim();
        if (!path) {
            alert('Please enter a valid directory path first.');
            return;
        }

        btnScan.disabled = true;
        btnScan.classList.add('indexing');
        btnScan.innerHTML = '<i class="fa-solid fa-rotate"></i> Indexing';

        try {
            const res = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Scan failed');
            }

            isIndexing = true;
            statusDot.className = 'status-dot indexing';
            statusText.textContent = 'Indexing...';
            progressBarContainer.style.display = 'block';
            progressBar.style.width = '0%';

            startIndexingPoll();
        } catch (e) {
            alert('Error starting indexer: ' + e.message);
            resetIndexingUI();
        }
    }

    function startIndexingPoll() {
        if (pollIntervalId) clearInterval(pollIntervalId);
        pollIntervalId = setInterval(pollIndexingStatus, 1000);
    }

    async function pollIndexingStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            handleStatusResponse(data);
        } catch (e) {
            console.error("Error polling index status:", e);
        }
    }

    function handleStatusResponse(data) {
        if (data.status === 'indexing') {
            statusDot.className = 'status-dot indexing';
            statusText.textContent = `Indexing (${data.processed_files}/${data.total_files})`;
            statusMessage.textContent = data.message || 'Processing files...';

            if (data.total_files > 0) {
                const percent = Math.round((data.processed_files / data.total_files) * 100);
                progressBar.style.width = `${percent}%`;
            }
        } else if (data.status === 'idle') {
            if (pollIntervalId) {
                clearInterval(pollIntervalId);
                pollIntervalId = null;
            }

            resetIndexingUI();
            statusDot.className = 'status-dot success';
            statusText.textContent = 'Ready';
            statusMessage.textContent = data.message || 'Workspace indexed and ready.';
            progressBarContainer.style.display = 'none';

            fetchIndexedFiles();
        }
    }

    async function startGithubImport() {
        const url = githubUrlInput.value.trim();
        if (!url) {
            alert('Please enter a valid GitHub repository URL.');
            return;
        }

        btnGithubImport.disabled = true;
        btnGithubImport.innerHTML = '<i class="fa-solid fa-rotate fa-spin"></i> Importing';

        try {
            const res = await fetch('/api/github-import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Import failed');
            }

            isIndexing = true;
            statusDot.className = 'status-dot indexing';
            statusText.textContent = 'Importing...';
            statusMessage.textContent = 'Downloading repository ZIP...';
            progressBarContainer.style.display = 'block';
            progressBar.style.width = '0%';
            
            startIndexingPoll();
        } catch (e) {
            alert('Error starting GitHub import: ' + e.message);
            resetIndexingUI();
        }
    }

    function resetIndexingUI() {
        isIndexing = false;
        btnScan.disabled = false;
        btnScan.classList.remove('indexing');
        btnScan.innerHTML = '<i class="fa-solid fa-rotate"></i> Index';
        
        if (btnGithubImport) {
            btnGithubImport.disabled = false;
            btnGithubImport.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Import';
        }
    }

    async function fetchIndexedFiles() {
        try {
            const res = await fetch('/api/files');
            const data = await res.json();
            indexedFiles = data.files || [];

            // Add new files to the selection set
            indexedFiles.forEach(file => {
                selectedFiles.add(file);
            });

            filesCountBadge.textContent = indexedFiles.length;
            renderFileList();
            updateChatFocusIndicator();

            // Enable chat input if we have files
            btnSend.disabled = chatInput.value.trim() === '';
        } catch (e) {
            console.error("Error loading files list:", e);
        }
    }

    function renderFileList() {
        const filter = fileSearchInput.value.toLowerCase().trim();
        filesTree.innerHTML = '';

        const filteredFiles = indexedFiles.filter(file => file.toLowerCase().includes(filter));

        if (filteredFiles.length === 0) {
            filesTree.innerHTML = `<div class="empty-files-message">${indexedFiles.length === 0 ? 'No files indexed yet.' : 'No matching files.'}</div>`;
            return;
        }

        filteredFiles.forEach(file => {
            const ext = '.' + file.split('.').pop().toLowerCase();
            let iconClass = 'fa-file-code';

            if (ext === '.py') iconClass = 'fa-brands fa-python';
            else if (ext === '.c' || ext === '.h') iconClass = 'fa-solid fa-c';
            else if (ext === '.java') iconClass = 'fa-brands fa-java';
            else if (ext === '.md') iconClass = 'fa-brands fa-markdown';
            else if (ext === '.json') iconClass = 'fa-solid fa-braces-asterisk';
            else if (ext === '.html' || ext === '.css' || ext === '.js' || ext === '.ts') iconClass = 'fa-solid fa-code';
            else iconClass = 'fa-solid fa-file-lines';

            const item = document.createElement('div');
            item.className = 'file-item';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = selectedFiles.has(file);
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    selectedFiles.add(file);
                } else {
                    selectedFiles.delete(file);
                }
                updateChatFocusIndicator();
            });

            item.appendChild(checkbox);

            const icon = document.createElement('i');
            icon.className = iconClass;
            item.appendChild(icon);

            const nameSpan = document.createElement('span');
            nameSpan.className = 'file-name';
            nameSpan.textContent = file;
            nameSpan.title = file;
            item.appendChild(nameSpan);

            item.addEventListener('click', (e) => {
                // If the user clicked the item but not the checkbox directly, toggle it
                if (e.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                }
            });

            filesTree.appendChild(item);
        });
    }

    function selectAllFiles() {
        indexedFiles.forEach(file => selectedFiles.add(file));
        renderFileList();
        updateChatFocusIndicator();
    }

    function deselectAllFiles() {
        selectedFiles.clear();
        renderFileList();
        updateChatFocusIndicator();
    }

    function updateChatFocusIndicator() {
        if (selectedFiles.size === 0) {
            chatFocusIndicator.textContent = "Search focus: No files selected (Assistant will answer generally)";
        } else if (selectedFiles.size === indexedFiles.length) {
            chatFocusIndicator.textContent = "Search focus: All indexed files";
        } else {
            chatFocusIndicator.textContent = `Search focus: ${selectedFiles.size} of ${indexedFiles.length} files selected`;
        }
    }

    function adjustTextareaHeight() {
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight) + 'px';
        btnSend.disabled = chatInput.value.trim() === '' || isIndexing;
    }

    function handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    }

    function clearChatHistory() {
        chatHistory = [];
        chatMessages.innerHTML = `
            <div id="welcome-container" class="welcome-container">
                <div class="welcome-logo">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <h1>Welcome to Code Companion</h1>
                <p>Ask a question to start understanding your codebase</p>
            </div>
        `;
    }

    async function handleSendMessage() {
        const text = chatInput.value.trim();
        if (!text || isIndexing) return;

        // Remove welcome container on first message
        const welcomeContainer = document.getElementById('welcome-container');
        if (welcomeContainer) {
            welcomeContainer.remove();
        }

        // Reset input textarea
        chatInput.value = '';
        chatInput.style.height = 'auto';
        btnSend.disabled = true;

        // Add user message to UI
        appendMessage('user', text);

        // Prepare API parameters
        const allowedFilesList = selectedFiles.size === indexedFiles.length ? null : Array.from(selectedFiles);
        const payload = {
            message: text,
            history: [...chatHistory],
            allowed_files: allowedFilesList
        };

        // Update local chat history (user turn)
        chatHistory.push({ role: 'user', content: text });

        // Add assistant placeholder with loading spinner
        const assistantMsgDiv = appendMessage('assistant', `
            <div class="thinking-loader">
                <span></span>
                <span></span>
                <span></span>
                <span style="background:none; width:auto; height:auto; border-radius:0; color:var(--text-muted); font-size:0.9rem; margin-left:6px; animation:none; opacity:1;">Thinking...</span>
            </div>
        `);
        const assistantContentDiv = assistantMsgDiv.querySelector('.message-content');

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                throw new Error("Chat request failed");
            }

            assistantContentDiv.innerHTML = ''; // Clear loader
            let completeResponse = '';

            // Read SSE stream
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Keep the last partial line in the buffer
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.error) {
                                assistantContentDiv.innerHTML += `<div class="error-text">Error: ${data.error}</div>`;
                            } else if (data.content) {
                                completeResponse += data.content;
                                assistantContentDiv.innerHTML = formatMarkdown(completeResponse);
                                chatMessages.scrollTop = chatMessages.scrollHeight;
                            }
                        } catch (err) {
                            console.error("SSE parse error", err, line);
                        }
                    }
                }
            }

            // Append assistant response to history
            chatHistory.push({ role: 'assistant', content: completeResponse });

            // Re-bind copy buttons inside the new message
            bindCopyButtons(assistantContentDiv);

        } catch (e) {
            assistantContentDiv.innerHTML = `<div class="error-text"><i class="fa-solid fa-triangle-exclamation"></i> Failed to communicate: ${e.message}</div>`;
            chatHistory.pop(); // Remove user turn from history since it failed
        }
    }

    function appendMessage(role, htmlContent) {
        const msg = document.createElement('div');
        msg.className = `message ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';

        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = role === 'user' ? escapeHTML(htmlContent) : htmlContent;

        msg.appendChild(avatar);
        msg.appendChild(content);
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return msg;
    }

    function escapeHTML(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // A lightweight markdown-to-HTML parser focused on code blocks and developer aesthetics
    function formatMarkdown(text) {
        const codeBlocks = [];
        // 1. Temporarily extract and replace code blocks with a placeholder to prevent list/heading parsing inside code
        const codeBlockRegex = /```(\w*)\n([\s\S]*?)(```|$)/g;
        let formatted = text.replace(codeBlockRegex, (match, lang, code) => {
            const cleanCode = escapeHTML(code.trim());
            const displayLang = lang || 'code';
            const placeholder = `__CODE_BLOCK_PLACEHOLDER_${codeBlocks.length}__`;

            codeBlocks.push(`
                <div class="code-block-container">
                    <div class="code-block-header">
                        <span>${displayLang.toUpperCase()}</span>
                        <button class="btn-copy" data-code="${encodeURIComponent(code.trim())}">
                            <i class="fa-regular fa-clipboard"></i> Copy
                        </button>
                    </div>
                    <pre><code>${cleanCode}</code></pre>
                </div>
            `);
            return placeholder;
        });

        // 2. Inline code (`code`)
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // 3. Headings (# Title)
        formatted = formatted.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        formatted = formatted.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        formatted = formatted.replace(/^# (.*$)/gim, '<h1>$1</h1>');

        // 4. Bullet points (* list or - list)
        formatted = formatted.replace(/^\s*[-*+]\s+(.*$)/gim, '<li>$1</li>');
        // Wrap consecutive <li> elements in <ul>
        formatted = formatted.replace(/(<li>.*?<\/li>(?:\s*<li>.*?<\/li>)*)/gs, '<ul>$1</ul>');

        // 5. Newlines
        formatted = formatted.replace(/\n/g, '<br>');

        // 6. Restore code blocks
        codeBlocks.forEach((blockHtml, index) => {
            formatted = formatted.replace(`__CODE_BLOCK_PLACEHOLDER_${index}__`, blockHtml);
        });

        return formatted;
    }

    function bindCopyButtons(container) {
        const copyBtns = container.querySelectorAll('.btn-copy');
        copyBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const code = decodeURIComponent(btn.getAttribute('data-code'));
                navigator.clipboard.writeText(code).then(() => {
                    btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                    btn.style.color = '#2ea043';
                    setTimeout(() => {
                        btn.innerHTML = '<i class="fa-regular fa-clipboard"></i> Copy';
                        btn.style.color = '';
                    }, 2000);
                }).catch(err => {
                    console.error('Could not copy text: ', err);
                });
            });
        });
    }
});
