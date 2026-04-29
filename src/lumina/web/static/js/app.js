/**
 * Lumina Web Interface - Frontend Application
 */

// 全局状态
const state = {
    currentView: 'dashboard',
    notes: [],
    graph: null,
    isProcessing: false
};

// API 基础 URL
const API_BASE = '';

// DOM 元素
const views = {
    dashboard: document.getElementById('dashboard-view'),
    search: document.getElementById('search-view'),
    graph: document.getElementById('graph-view'),
    notes: document.getElementById('notes-view'),
    config: document.getElementById('config-view')
};

const navButtons = document.querySelectorAll('.nav-btn');
const modal = document.getElementById('note-modal');
const loadingOverlay = document.getElementById('loading-overlay');

// 初始化
function init() {
    setupNavigation();
    setupEventListeners();
    loadDashboardData();
    loadNotes();
    loadConfig();
}

// 导航切换
function setupNavigation() {
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const viewName = btn.dataset.view;
            switchView(viewName);
        });
    });
}

function switchView(viewName) {
    navButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });

    Object.values(views).forEach(view => view.classList.remove('active'));
    if (views[viewName]) {
        views[viewName].classList.add('active');
    }
    state.currentView = viewName;

    if (viewName === 'graph') {
        loadGraph();
    } else if (viewName === 'notes') {
        loadNotes();
    }
}

// 事件监听
function setupEventListeners() {
    // 搜索
    document.getElementById('btn-search').addEventListener('click', performSearch);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // 模态框
    document.getElementById('btn-close-modal').addEventListener('click', closeModal);
    document.getElementById('btn-close-modal-2').addEventListener('click', closeModal);
    document.getElementById('btn-regenerate').addEventListener('click', regenerateNote);

    // 相似度滑块
    document.getElementById('similarity-slider').addEventListener('input', (e) => {
        document.getElementById('similarity-value').textContent = e.target.value;
    });
    document.getElementById('btn-refresh-graph').addEventListener('click', loadGraph);

    // 快速操作
    document.getElementById('btn-scan').addEventListener('click', scanDirectory);
    document.getElementById('btn-batch-repair').addEventListener('click', batchRepair);
    document.getElementById('btn-refresh').addEventListener('click', refreshData);

    // 按源文件重生成
    const sourceInput = document.getElementById('source-file-input');
    const regenerateSourceBtn = document.getElementById('btn-regenerate-source');
    if (regenerateSourceBtn) {
        regenerateSourceBtn.addEventListener('click', regenerateBySourcePath);
    }
    if (sourceInput) {
        sourceInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                regenerateBySourcePath();
            }
        });
    }
}

// API 请求
async function apiRequest(endpoint, options = {}) {
    try {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json'
            }
        };

        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...(options.headers || {})
            }
        };

        const response = await fetch(`${API_BASE}${endpoint}`, mergedOptions);

        if (!response.ok) {
            let detail = '';
            try {
                const err = await response.json();
                detail = err?.error || err?.message || '';
            } catch (_) {
                // ignore non-JSON response
            }
            const suffix = detail ? ` - ${detail}` : '';
            throw new Error(`HTTP ${response.status}: ${response.statusText}${suffix}`);
        }

        return await response.json();
    } catch (error) {
        showToast(`请求失败: ${error.message}`, 'error');
        throw error;
    }
}

// 仪表板数据
async function loadDashboardData() {
    try {
        const stats = await apiRequest('/api/stats');

        document.getElementById('stat-notes').textContent = stats.total_notes || 0;
        document.getElementById('stat-processed').textContent = stats.total_files_processed || 0;
        document.getElementById('stat-score').textContent = (stats.avg_score || 0).toFixed(2);
        document.getElementById('stat-vector').textContent =
            stats.vector_store?.total_documents || 0;
        renderProcessedFiles(stats.recent_processed_files || []);

        const statusDisplay = document.getElementById('status-display');
        if (stats.status && stats.status !== 'idle') {
            statusDisplay.innerHTML = `
                <div class="status-active">
                    <span class="status-indicator"></span>
                    正在处理: ${stats.status}
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

// 构建文件路径树结构
function buildFileTree(files) {
    const dirs = files.map(f => {
        const i = (f.file_path || '').lastIndexOf('/');
        return i >= 0 ? f.file_path.substring(0, i) : '';
    });
    let prefix = dirs.length ? (dirs[0] + '/') : '';
    for (const d of dirs) {
        const p = d + '/';
        let i = 0;
        while (i < prefix.length && i < p.length && prefix[i] === p[i]) i++;
        prefix = prefix.substring(0, i);
    }
    const lastSlash = prefix.lastIndexOf('/');
    prefix = lastSlash >= 0 ? prefix.substring(0, lastSlash + 1) : '';

    const root = { children: {}, files: [] };
    for (const item of files) {
        const rel = item.file_path && item.file_path.startsWith(prefix)
            ? item.file_path.slice(prefix.length)
            : (item.file_path || '');
        const parts = rel.split('/').filter(Boolean);
        let node = root;
        for (let i = 0; i < parts.length - 1; i++) {
            const seg = parts[i];
            if (!node.children[seg]) node.children[seg] = { children: {}, files: [] };
            node = node.children[seg];
        }
        node.files.push(item);
    }
    return { root, prefix };
}

function countFilesInNode(node) {
    let count = node.files.length;
    for (const child of Object.values(node.children)) count += countFilesInNode(child);
    return count;
}

function renderTreeNode(node, idPrefix) {
    let html = '';
    Object.entries(node.children).forEach(([name, child], idx) => {
        const nodeId = `${idPrefix}_${idx}`;
        const total = countFilesInNode(child);
        html += `<div class="pf-dir-group pf-nested">
            <div class="pf-dir-header" onclick="togglePfGroup('${nodeId}')">
                <span class="pf-dir-arrow" id="${nodeId}-arrow">▶</span>
                <span class="pf-dir-name">${escapeHtml(name)}/</span>
                <span class="pf-dir-count">${total} 个文件</span>
            </div>
            <div class="pf-dir-files pf-collapsed" id="${nodeId}">
                ${renderTreeNode(child, nodeId)}
            </div>
        </div>`;
    });
    html += node.files.map(item => `
        <div class="processed-file-item" title="${escapeHtml(item.file_path || '')}">
            <div class="processed-file-main">
                <div class="processed-file-name">${escapeHtml(item.file_name || 'unknown')}</div>
            </div>
            <div class="processed-file-meta">
                <div class="processed-file-time">${formatDateTime(item.last_processed_time)}</div>
                <div class="processed-file-version">v${item.processing_version || 0}</div>
            </div>
        </div>`).join('');
    return html;
}

function renderProcessedFiles(files) {
    const container = document.getElementById('processed-files-list');
    if (!container) return;
    if (!files || files.length === 0) {
        container.innerHTML = '<p class="hint">暂无已处理记录</p>';
        return;
    }
    const { root, prefix } = buildFileTree(files);
    const shortPrefix = prefix.replace(/^\/Users\/[^/]+/, '~').replace(/\/$/, '');
    let html = '';
    if (shortPrefix) {
        html += `<div class="pf-root-label" title="${escapeHtml(prefix)}">${escapeHtml(shortPrefix)}</div>`;
    }
    html += renderTreeNode(root, 'pfr');
    container.innerHTML = html;
}

function togglePfGroup(groupId) {
    const el = document.getElementById(groupId);
    const arrow = document.getElementById(groupId + '-arrow');
    if (!el) return;
    const collapsed = el.classList.toggle('pf-collapsed');
    if (arrow) arrow.classList.toggle('expanded', !collapsed);
}

// 搜索功能
async function performSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    showLoading(true);

    try {
        const results = await apiRequest('/api/search', {
            method: 'POST',
            body: JSON.stringify({ query, n_results: 10 })
        });

        displaySearchResults(results);
    } catch (error) {
        console.error('Search failed:', error);
    } finally {
        showLoading(false);
    }
}

function displaySearchResults(data) {
    const container = document.getElementById('search-results');

    if (!data.results || data.results.length === 0) {
        container.innerHTML = '<p class="hint">未找到相关结果</p>';
        return;
    }

    container.innerHTML = data.results.map(result => `
        <div class="search-result" data-id="${result.id}">
            <div class="result-title">${escapeHtml(result.title)}</div>
            <div class="result-preview">${escapeHtml(result.content_preview)}</div>
            <div class="result-meta">
                <span class="result-score">⭐ ${(result.score * 100).toFixed(1)}%</span>
                <span>${escapeHtml(result.source)}</span>
                <span>${result.tags?.join(', ') || ''}</span>
            </div>
        </div>
    `).join('');

    container.querySelectorAll('.search-result').forEach(el => {
        el.addEventListener('click', () => openNoteDetail(el.dataset.id));
    });
}

// 知识图谱
async function loadGraph() {
    const container = document.getElementById('graph-container');

    if (state.graph) {
        state.graph.destroy();
    }

    showLoading(true);

    try {
        const minSimilarity = document.getElementById('similarity-slider').value;
        const data = await apiRequest(`/api/graph?min_similarity=${minSimilarity}`);

        if (!data.nodes || data.nodes.length === 0) {
            container.innerHTML = '<p class="hint">暂无知识图谱数据</p>';
            showLoading(false);
            return;
        }

        const nodes = new vis.DataSet(
            data.nodes.map(node => ({
                id: node.id,
                label: node.title || node.id,
                title: `Score: ${node.score?.toFixed(2) || 'N/A'}`,
                color: {
                    background: '#1565c0',
                    border: '#0d47a1'
                }
            }))
        );

        const edges = new vis.DataSet(
            data.edges.map(edge => ({
                from: edge.source,
                to: edge.target,
                value: edge.weight,
                title: `Similarity: ${edge.weight?.toFixed(2) || 'N/A'}`
            }))
        );

        const options = {
            nodes: {
                shape: 'dot',
                size: 16,
                font: {
                    color: '#ffffff',
                    size: 14
                }
            },
            edges: {
                color: {
                    color: '#90a4ae',
                    highlight: '#1565c0'
                },
                smooth: {
                    type: 'continuous'
                }
            },
            physics: {
                stabilization: false,
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04
                }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200
            }
        };

        state.graph = new vis.Network(container, { nodes, edges }, options);

        state.graph.on('click', (params) => {
            if (params.nodes.length > 0) {
                openNoteDetail(params.nodes[0]);
            }
        });

    } catch (error) {
        console.error('Failed to load graph:', error);
        container.innerHTML = '<p class="hint">加载知识图谱失败</p>';
    } finally {
        showLoading(false);
    }
}

// 笔记管理
async function loadNotes() {
    const container = document.getElementById('notes-grid');
    container.innerHTML = '<p class="loading">加载笔记...</p>';

    try {
        const data = await apiRequest('/api/notes');
        state.notes = data.notes || [];

        if (state.notes.length === 0) {
            container.innerHTML = '<p class="hint">暂无笔记</p>';
            return;
        }

        container.innerHTML = state.notes.map(note => `
            <div class="note-card" data-id="${note.id}">
                <div class="note-title">${escapeHtml(note.title)}</div>
                <div class="note-meta">
                    <span>${formatSize(note.size)}</span>
                    <span>${formatDate(note.modified)}</span>
                </div>
            </div>
        `).join('');

        container.querySelectorAll('.note-card').forEach(el => {
            el.addEventListener('click', () => openNoteDetail(el.dataset.id));
        });

    } catch (error) {
        console.error('Failed to load notes:', error);
        container.innerHTML = '<p class="hint">加载笔记失败</p>';
    }
}

async function openNoteDetail(noteId) {
    showLoading(true);

    try {
        const note = await apiRequest(`/api/notes/${encodeURIComponent(noteId)}`);

        document.getElementById('modal-title').textContent = note.title || '笔记详情';
        document.getElementById('modal-body').innerHTML = `
            <div class="note-detail">
                <div class="note-tags">
                    ${(note.tags || []).map(tag => `<span class="tag">#${escapeHtml(tag)}</span>`).join('')}
                </div>
                <div class="note-content">
                    ${escapeHtml(note.content)}
                </div>
                ${note.links?.length ? `
                    <div class="note-links">
                        <h3>相关链接</h3>
                        ${note.links.map(link => `<div class="link">${escapeHtml(link)}</div>`).join('')}
                    </div>
                ` : ''}
            </div>
        `;

        modal.classList.remove('hidden');
        modal.dataset.noteId = noteId;
        modal.dataset.sourcePath = note.source_path || '';

    } catch (error) {
        console.error('Failed to load note detail:', error);
        showToast('加载笔记详情失败', 'error');
    } finally {
        showLoading(false);
    }
}

function closeModal() {
    modal.classList.add('hidden');
    delete modal.dataset.noteId;
    delete modal.dataset.sourcePath;
}

async function regenerateNote() {
    const noteId = modal.dataset.noteId;
    const sourcePath = modal.dataset.sourcePath;
    if (!noteId || !sourcePath) return;

    showLoading(true);

    try {
        const result = await apiRequest(`/api/notes/${encodeURIComponent(noteId)}/regenerate`, {
            method: 'POST',
            body: JSON.stringify({ source_path: sourcePath })
        });

        if (result.success) {
            showToast('笔记重新生成成功！');
            closeModal();
            await loadDashboardData();
            await loadNotes();
        } else {
            showToast('重新生成失败: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('Failed to regenerate note:', error);
        showToast('重新生成失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function regenerateBySourcePath() {
    const input = document.getElementById('source-file-input');
    const btn = document.getElementById('btn-regenerate-source');
    if (!input || !btn) return;

    const sourcePath = input.value.trim();
    if (!sourcePath) {
        showToast('请先输入源文件路径', 'error');
        return;
    }

    btn.disabled = true;
    showLoading(true);

    try {
        const result = await apiRequest('/api/regenerate-source', {
            method: 'POST',
            body: JSON.stringify({ source_path: sourcePath })
        });

        if (result.success) {
            showToast('指定源文件笔记已重新生成');
            await loadDashboardData();
            await loadNotes();
        } else {
            showToast('重新生成失败: ' + (result.message || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('Regenerate by source failed:', error);
        showToast('重新生成失败: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        showLoading(false);
    }
}

// 配置管理
async function loadConfig() {
    const container = document.getElementById('config-form');

    try {
        const config = await apiRequest('/api/config');

        container.innerHTML = `
            <form id="config-update-form">
                <div class="form-group">
                    <label class="form-label">最大迭代次数</label>
                    <input type="number" class="form-input" name="max_iterations"
                           value="${config.max_iterations}" min="1" max="10">
                </div>
                <div class="form-group">
                    <label class="form-label">质量阈值</label>
                    <input type="number" class="form-input" name="quality_threshold"
                           value="${config.quality_threshold}" min="0" max="1" step="0.1">
                </div>
                <div class="form-group">
                    <label class="form-label">输出目录</label>
                    <input type="text" class="form-input" name="output_dir"
                           value="${config.output_dir}">
                </div>
                <div class="form-group">
                    <label class="form-label">插件</label>
                    <select class="form-input" name="plugin">
                        <option value="obsidian" ${config.plugin === 'obsidian' ? 'selected' : ''}>Obsidian</option>
                        <option value="plain" ${config.plugin === 'plain' ? 'selected' : ''}>Plain Markdown</option>
                    </select>
                </div>
                <div class="form-group form-checkbox">
                    <input type="checkbox" id="incremental" name="incremental"
                           ${config.incremental ? 'checked' : ''}>
                    <label for="incremental">增量处理</label>
                </div>
                <div class="form-group form-checkbox">
                    <input type="checkbox" id="parallel" name="parallel"
                           ${config.parallel ? 'checked' : ''}>
                    <label for="parallel">并行处理</label>
                </div>
                <div class="form-group form-checkbox">
                    <input type="checkbox" id="enable_vector_store" name="enable_vector_store"
                           ${config.enable_vector_store ? 'checked' : ''}>
                    <label for="enable_vector_store">启用向量存储</label>
                </div>
                <button type="submit" class="btn btn-primary">保存配置</button>
            </form>
        `;

        document.getElementById('config-update-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const newConfig = {};

            formData.forEach((value, key) => {
                if (value === 'on') {
                    newConfig[key] = true;
                } else if (!isNaN(value) && value !== '') {
                    newConfig[key] = Number(value);
                } else {
                    newConfig[key] = value;
                }
            });

            try {
                await apiRequest('/api/config', {
                    method: 'POST',
                    body: JSON.stringify(newConfig)
                });
                showToast('配置已保存！');
            } catch (error) {
                showToast('保存配置失败', 'error');
            }
        });

    } catch (error) {
        console.error('Failed to load config:', error);
        container.innerHTML = '<p class="hint">加载配置失败</p>';
    }
}

// 快速操作
async function scanDirectory() {
    // 检查是否已在扫描
    try {
        const status = await apiRequest('/api/scan/status');
        if (status.running) {
            showToast('扫描已在进行中，请稍候…', 'warning');
            return;
        }
    } catch (_) {}

    showLoading(true);
    showToast('正在启动扫描...');
    try {
        await apiRequest('/api/scan', { method: 'POST', body: JSON.stringify({ incremental: true }) });
    } catch (error) {
        showToast('启动扫描失败: ' + (error.message || error), 'error');
        showLoading(false);
        return;
    }

    // 轮询状态直到扫描结束
    const pollInterval = setInterval(async () => {
        try {
            const status = await apiRequest('/api/scan/status');
            if (!status.running) {
                clearInterval(pollInterval);
                showLoading(false);
                showToast(status.message || '扫描完成');
                await loadDashboardData();
                await loadNotes();
            }
        } catch (_) {
            clearInterval(pollInterval);
            showLoading(false);
        }
    }, 2000);
}

async function batchRepair() {
    showLoading(true);

    try {
        const result = await apiRequest('/api/batch-repair', {
            method: 'POST',
            body: JSON.stringify({ min_score: 0.6 })
        });

        showToast(`批量修复完成: ${result.repaired} 成功, ${result.failed} 失败`);
        await loadDashboardData();
        await loadNotes();
    } catch (error) {
        console.error('Batch repair failed:', error);
        showToast('批量修复失败', 'error');
    } finally {
        showLoading(false);
    }
}

async function refreshData() {
    showToast('正在刷新数据...');
    await loadDashboardData();
    await loadNotes();
    showToast('数据已刷新！');
}

// UI 工具函数
function showLoading(show) {
    loadingOverlay.classList.toggle('hidden', !show);
}

function showToast(message, type = 'success') {
    const toastEl = document.getElementById('toast');
    const messageEl = document.getElementById('toast-message');

    messageEl.textContent = message;
    toastEl.style.background = type === 'error' ? '#c62828' : '#2e7d32';
    toastEl.classList.remove('hidden');

    setTimeout(() => {
        toastEl.classList.add('hidden');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleDateString('zh-CN');
}

function formatDateTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 启动
init();
