/**
 * Lumina Web Interface - Frontend Application
 */

// 全局状态
const state = {
    currentView: 'dashboard',
    notes: [],
    graph: null,
    isProcessing: false,
    scanStatus: null,
    selectedFailureIds: []
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
const failureModal = document.getElementById('failure-modal');
const loadingOverlay = document.getElementById('loading-overlay');
let scanPollTimer = null;
let scanStatusTicker = null;

// 初始化
function init() {
    setupNavigation();
    setupEventListeners();
    loadDashboardData();
    startScanStatusTicker();
    loadNotes();
    loadConfig();
}

function startScanStatusTicker() {
    if (scanStatusTicker) {
        clearInterval(scanStatusTicker);
    }
    updateScanStatus();
    scanStatusTicker = setInterval(updateScanStatus, 2000);
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
    const failureClose1 = document.getElementById('btn-close-failure-modal');
    const failureClose2 = document.getElementById('btn-close-failure-modal-2');
    if (failureClose1) failureClose1.addEventListener('click', closeFailureModal);
    if (failureClose2) failureClose2.addEventListener('click', closeFailureModal);
    const failureSelectAll = document.getElementById('failure-select-all');
    const failureTagBtn = document.getElementById('btn-failure-tag');
    const failureExportBtn = document.getElementById('btn-failure-export');
    const failureRegenerateBtn = document.getElementById('btn-failure-regenerate');
    const failureDeleteBtn = document.getElementById('btn-failure-delete');
    if (failureSelectAll) failureSelectAll.addEventListener('change', toggleSelectAllFailures);
    if (failureTagBtn) failureTagBtn.addEventListener('click', batchTagFailures);
    if (failureExportBtn) failureExportBtn.addEventListener('click', exportSelectedFailures);
    if (failureRegenerateBtn) failureRegenerateBtn.addEventListener('click', batchRegenerateFailures);
    if (failureDeleteBtn) failureDeleteBtn.addEventListener('click', batchDeleteFailures);

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

        await updateScanStatus();
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

async function updateScanStatus() {
    try {
        const response = await fetch('/api/scan/status');
        if (!response.ok) return;
        const status = await response.json();
        state.scanStatus = status || null;
        renderScanStatus(status || {});
        if (failureModal && !failureModal.classList.contains('hidden')) {
            renderFailureModalBody();
        }
    } catch (_) {
        // keep current status panel as-is on transient failures
    }
}

function renderScanStatus(status) {
    const container = document.getElementById('status-display');
    if (!container) return;

    const phase = status.phase || (status.running ? 'running' : 'idle');
    const lastStatus = status.last_status || phase;
    const fileCounts = status.file_counts || {};
    const queue = Array.isArray(status.queue) ? status.queue : [];
    const currentSource = status.current_source || '';
    const running = Boolean(status.running);
    const message = status.message || (running ? '扫描中...' : '等待处理...');
    const lastCompletedAt = status.last_completed_at || status.last_event_at || '';
    const elapsedSeconds = Number(status.elapsed_seconds || 0);
    const failedItems = Array.isArray(status.failed_items) ? status.failed_items : [];

    if (!running && queue.length === 0) {
        if (lastStatus === 'completed' || lastStatus === 'failed') {
            const badgeClass = lastStatus === 'failed' ? 'failed' : 'completed';
            const badgeText = lastStatus === 'failed' ? '上次运行有失败' : '最近一次已完成';
            container.innerHTML = `
                <div class="queue-summary queue-summary-static ${badgeClass}">
                    <div class="queue-summary-top">
                        <div class="status-active stopped ${badgeClass}">
                            <span class="status-indicator"></span>
                            ${badgeText}
                        </div>
                        <div class="queue-message">${escapeHtml(message || '可再次开始扫描')}</div>
                    </div>
                    <div class="queue-counters secondary">
                        <span>成功 ${fileCounts.processed || 0}</span>
                        <span>失败 ${fileCounts.failed || 0}</span>
                        <span>跳过 ${fileCounts.skipped || 0}</span>
                        <span>总计 ${fileCounts.completed || fileCounts.total || 0}</span>
                    </div>
                    ${lastCompletedAt ? `<div class="queue-last-run">最近更新时间 ${escapeHtml(formatDateTime(lastCompletedAt))}</div>` : ''}
                    ${failedItems.length ? `
                        <div class="queue-failure-actions">
                            <button class="btn btn-secondary btn-sm" id="btn-view-failures">查看失败详情 (${failedItems.length})</button>
                        </div>
                    ` : ''}
                </div>
            `;
            const failureBtn = document.getElementById('btn-view-failures');
            if (failureBtn) {
                failureBtn.addEventListener('click', openFailureModal);
            }
            return;
        }

        container.innerHTML = `
            <div class="queue-summary queue-summary-static idle">
                <div class="queue-summary-top">
                    <div class="status-active stopped idle">
                        <span class="status-indicator"></span>
                        尚未开始
                    </div>
                    <div class="queue-message">${escapeHtml(message || '点击开始扫描后，这里会显示实时进度和最近一次运行结果。')}</div>
                </div>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="queue-summary">
            <div class="queue-summary-top">
                <div class="status-active ${running ? 'running' : 'stopped'}">
                    <span class="status-indicator"></span>
                    ${running ? '处理中' : '已停止'}
                </div>
                <div class="queue-message">${escapeHtml(message)}</div>
            </div>
            <div class="queue-counters tertiary">
                <span>已耗时 ${formatDuration(elapsedSeconds)}</span>
            </div>
            ${currentSource ? `<div class="queue-current">当前: ${escapeHtml(currentSource)}</div>` : ''}
            ${failedItems.length ? `
                <div class="queue-failure-actions">
                    <button class="btn btn-secondary btn-sm" id="btn-view-failures">查看失败详情 (${failedItems.length})</button>
                </div>
            ` : ''}
        </div>
    `;

    const failureBtn = document.getElementById('btn-view-failures');
    if (failureBtn) {
        failureBtn.addEventListener('click', openFailureModal);
    }
}

function openFailureModal() {
    if (!failureModal) return;
    const failedItems = Array.isArray(state.scanStatus?.failed_items) ? state.scanStatus.failed_items : [];
    state.selectedFailureIds = failedItems.map(item => item.id);
    renderFailureModalBody();
    failureModal.classList.remove('hidden');
}

function closeFailureModal() {
    if (failureModal) {
        failureModal.classList.add('hidden');
    }
    state.selectedFailureIds = [];
}

function renderFailureModalBody() {
    const failedItems = Array.isArray(state.scanStatus?.failed_items) ? state.scanStatus.failed_items : [];
    const body = document.getElementById('failure-modal-body');
    const selectAll = document.getElementById('failure-select-all');
    if (!body) return;

    if (selectAll) {
        selectAll.checked = failedItems.length > 0 && state.selectedFailureIds.length === failedItems.length;
    }

    if (!failedItems.length) {
        body.innerHTML = '<p class="hint">当前没有失败项。</p>';
        return;
    }

    body.innerHTML = failedItems.map((item, index) => {
        const checked = state.selectedFailureIds.includes(item.id) ? 'checked' : '';
        const tags = Array.isArray(item.tags) ? item.tags : [];
        const status = item.status || 'open';
        const statusLabel = {
            open: '未处理',
            resolved: '已解决',
            retry_failed: '重试失败'
        }[status] || status;

        return `
            <div class="failure-item ${status}">
                <div class="failure-item-header">
                    <label class="failure-check">
                        <input type="checkbox" class="failure-checkbox" data-id="${escapeHtml(item.id)}" ${checked}>
                        <span class="failure-item-title">失败项 ${index + 1}</span>
                    </label>
                    <span class="queue-badge ${status === 'resolved' ? 'completed' : status === 'retry_failed' ? 'failed' : 'pending'}">${statusLabel}</span>
                </div>
                <div class="failure-item-row"><span class="failure-label">源:</span> <span>${escapeHtml(item.source || '-')}</span></div>
                <div class="failure-item-row"><span class="failure-label">文件:</span> <span>${escapeHtml(item.file || '-')}</span></div>
                <div class="failure-item-row"><span class="failure-label">错误:</span> <span>${escapeHtml(item.message || item.last_error || '未知错误')}</span></div>
                ${tags.length ? `<div class="failure-item-row"><span class="failure-label">标签:</span> <span>${tags.map(tag => `<span class="tag">#${escapeHtml(tag)}</span>`).join(' ')}</span></div>` : ''}
                <div class="failure-item-actions">
                    <button class="btn btn-secondary btn-sm failure-copy-path" data-id="${escapeHtml(item.id)}">复制路径</button>
                    <button class="btn btn-secondary btn-sm failure-copy-error" data-id="${escapeHtml(item.id)}">复制错误信息</button>
                </div>
            </div>
        `;
    }).join('');

    body.querySelectorAll('.failure-checkbox').forEach(el => {
        el.addEventListener('change', () => toggleFailureSelection(el.dataset.id, el.checked));
    });
    body.querySelectorAll('.failure-copy-path').forEach(el => {
        el.addEventListener('click', () => {
            const item = findFailureItemById(el.dataset.id);
            copyFailureValue(item?.file || '', '路径已复制');
        });
    });
    body.querySelectorAll('.failure-copy-error').forEach(el => {
        el.addEventListener('click', () => {
            const item = findFailureItemById(el.dataset.id);
            copyFailureValue(item?.message || item?.last_error || '', '错误信息已复制');
        });
    });
}

function findFailureItemById(id) {
    return (state.scanStatus?.failed_items || []).find(item => item.id === id) || null;
}

function toggleFailureSelection(id, checked) {
    const selected = new Set(state.selectedFailureIds);
    if (checked) {
        selected.add(id);
    } else {
        selected.delete(id);
    }
    state.selectedFailureIds = Array.from(selected);
    const failedItems = Array.isArray(state.scanStatus?.failed_items) ? state.scanStatus.failed_items : [];
    const selectAll = document.getElementById('failure-select-all');
    if (selectAll) {
        selectAll.checked = failedItems.length > 0 && state.selectedFailureIds.length === failedItems.length;
    }
}

function toggleSelectAllFailures(event) {
    const failedItems = Array.isArray(state.scanStatus?.failed_items) ? state.scanStatus.failed_items : [];
    state.selectedFailureIds = event.target.checked ? failedItems.map(item => item.id) : [];
    renderFailureModalBody();
}

function getSelectedFailureItems() {
    const selected = new Set(state.selectedFailureIds);
    return (state.scanStatus?.failed_items || []).filter(item => selected.has(item.id));
}

async function copyFailureValue(value, successMessage) {
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(value || '');
        } else {
            const input = document.createElement('textarea');
            input.value = value || '';
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
        }
        showToast(successMessage);
    } catch (error) {
        showToast(`复制失败: ${error.message}`, 'error');
    }
}

async function batchRegenerateFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast('请先选择失败项', 'error');
        return;
    }

    showLoading(true);
    try {
        const result = await apiRequest('/api/scan/failures/regenerate', {
            method: 'POST',
            body: JSON.stringify({ ids: selectedItems.map(item => item.id) })
        });
        showToast(`批量重生成完成: ${result.success || 0} 成功, ${result.failed || 0} 失败`);
        await updateScanStatus();
        renderFailureModalBody();
        await loadDashboardData();
        await loadNotes();
    } catch (error) {
        showToast(`批量重生成失败: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

function exportSelectedFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast('请先选择失败项', 'error');
        return;
    }

    const blob = new Blob([JSON.stringify(selectedItems, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `lumina-failures-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast('失败记录已导出');
}

async function batchDeleteFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast('请先选择失败项', 'error');
        return;
    }

    showLoading(true);
    try {
        const result = await apiRequest('/api/scan/failures/delete', {
            method: 'POST',
            body: JSON.stringify({ ids: selectedItems.map(item => item.id) })
        });
        showToast(`已删除 ${result.deleted || 0} 条失败记录`);
        await updateScanStatus();
        state.selectedFailureIds = [];
        renderFailureModalBody();
    } catch (error) {
        showToast(`删除失败: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

async function batchTagFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast('请先选择失败项', 'error');
        return;
    }

    const input = document.getElementById('failure-tag-input');
    const tags = (input?.value || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

    if (!tags.length) {
        showToast('请输入至少一个标签', 'error');
        return;
    }

    showLoading(true);
    try {
        const result = await apiRequest('/api/scan/failures/tag', {
            method: 'POST',
            body: JSON.stringify({ ids: selectedItems.map(item => item.id), tags })
        });
        showToast(`已为 ${result.updated || 0} 条记录打标签`);
        if (input) input.value = '';
        await updateScanStatus();
        renderFailureModalBody();
    } catch (error) {
        showToast(`打标签失败: ${error.message}`, 'error');
    } finally {
        showLoading(false);
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
        <div class="search-result" data-id="${encodeURIComponent(result.id || '')}" data-source="${encodeURIComponent(result.source || '')}">
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
        el.addEventListener('click', () => {
            const noteId = decodeURIComponent(el.dataset.id || '');
            const sourcePath = decodeURIComponent(el.dataset.source || '');
            openNoteDetail(noteId, sourcePath);
        });
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

function buildNoteDetailUrl(noteId) {
    const normalizedId = String(noteId || '').replace(/\\/g, '/');
    const encodedPath = normalizedId
        .split('/')
        .filter(segment => segment.length > 0)
        .map(segment => encodeURIComponent(segment))
        .join('/');
    return `/api/notes/${encodedPath}`;
}

async function openNoteDetail(noteId, sourcePath = '') {
    showLoading(true);

    try {
        let note = null;
        let resolvedNoteId = noteId;
        let lastError = null;

        if (sourcePath) {
            try {
                note = await apiRequest(`/api/notes/by-source?source=${encodeURIComponent(sourcePath)}`);
                resolvedNoteId = note.id || resolvedNoteId;
            } catch (error) {
                lastError = error;
            }
        }

        if (!note && noteId) {
            try {
                note = await apiRequest(buildNoteDetailUrl(noteId));
            } catch (error) {
                lastError = error;
            }
        }

        if (!note) {
            const sourceCandidate = sourcePath || noteId;
            if (!sourceCandidate) {
                throw lastError || new Error('Note identifier is required');
            }
            note = await apiRequest(`/api/notes/by-source?source=${encodeURIComponent(sourceCandidate)}`);
            resolvedNoteId = note.id || resolvedNoteId;
        }

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
        modal.dataset.noteId = resolvedNoteId;
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
        const systemCfg = config.system_config || {};
        const fixedCfg = systemCfg.fixed || {};
        const runtimeCfg = systemCfg.runtime || {};
        const serviceCfg = systemCfg.service || {};
        const currentSnapshot = config.current_snapshot || {};
        const rawUserConfig = config.raw_user_config || '';
        const agentCfg = (config.agent_config || {}).user_defined || {};
        const harnessCfg = currentSnapshot.harness || agentCfg.harness || {};
        const inputPref = currentSnapshot.input || (config.user_preferences || {}).input || {};
        const outputPref = currentSnapshot.output || (config.user_preferences || {}).output || {};
        const llmShared = currentSnapshot.llm || agentCfg.llm_shared || {};
        const llmPlanner = currentSnapshot.llm_planner || agentCfg.llm_planner || {};
        const llmExecutor = currentSnapshot.llm_executor || agentCfg.llm_executor || {};
        const llmValidator = currentSnapshot.llm_validator || agentCfg.llm_validator || {};

        container.innerHTML = `
            <form id="config-update-form" class="config-sections">
                <section class="config-section">
                    <h3>当前已配置内容</h3>
                    <p class="hint">这里可以直接看到并编辑当前的用户配置文件；分组输入框也会直接预填当前生效值。</p>
                    <div class="config-grid-2">
                        <div class="config-card readonly">
                            <div class="form-label">当前生效配置快照</div>
                            <pre class="json-preview config-tall-preview">${escapeHtml(JSON.stringify(currentSnapshot, null, 2))}</pre>
                        </div>
                        <div class="config-card">
                            <div class="form-label">用户配置文件原文（YAML，可直接编辑）</div>
                            <textarea class="form-input json-input config-tall-preview" id="cfg-raw-user-config">${escapeHtml(rawUserConfig || '# 当前无配置文件内容')}</textarea>
                            <div class="config-actions inline-top-gap">
                                <button type="button" class="btn btn-secondary" id="btn-save-raw-config">保存 YAML 配置</button>
                            </div>
                        </div>
                    </div>
                </section>

                <section class="config-section">
                    <h3>系统配置（固定/运行态）</h3>
                                <textarea class="form-input json-input" id="cfg-llm-shared" rows="8">${escapeHtml(JSON.stringify(llmShared || {}, null, 2))}</textarea>
                    <div class="config-grid-2">
                        <div class="config-card readonly">
                            <div class="form-label">Schema 版本</div>
                                <textarea class="form-input json-input" id="cfg-llm-planner" rows="5">${escapeHtml(JSON.stringify(llmPlanner || {}, null, 2))}</textarea>
                            <div class="form-label">支持 Agents</div>
                            <div class="readonly-value">${escapeHtml((fixedCfg.supported_agents || []).join(', ') || '-')}</div>
                            <div class="form-label">Planner 默认 PARA</div>
                                <textarea class="form-input json-input" id="cfg-llm-executor" rows="5">${escapeHtml(JSON.stringify(llmExecutor || {}, null, 2))}</textarea>
                        </div>
                        <div class="config-card readonly">
                            <div class="form-label">运行状态</div>
                                <textarea class="form-input json-input" id="cfg-llm-validator" rows="5">${escapeHtml(JSON.stringify(llmValidator || {}, null, 2))}</textarea>
                            <div class="form-label">当前会话</div>
                            <div class="readonly-value">${escapeHtml(runtimeCfg.session_id || '-')}</div>
                            <div class="form-label">当前输出目录</div>
                            <div class="readonly-value">${escapeHtml(runtimeCfg.output_dir || '-')}</div>
                            <div class="form-group">
                                <label class="form-label">日志保留天数</label>
                                <input type="number" class="form-input" id="cfg-log-retention-days" min="0" value="${Number(serviceCfg.log_retention_days ?? 15)}">
                            </div>
                        </div>
                    </div>
                </section>

                <section class="config-section">
                    <h3>Agent 配置（可调）</h3>
                    <div class="config-grid-2">
                        <div class="config-card">
                            <div class="form-group">
                                <label class="form-label">Harness 最大迭代次数</label>
                                <input type="number" class="form-input" id="cfg-max-iterations" min="1" max="10" value="${Number(harnessCfg.max_iterations ?? 3)}">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Harness 质量阈值</label>
                                <input type="number" class="form-input" id="cfg-quality-threshold" min="0" max="1" step="0.05" value="${Number(harnessCfg.quality_threshold ?? 0.8)}">
                            </div>
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-incremental" ${harnessCfg.incremental ? 'checked' : ''}>
                                <label for="cfg-incremental">增量处理</label>
                            </div>
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-parallel" ${harnessCfg.parallel ? 'checked' : ''}>
                                <label for="cfg-parallel">并行处理</label>
                            </div>
                            <div class="form-group">
                                <label class="form-label">并行 worker 数</label>
                                <input type="number" class="form-input" id="cfg-max-workers" min="1" max="32" value="${Number(harnessCfg.max_workers ?? 4)}">
                            </div>
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-enable-vector-store" ${harnessCfg.enable_vector_store ? 'checked' : ''}>
                                <label for="cfg-enable-vector-store">启用向量存储</label>
                            </div>
                        </div>
                        <div class="config-card">
                            <div class="form-group">
                                <label class="form-label">共享 LLM 配置（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-llm-shared" rows="8">${escapeHtml(JSON.stringify(agentCfg.llm_shared || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Planner LLM 覆盖（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-llm-planner" rows="5">${escapeHtml(JSON.stringify(agentCfg.llm_planner || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Executor LLM 覆盖（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-llm-executor" rows="5">${escapeHtml(JSON.stringify(agentCfg.llm_executor || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Validator LLM 覆盖（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-llm-validator" rows="5">${escapeHtml(JSON.stringify(agentCfg.llm_validator || {}, null, 2))}</textarea>
                            </div>
                        </div>
                    </div>
                </section>

                <section class="config-section">
                    <h3>用户个性化配置</h3>
                    <div class="config-grid-2">
                        <div class="config-card">
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-default-recursive" ${inputPref.default_recursive ? 'checked' : ''}>
                                <label for="cfg-default-recursive">输入源默认递归</label>
                            </div>
                            <div class="form-group">
                                <label class="form-label">支持扩展名（JSON 数组）</label>
                                <textarea class="form-input json-input" id="cfg-supported-extensions" rows="4">${escapeHtml(JSON.stringify(inputPref.supported_extensions || [], null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">输入源列表（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-input-sources" rows="8">${escapeHtml(JSON.stringify(inputPref.sources || [], null, 2))}</textarea>
                            </div>
                        </div>
                        <div class="config-card">
                            <div class="form-group">
                                <label class="form-label">输出插件</label>
                                <select class="form-input" id="cfg-output-plugin">
                                    <option value="obsidian" ${outputPref.plugin === 'obsidian' ? 'selected' : ''}>Obsidian</option>
                                    <option value="plain" ${outputPref.plugin === 'plain' ? 'selected' : ''}>Plain Markdown</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label class="form-label">输出目录</label>
                                <input type="text" class="form-input" id="cfg-output-base-dir" value="${escapeHtml(outputPref.base_dir || '')}">
                            </div>
                            <div class="form-group">
                                <label class="form-label">Vault 路径</label>
                                <input type="text" class="form-input" id="cfg-output-vault-path" value="${escapeHtml(outputPref.vault_path || '')}">
                            </div>
                            <div class="form-group">
                                <label class="form-label">输出结构（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-output-structure" rows="4">${escapeHtml(JSON.stringify(outputPref.structure || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">命名规则（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-output-naming" rows="4">${escapeHtml(JSON.stringify(outputPref.naming || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">笔记组织规则（JSON）</label>
                                <textarea class="form-input json-input" id="cfg-note-organization" rows="10">${escapeHtml(JSON.stringify(outputPref.note_organization || {}, null, 2))}</textarea>
                            </div>
                        </div>
                    </div>
                </section>

                <div class="config-actions">
                    <button type="submit" class="btn btn-primary">保存全部配置</button>
                </div>
            </form>
        `;

        document.getElementById('config-update-form').addEventListener('submit', async (e) => {
            e.preventDefault();

            const parseJson = (id, fallback) => {
                const raw = (document.getElementById(id)?.value || '').trim();
                if (!raw) return fallback;
                return JSON.parse(raw);
            };

            try {
                const payload = {
                    system_config: {
                        service: {
                            log_retention_days: Number(document.getElementById('cfg-log-retention-days').value || 15)
                        }
                    },
                    agent_config: {
                        user_defined: {
                            harness: {
                                max_iterations: Number(document.getElementById('cfg-max-iterations').value || 3),
                                quality_threshold: Number(document.getElementById('cfg-quality-threshold').value || 0.8),
                                incremental: document.getElementById('cfg-incremental').checked,
                                parallel: document.getElementById('cfg-parallel').checked,
                                max_workers: Number(document.getElementById('cfg-max-workers').value || 4),
                                enable_vector_store: document.getElementById('cfg-enable-vector-store').checked,
                            },
                            llm_shared: parseJson('cfg-llm-shared', {}),
                            llm_planner: parseJson('cfg-llm-planner', {}),
                            llm_executor: parseJson('cfg-llm-executor', {}),
                            llm_validator: parseJson('cfg-llm-validator', {}),
                        }
                    },
                    user_preferences: {
                        input: {
                            default_recursive: document.getElementById('cfg-default-recursive').checked,
                            supported_extensions: parseJson('cfg-supported-extensions', []),
                            sources: parseJson('cfg-input-sources', []),
                        },
                        output: {
                            plugin: document.getElementById('cfg-output-plugin').value,
                            base_dir: document.getElementById('cfg-output-base-dir').value,
                            vault_path: document.getElementById('cfg-output-vault-path').value,
                            structure: parseJson('cfg-output-structure', {}),
                            naming: parseJson('cfg-output-naming', {}),
                            note_organization: parseJson('cfg-note-organization', {}),
                        }
                    }
                };

                await apiRequest('/api/config', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });

                showToast('配置已保存并热更新');
                await loadConfig();
            } catch (error) {
                console.error('Config save failed:', error);
                showToast('保存配置失败，请检查 JSON 格式', 'error');
            }
        });

        document.getElementById('btn-save-raw-config').addEventListener('click', async () => {
            const rawText = document.getElementById('cfg-raw-user-config').value;
            try {
                await apiRequest('/api/config', {
                    method: 'POST',
                    body: JSON.stringify({ raw_user_config: rawText })
                });
                showToast('YAML 配置已保存并重新加载');
                await loadConfig();
            } catch (error) {
                console.error('Raw config save failed:', error);
                showToast('YAML 配置保存失败，请检查格式', 'error');
            }
        });

    } catch (error) {
        console.error('Failed to load config:', error);
        container.innerHTML = '<p class="hint">加载配置失败</p>';
    }
}

// 快速操作
async function scanDirectory() {
    if (scanPollTimer) {
        showToast('扫描任务正在进行中，请稍候…', 'warning');
        return;
    }

    // 检查是否已在扫描
    try {
        const status = await apiRequest('/api/scan/status');
        if (status.running) {
            showToast('扫描已在进行中，请稍候…', 'warning');
            return;
        }
    } catch (_) {}

    showToast('正在启动扫描...');
    try {
        showLoading(true);
        await apiRequest('/api/scan', { method: 'POST', body: JSON.stringify({ incremental: true }) });
        // 启动请求完成后立即解除全屏遮罩，后续用轮询+提示反馈进度，避免页面长期“转圈”
        showLoading(false);
        await updateScanStatus();
    } catch (error) {
        showToast('启动扫描失败: ' + (error.message || error), 'error');
        showLoading(false);
        return;
    }

    const startedAt = Date.now();
    const maxPollMs = 10 * 60 * 1000;

    // 轮询状态直到扫描结束（或超时）
    scanPollTimer = setInterval(async () => {
        try {
            const status = await apiRequest('/api/scan/status');
            renderScanStatus(status || {});
            if (!status.running) {
                clearInterval(scanPollTimer);
                scanPollTimer = null;
                showLoading(false);
                showToast(status.message || '扫描完成');
                await loadDashboardData();
                await loadNotes();
                return;
            }

            if (Date.now() - startedAt > maxPollMs) {
                clearInterval(scanPollTimer);
                scanPollTimer = null;
                showToast('扫描仍在后台执行，请稍后点“刷新数据”查看结果', 'warning');
            }
        } catch (_) {
            clearInterval(scanPollTimer);
            scanPollTimer = null;
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

function formatDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds || 0)));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;

    if (hours > 0) {
        return `${hours}小时 ${minutes}分`;
    }
    if (minutes > 0) {
        return `${minutes}分 ${secs}秒`;
    }
    return `${secs}秒`;
}

// 启动
init();
