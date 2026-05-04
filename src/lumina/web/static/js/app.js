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
    selectedFailureIds: [],
    i18n: {
        locale: 'en',
        preference: 'auto',
        messages: {},
        fallbackMessages: {}
    }
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

const I18N_STORAGE_KEY = 'lumina.locale';
const FALLBACK_LOCALE = 'en';
const SUPPORTED_LOCALES = [
    'en', 'zh-CN', 'zh-TW', 'hi', 'es', 'fr', 'ar', 'bn', 'pt', 'ru', 'ur', 'ja', 'ko'
];
const LOCALE_LABELS = {
    auto: 'Auto (Follow Browser)',
    en: 'English',
    'zh-CN': '简体中文',
    'zh-TW': '繁体中文',
    hi: 'हिन्दी',
    es: 'Español',
    fr: 'Français',
    ar: 'العربية',
    bn: 'বাংলা',
    pt: 'Português',
    ru: 'Русский',
    ur: 'اردو',
    ja: '日本語',
    ko: '한국어'
};

// 初始化
async function init() {
    await initI18n();
    setupNavigation();
    setupEventListeners();
    loadDashboardData();
    startScanStatusTicker();
    loadNotes();
    loadConfig();
}

function deepGet(source, path) {
    return String(path || '').split('.').reduce((cur, part) => {
        if (cur && Object.prototype.hasOwnProperty.call(cur, part)) {
            return cur[part];
        }
        return undefined;
    }, source);
}

function interpolate(template, vars = {}) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) => {
        return vars[key] === undefined || vars[key] === null ? '' : String(vars[key]);
    });
}

function t(key, vars = {}, fallback = '') {
    const active = deepGet(state.i18n.messages, key);
    const base = active !== undefined ? active : deepGet(state.i18n.fallbackMessages, key);
    const text = base !== undefined ? base : (fallback || key);
    return interpolate(text, vars);
}

function normalizeLocale(input) {
    const raw = String(input || '').trim();
    if (!raw) return FALLBACK_LOCALE;

    const lower = raw.toLowerCase();
    if (lower.startsWith('zh-tw') || lower.startsWith('zh-hk') || lower.startsWith('zh-mo')) {
        return 'zh-TW';
    }
    if (lower.startsWith('zh')) {
        return 'zh-CN';
    }

    const exact = SUPPORTED_LOCALES.find(locale => locale.toLowerCase() === lower);
    if (exact) return exact;

    const base = lower.split('-')[0];
    const baseMatch = SUPPORTED_LOCALES.find(locale => locale.toLowerCase() === base);
    return baseMatch || FALLBACK_LOCALE;
}

function detectBrowserLocale() {
    const candidates = Array.isArray(navigator.languages) && navigator.languages.length
        ? navigator.languages
        : [navigator.language || FALLBACK_LOCALE];

    for (const item of candidates) {
        const normalized = normalizeLocale(item);
        if (SUPPORTED_LOCALES.includes(normalized)) {
            return normalized;
        }
    }
    return FALLBACK_LOCALE;
}

async function loadLocaleMessages(locale) {
    const response = await fetch(`/static/i18n/${encodeURIComponent(locale)}.json`);
    if (!response.ok) {
        throw new Error(`Failed to load locale ${locale}`);
    }
    return response.json();
}

async function applyLocale(locale) {
    const normalized = normalizeLocale(locale);
    const [messages, fallbackMessages] = await Promise.all([
        loadLocaleMessages(normalized),
        normalized === FALLBACK_LOCALE ? Promise.resolve({}) : loadLocaleMessages(FALLBACK_LOCALE),
    ]);

    state.i18n.locale = normalized;
    state.i18n.messages = messages || {};
    state.i18n.fallbackMessages = normalized === FALLBACK_LOCALE ? state.i18n.messages : (fallbackMessages || {});

    document.documentElement.lang = normalized;
    applyI18nToStaticDom();
}

async function applyLocaleFromPreference() {
    const preferred = state.i18n.preference || 'auto';
    const resolved = preferred === 'auto' ? detectBrowserLocale() : normalizeLocale(preferred);
    await applyLocale(resolved);
}

function applyI18nToStaticDom() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (!key) return;
        el.textContent = t(key);
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (!key) return;
        el.setAttribute('placeholder', t(key));
    });

    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        if (!key) return;
        el.setAttribute('title', t(key));
    });

    document.title = t('meta.title', {}, 'Lumina');
}

function setupLocaleSelector() {
    const selector = document.getElementById('locale-selector');
    if (!selector) return;

    selector.innerHTML = '';
    const options = ['auto', ...SUPPORTED_LOCALES];
    options.forEach(locale => {
        const option = document.createElement('option');
        option.value = locale;
        option.textContent = LOCALE_LABELS[locale] || locale;
        selector.appendChild(option);
    });

    selector.value = state.i18n.preference || 'auto';
}

async function initI18n() {
    const savedPreference = localStorage.getItem(I18N_STORAGE_KEY);
    state.i18n.preference = savedPreference || 'auto';
    await applyLocaleFromPreference();
    setupLocaleSelector();
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
    const localeSelector = document.getElementById('locale-selector');
    if (localeSelector) {
        localeSelector.addEventListener('change', async (e) => {
            const value = String(e.target.value || 'auto');
            state.i18n.preference = value;
            localStorage.setItem(I18N_STORAGE_KEY, value);
            await applyLocaleFromPreference();
            await loadConfig();
            if (state.scanStatus) {
                renderScanStatus(state.scanStatus);
            }
            if (failureModal && !failureModal.classList.contains('hidden')) {
                renderFailureModalBody();
            }
        });
    }

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
        showToast(t('error.request_failed', { message: error.message }, `Request failed: ${error.message}`), 'error');
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

function formatSourcePath(path) {
    if (!path) return '-';
    return String(path).replace(/^\/Users\/[^/]+/, '~');
}

function normalizeQueueStatus(status, failed, completed, total) {
    const known = ['pending', 'processing', 'completed', 'failed'];
    if (known.includes(status)) return status;
    if (failed > 0) return 'failed';
    if (completed > 0 && total > 0 && completed >= total) return 'completed';
    if (completed > 0) return 'processing';
    return 'pending';
}

function renderQueueDetails(queue) {
    if (!Array.isArray(queue) || queue.length === 0) {
        return '';
    }

    const labelMap = {
        pending: t('queue.badge.pending', {}, 'Pending'),
        processing: t('queue.badge.processing', {}, 'Processing'),
        completed: t('queue.badge.completed', {}, 'Completed'),
        failed: t('queue.badge.failed', {}, 'Failed'),
    };

    const rows = queue.map((item, index) => {
        const total = Number(item.changed_files || item.total_files || 0);
        const processed = Number(item.processed || 0);
        const failed = Number(item.failed || 0);
        const skipped = Number(item.skipped || 0);
        const completed = Number(item.completed || (processed + failed + skipped));
        const progress = Number(item.progress_percent || (total > 0 ? (completed / total) * 100 : 0));
        const progressSafe = Math.max(0, Math.min(100, progress));
        const statusKey = normalizeQueueStatus(String(item.status || ''), failed, completed, total);

        return `
            <div class="queue-item ${statusKey}">
                <div class="queue-item-top">
                    <div class="queue-source" title="${escapeHtml(item.source || '')}">${escapeHtml(formatSourcePath(item.source || `source_${index + 1}`))}</div>
                    <span class="queue-badge ${statusKey}">${labelMap[statusKey] || statusKey}</span>
                </div>
                <div class="queue-item-meta">${escapeHtml(t('queue.meta.total_completed', { total, completed }, `Total ${total}, Completed ${completed}`))}</div>
                <div class="queue-progress-row">
                    <div class="queue-mini-progress"><span style="width:${progressSafe}%;"></span></div>
                    <div class="queue-progress-text">${progressSafe.toFixed(0)}%</div>
                </div>
                <div class="queue-counters secondary">
                    <span>${escapeHtml(t('queue.counter.processed', { count: processed }, `processed ${processed}`))}</span>
                    <span>${escapeHtml(t('queue.counter.failed', { count: failed }, `failed ${failed}`))}</span>
                    <span>${escapeHtml(t('queue.counter.skipped', { count: skipped }, `skipped ${skipped}`))}</span>
                </div>
            </div>
        `;
    }).join('');

    return `<div class="queue-list">${rows}</div>`;
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
    const message = status.message || (running ? t('scan.running', {}, 'Running...') : t('scan.waiting', {}, 'Waiting...'));
    const lastCompletedAt = status.last_completed_at || status.last_event_at || '';
    const elapsedSeconds = Number(status.elapsed_seconds || 0);
    const failedItems = Array.isArray(status.failed_items) ? status.failed_items : [];
    const queueDetailsHtml = renderQueueDetails(queue);

    if (!running && queue.length === 0) {
        if (lastStatus === 'completed' || lastStatus === 'failed') {
            const badgeClass = lastStatus === 'failed' ? 'failed' : 'completed';
            const badgeText = lastStatus === 'failed'
                ? t('scan.last_run_failed', {}, 'Last run had failures')
                : t('scan.last_run_completed', {}, 'Last run completed');
            container.innerHTML = `
                <div class="queue-summary queue-summary-static ${badgeClass}">
                    <div class="queue-summary-top">
                        <div class="status-active stopped ${badgeClass}">
                            <span class="status-indicator"></span>
                            ${badgeText}
                        </div>
                        <div class="queue-message">${escapeHtml(message || t('scan.ready_for_rescan', {}, 'Ready to scan again'))}</div>
                    </div>
                    <div class="queue-counters secondary">
                        <span>${escapeHtml(t('scan.counter.scanned', { count: fileCounts.scanned || fileCounts.total || 0 }, `Scanned ${fileCounts.scanned || fileCounts.total || 0}`))}</span>
                        <span>${escapeHtml(t('scan.counter.changed', { count: fileCounts.changed || fileCounts.total || 0 }, `Changed ${fileCounts.changed || fileCounts.total || 0}`))}</span>
                        <span>${escapeHtml(t('scan.counter.in_progress', { count: fileCounts.in_progress || 0 }, `In progress ${fileCounts.in_progress || 0}`))}</span>
                        <span>${escapeHtml(t('scan.counter.processed', { count: fileCounts.processed || 0 }, `Processed ${fileCounts.processed || 0}`))}</span>
                        <span>${escapeHtml(t('scan.counter.failed', { count: fileCounts.failed || 0 }, `Failed ${fileCounts.failed || 0}`))}</span>
                        <span>${escapeHtml(t('scan.counter.skipped', { count: fileCounts.skipped || 0 }, `Skipped ${fileCounts.skipped || 0}`))}</span>
                        <span>${escapeHtml(t('scan.counter.total', { count: fileCounts.completed || fileCounts.total || 0 }, `Total ${fileCounts.completed || fileCounts.total || 0}`))}</span>
                    </div>
                    ${lastCompletedAt ? `<div class="queue-last-run">${escapeHtml(t('scan.last_updated_at', { time: formatDateTime(lastCompletedAt) }, `Updated ${formatDateTime(lastCompletedAt)}`))}</div>` : ''}
                    ${queueDetailsHtml}
                    ${failedItems.length ? `
                        <div class="queue-failure-actions">
                            <button class="btn btn-secondary btn-sm" id="btn-view-failures">${escapeHtml(t('failure.view_details', { count: failedItems.length }, `View failure details (${failedItems.length})`))}</button>
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
                        ${escapeHtml(t('scan.not_started', {}, 'Not started'))}
                    </div>
                    <div class="queue-message">${escapeHtml(message || t('scan.idle_hint', {}, 'Start a scan to see live progress and latest results.'))}</div>
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
                    ${running ? t('scan.status.processing', {}, 'Processing') : t('scan.status.stopped', {}, 'Stopped')}
                </div>
                <div class="queue-message">${escapeHtml(message)}</div>
            </div>
            <div class="queue-counters tertiary">
                <span>${escapeHtml(t('scan.counter.elapsed', { value: formatDuration(elapsedSeconds) }, `Elapsed ${formatDuration(elapsedSeconds)}`))}</span>
                <span>${escapeHtml(t('scan.counter.scanned', { count: fileCounts.scanned || fileCounts.total || 0 }, `Scanned ${fileCounts.scanned || fileCounts.total || 0}`))}</span>
                <span>${escapeHtml(t('scan.counter.changed', { count: fileCounts.changed || fileCounts.total || 0 }, `Changed ${fileCounts.changed || fileCounts.total || 0}`))}</span>
                <span>${escapeHtml(t('scan.counter.in_progress', { count: fileCounts.in_progress || 0 }, `In progress ${fileCounts.in_progress || 0}`))}</span>
                <span>${escapeHtml(t('scan.counter.completed', { count: fileCounts.completed || 0 }, `Completed ${fileCounts.completed || 0}`))}</span>
                <span>${escapeHtml(t('scan.counter.failed', { count: fileCounts.failed || 0 }, `Failed ${fileCounts.failed || 0}`))}</span>
                <span>${escapeHtml(t('scan.counter.skipped', { count: fileCounts.skipped || 0 }, `Skipped ${fileCounts.skipped || 0}`))}</span>
            </div>
            ${currentSource ? `<div class="queue-current">${escapeHtml(t('scan.current_source', { source: currentSource }, `Current: ${currentSource}`))}</div>` : ''}
            ${queueDetailsHtml}
            ${failedItems.length ? `
                <div class="queue-failure-actions">
                    <button class="btn btn-secondary btn-sm" id="btn-view-failures">${escapeHtml(t('failure.view_details', { count: failedItems.length }, `View failure details (${failedItems.length})`))}</button>
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
        body.innerHTML = `<p class="hint">${escapeHtml(t('failure.empty', {}, 'No failure items right now.'))}</p>`;
        return;
    }

    body.innerHTML = failedItems.map((item, index) => {
        const checked = state.selectedFailureIds.includes(item.id) ? 'checked' : '';
        const tags = Array.isArray(item.tags) ? item.tags : [];
        const status = item.status || 'open';
        const statusLabel = {
            open: t('failure.status.open', {}, 'Open'),
            resolved: t('failure.status.resolved', {}, 'Resolved'),
            retry_failed: t('failure.status.retry_failed', {}, 'Retry failed')
        }[status] || status;

        return `
            <div class="failure-item ${status}">
                <div class="failure-item-header">
                    <label class="failure-check">
                        <input type="checkbox" class="failure-checkbox" data-id="${escapeHtml(item.id)}" ${checked}>
                        <span class="failure-item-title">${escapeHtml(t('failure.item_title', { index: index + 1 }, `Failure ${index + 1}`))}</span>
                    </label>
                    <span class="queue-badge ${status === 'resolved' ? 'completed' : status === 'retry_failed' ? 'failed' : 'pending'}">${statusLabel}</span>
                </div>
                <div class="failure-item-row"><span class="failure-label">${escapeHtml(t('failure.field.source', {}, 'Source:'))}</span> <span>${escapeHtml(item.source || '-')}</span></div>
                <div class="failure-item-row"><span class="failure-label">${escapeHtml(t('failure.field.file', {}, 'File:'))}</span> <span>${escapeHtml(item.file || '-')}</span></div>
                <div class="failure-item-row"><span class="failure-label">${escapeHtml(t('failure.field.error', {}, 'Error:'))}</span> <span>${escapeHtml(item.message || item.last_error || t('common.unknown_error', {}, 'Unknown error'))}</span></div>
                ${tags.length ? `<div class="failure-item-row"><span class="failure-label">${escapeHtml(t('failure.field.tags', {}, 'Tags:'))}</span> <span>${tags.map(tag => `<span class="tag">#${escapeHtml(tag)}</span>`).join(' ')}</span></div>` : ''}
                <div class="failure-item-actions">
                    <button class="btn btn-secondary btn-sm failure-copy-path" data-id="${escapeHtml(item.id)}">${escapeHtml(t('failure.copy_path', {}, 'Copy path'))}</button>
                    <button class="btn btn-secondary btn-sm failure-copy-error" data-id="${escapeHtml(item.id)}">${escapeHtml(t('failure.copy_error', {}, 'Copy error'))}</button>
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
            copyFailureValue(item?.file || '', t('failure.path_copied', {}, 'Path copied'));
        });
    });
    body.querySelectorAll('.failure-copy-error').forEach(el => {
        el.addEventListener('click', () => {
            const item = findFailureItemById(el.dataset.id);
            copyFailureValue(item?.message || item?.last_error || '', t('failure.error_copied', {}, 'Error copied'));
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
        showToast(t('failure.copy_failed', { message: error.message }, `Copy failed: ${error.message}`), 'error');
    }
}

async function batchRegenerateFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast(t('failure.select_required', {}, 'Please select failure items first'), 'error');
        return;
    }

    showLoading(true);
    try {
        const result = await apiRequest('/api/scan/failures/regenerate', {
            method: 'POST',
            body: JSON.stringify({ ids: selectedItems.map(item => item.id) })
        });
        showToast(t('failure.batch_regenerate_done', { success: result.success || 0, failed: result.failed || 0 }, `Batch regenerate done: ${result.success || 0} success, ${result.failed || 0} failed`));
        await updateScanStatus();
        renderFailureModalBody();
        await loadDashboardData();
        await loadNotes();
    } catch (error) {
        showToast(t('failure.batch_regenerate_failed', { message: error.message }, `Batch regenerate failed: ${error.message}`), 'error');
    } finally {
        showLoading(false);
    }
}

function exportSelectedFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast(t('failure.select_required', {}, 'Please select failure items first'), 'error');
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
    showToast(t('failure.export_done', {}, 'Failure records exported'));
}

async function batchDeleteFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast(t('failure.select_required', {}, 'Please select failure items first'), 'error');
        return;
    }

    showLoading(true);
    try {
        const result = await apiRequest('/api/scan/failures/delete', {
            method: 'POST',
            body: JSON.stringify({ ids: selectedItems.map(item => item.id) })
        });
        showToast(t('failure.deleted_count', { count: result.deleted || 0 }, `Deleted ${result.deleted || 0} failure records`));
        await updateScanStatus();
        state.selectedFailureIds = [];
        renderFailureModalBody();
    } catch (error) {
        showToast(t('failure.delete_failed', { message: error.message }, `Delete failed: ${error.message}`), 'error');
    } finally {
        showLoading(false);
    }
}

async function batchTagFailures() {
    const selectedItems = getSelectedFailureItems();
    if (!selectedItems.length) {
        showToast(t('failure.select_required', {}, 'Please select failure items first'), 'error');
        return;
    }

    const input = document.getElementById('failure-tag-input');
    const tags = (input?.value || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

    if (!tags.length) {
        showToast(t('failure.tag_required', {}, 'Please enter at least one tag'), 'error');
        return;
    }

    showLoading(true);
    try {
        const result = await apiRequest('/api/scan/failures/tag', {
            method: 'POST',
            body: JSON.stringify({ ids: selectedItems.map(item => item.id), tags })
        });
        showToast(t('failure.tagged_count', { count: result.updated || 0 }, `Tagged ${result.updated || 0} records`));
        if (input) input.value = '';
        await updateScanStatus();
        renderFailureModalBody();
    } catch (error) {
        showToast(t('failure.tag_failed', { message: error.message }, `Tagging failed: ${error.message}`), 'error');
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
                <span class="pf-dir-count">${escapeHtml(t('processed.files_count', { count: total }, `${total} files`))}</span>
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
        container.innerHTML = `<p class="hint">${escapeHtml(t('processed.empty', {}, 'No processed records yet'))}</p>`;
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
        container.innerHTML = `<p class="hint">${escapeHtml(t('search.no_results', {}, 'No results found'))}</p>`;
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
            container.innerHTML = `<p class="hint">${escapeHtml(t('graph.empty', {}, 'No graph data available'))}</p>`;
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
        container.innerHTML = `<p class="hint">${escapeHtml(t('graph.load_failed', {}, 'Failed to load graph'))}</p>`;
    } finally {
        showLoading(false);
    }
}

// 笔记管理
async function loadNotes() {
    const container = document.getElementById('notes-grid');
    container.innerHTML = `<p class="loading">${escapeHtml(t('notes.loading', {}, 'Loading notes...'))}</p>`;

    try {
        const data = await apiRequest('/api/notes');
        state.notes = data.notes || [];

        if (state.notes.length === 0) {
            container.innerHTML = `<p class="hint">${escapeHtml(t('notes.empty', {}, 'No notes yet'))}</p>`;
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
        container.innerHTML = `<p class="hint">${escapeHtml(t('notes.load_failed', {}, 'Failed to load notes'))}</p>`;
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

        document.getElementById('modal-title').textContent = note.title || t('notes.modal_title', {}, 'Note Details');
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
                        <h3>${escapeHtml(t('notes.related_links', {}, 'Related Links'))}</h3>
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
        showToast(t('notes.detail_load_failed', {}, 'Failed to load note details'), 'error');
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
            showToast(t('notes.regenerate_success', {}, 'Note regenerated successfully'));
            closeModal();
            await loadDashboardData();
            await loadNotes();
        } else {
            showToast(t('notes.regenerate_failed_with_message', { message: result.message }, `Regenerate failed: ${result.message}`), 'error');
        }
    } catch (error) {
        console.error('Failed to regenerate note:', error);
        showToast(t('notes.regenerate_failed', {}, 'Regenerate failed'), 'error');
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
        showToast(t('notes.source_path_required', {}, 'Please enter a source file path first'), 'error');
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
            showToast(t('notes.source_regenerate_success', {}, 'Source file note regenerated'));
            await loadDashboardData();
            await loadNotes();
        } else {
            showToast(t('notes.regenerate_failed_with_message', { message: result.message || t('common.unknown_error', {}, 'Unknown error') }, `Regenerate failed: ${result.message || 'Unknown error'}`), 'error');
        }
    } catch (error) {
        console.error('Regenerate by source failed:', error);
        showToast(t('notes.regenerate_failed_with_message', { message: error.message }, `Regenerate failed: ${error.message}`), 'error');
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
                    <h3>${escapeHtml(t('config.page.current_config.title', {}, 'Current Configuration'))}</h3>
                    <p class="hint">${escapeHtml(t('config.page.current_config.hint', {}, 'You can view and edit the current user configuration here.'))}</p>
                    <div class="config-grid-2">
                        <div class="config-card readonly">
                            <div class="form-label">${escapeHtml(t('config.page.current_config.snapshot', {}, 'Active Config Snapshot'))}</div>
                            <pre class="json-preview config-tall-preview">${escapeHtml(JSON.stringify(currentSnapshot, null, 2))}</pre>
                        </div>
                        <div class="config-card">
                            <div class="form-label">${escapeHtml(t('config.page.current_config.raw_yaml', {}, 'User Config YAML (editable)'))}</div>
                            <textarea class="form-input json-input config-tall-preview" id="cfg-raw-user-config">${escapeHtml(rawUserConfig || t('config.page.current_config.empty_yaml', {}, '# Empty user config'))}</textarea>
                            <div class="config-actions inline-top-gap">
                                <button type="button" class="btn btn-secondary" id="btn-save-raw-config">${escapeHtml(t('config.page.actions.save_yaml', {}, 'Save YAML Config'))}</button>
                            </div>
                        </div>
                    </div>
                </section>

                <section class="config-section">
                    <h3>${escapeHtml(t('config.page.system.title', {}, 'System Configuration'))}</h3>
                                <textarea class="form-input json-input" id="cfg-llm-shared" rows="8">${escapeHtml(JSON.stringify(llmShared || {}, null, 2))}</textarea>
                    <div class="config-grid-2">
                        <div class="config-card readonly">
                            <div class="form-label">${escapeHtml(t('config.page.system.schema_version', {}, 'Schema Version'))}</div>
                                <textarea class="form-input json-input" id="cfg-llm-planner" rows="5">${escapeHtml(JSON.stringify(llmPlanner || {}, null, 2))}</textarea>
                            <div class="form-label">${escapeHtml(t('config.page.system.supported_agents', {}, 'Supported Agents'))}</div>
                            <div class="readonly-value">${escapeHtml((fixedCfg.supported_agents || []).join(', ') || '-')}</div>
                            <div class="form-label">${escapeHtml(t('config.page.system.planner_default_para', {}, 'Planner Default PARA'))}</div>
                                <textarea class="form-input json-input" id="cfg-llm-executor" rows="5">${escapeHtml(JSON.stringify(llmExecutor || {}, null, 2))}</textarea>
                        </div>
                        <div class="config-card readonly">
                            <div class="form-label">${escapeHtml(t('config.page.system.runtime_status', {}, 'Runtime Status'))}</div>
                                <textarea class="form-input json-input" id="cfg-llm-validator" rows="5">${escapeHtml(JSON.stringify(llmValidator || {}, null, 2))}</textarea>
                            <div class="form-label">${escapeHtml(t('config.page.system.current_session', {}, 'Current Session'))}</div>
                            <div class="readonly-value">${escapeHtml(runtimeCfg.session_id || '-')}</div>
                            <div class="form-label">${escapeHtml(t('config.page.system.current_output_dir', {}, 'Current Output Directory'))}</div>
                            <div class="readonly-value">${escapeHtml(runtimeCfg.output_dir || '-')}</div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.system.log_retention_days', {}, 'Log Retention Days'))}</label>
                                <input type="number" class="form-input" id="cfg-log-retention-days" min="0" value="${Number(serviceCfg.log_retention_days ?? 15)}">
                            </div>
                        </div>
                    </div>
                </section>

                <section class="config-section">
                    <h3>${escapeHtml(t('config.page.agent.title', {}, 'Agent Configuration'))}</h3>
                    <div class="config-grid-2">
                        <div class="config-card">
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.max_iterations', {}, 'Harness Max Iterations'))}</label>
                                <input type="number" class="form-input" id="cfg-max-iterations" min="1" max="10" value="${Number(harnessCfg.max_iterations ?? 3)}">
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.quality_threshold', {}, 'Harness Quality Threshold'))}</label>
                                <input type="number" class="form-input" id="cfg-quality-threshold" min="0" max="1" step="0.05" value="${Number(harnessCfg.quality_threshold ?? 0.8)}">
                            </div>
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-incremental" ${harnessCfg.incremental ? 'checked' : ''}>
                                <label for="cfg-incremental">${escapeHtml(t('config.page.agent.incremental', {}, 'Incremental Processing'))}</label>
                            </div>
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-parallel" ${harnessCfg.parallel ? 'checked' : ''}>
                                <label for="cfg-parallel">${escapeHtml(t('config.page.agent.parallel', {}, 'Parallel Processing'))}</label>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.max_workers', {}, 'Parallel Worker Count'))}</label>
                                <input type="number" class="form-input" id="cfg-max-workers" min="1" max="32" value="${Number(harnessCfg.max_workers ?? 4)}">
                            </div>
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-enable-vector-store" ${harnessCfg.enable_vector_store ? 'checked' : ''}>
                                <label for="cfg-enable-vector-store">${escapeHtml(t('config.page.agent.enable_vector_store', {}, 'Enable Vector Store'))}</label>
                            </div>
                        </div>
                        <div class="config-card">
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.llm_shared', {}, 'Shared LLM Config (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-llm-shared" rows="8">${escapeHtml(JSON.stringify(agentCfg.llm_shared || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.llm_planner', {}, 'Planner LLM Override (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-llm-planner" rows="5">${escapeHtml(JSON.stringify(agentCfg.llm_planner || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.llm_executor', {}, 'Executor LLM Override (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-llm-executor" rows="5">${escapeHtml(JSON.stringify(agentCfg.llm_executor || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.agent.llm_validator', {}, 'Validator LLM Override (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-llm-validator" rows="5">${escapeHtml(JSON.stringify(agentCfg.llm_validator || {}, null, 2))}</textarea>
                            </div>
                        </div>
                    </div>
                </section>

                <section class="config-section">
                    <h3>${escapeHtml(t('config.page.user.title', {}, 'User Preferences'))}</h3>
                    <div class="config-grid-2">
                        <div class="config-card">
                            <div class="form-group form-checkbox">
                                <input type="checkbox" id="cfg-default-recursive" ${inputPref.default_recursive ? 'checked' : ''}>
                                <label for="cfg-default-recursive">${escapeHtml(t('config.page.user.default_recursive', {}, 'Default Recursive for Input Sources'))}</label>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.supported_extensions', {}, 'Supported Extensions (JSON Array)'))}</label>
                                <textarea class="form-input json-input" id="cfg-supported-extensions" rows="4">${escapeHtml(JSON.stringify(inputPref.supported_extensions || [], null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.input_sources', {}, 'Input Source List (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-input-sources" rows="8">${escapeHtml(JSON.stringify(inputPref.sources || [], null, 2))}</textarea>
                            </div>
                        </div>
                        <div class="config-card">
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.output_plugin', {}, 'Output Plugin'))}</label>
                                <select class="form-input" id="cfg-output-plugin">
                                    <option value="obsidian" ${outputPref.plugin === 'obsidian' ? 'selected' : ''}>Obsidian</option>
                                    <option value="plain" ${outputPref.plugin === 'plain' ? 'selected' : ''}>Plain Markdown</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.output_dir', {}, 'Output Directory'))}</label>
                                <input type="text" class="form-input" id="cfg-output-base-dir" value="${escapeHtml(outputPref.base_dir || '')}">
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.vault_path', {}, 'Vault Path'))}</label>
                                <input type="text" class="form-input" id="cfg-output-vault-path" value="${escapeHtml(outputPref.vault_path || '')}">
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.output_structure', {}, 'Output Structure (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-output-structure" rows="4">${escapeHtml(JSON.stringify(outputPref.structure || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.naming_rules', {}, 'Naming Rules (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-output-naming" rows="4">${escapeHtml(JSON.stringify(outputPref.naming || {}, null, 2))}</textarea>
                            </div>
                            <div class="form-group">
                                <label class="form-label">${escapeHtml(t('config.page.user.note_organization', {}, 'Note Organization Rules (JSON)'))}</label>
                                <textarea class="form-input json-input" id="cfg-note-organization" rows="10">${escapeHtml(JSON.stringify(outputPref.note_organization || {}, null, 2))}</textarea>
                            </div>
                        </div>
                    </div>
                </section>

                <div class="config-actions">
                    <button type="submit" class="btn btn-primary">${escapeHtml(t('config.page.actions.save_all', {}, 'Save All Configuration'))}</button>
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

                showToast(t('config.saved', {}, 'Configuration saved and hot reloaded'));
                await loadConfig();
            } catch (error) {
                console.error('Config save failed:', error);
                showToast(t('config.save_failed', {}, 'Failed to save config, please check JSON format'), 'error');
            }
        });

        document.getElementById('btn-save-raw-config').addEventListener('click', async () => {
            const rawText = document.getElementById('cfg-raw-user-config').value;
            try {
                await apiRequest('/api/config', {
                    method: 'POST',
                    body: JSON.stringify({ raw_user_config: rawText })
                });
                showToast(t('config.raw_saved', {}, 'YAML config saved and reloaded'));
                await loadConfig();
            } catch (error) {
                console.error('Raw config save failed:', error);
                showToast(t('config.raw_save_failed', {}, 'Failed to save YAML config, please check format'), 'error');
            }
        });

    } catch (error) {
        console.error('Failed to load config:', error);
        container.innerHTML = `<p class="hint">${escapeHtml(t('config.load_failed', {}, 'Failed to load config'))}</p>`;
    }
}

// 快速操作
async function scanDirectory() {
    if (scanPollTimer) {
        showToast(t('scan.already_running', {}, 'Scan is already running, please wait...'), 'warning');
        return;
    }

    // 检查是否已在扫描
    try {
        const status = await apiRequest('/api/scan/status');
        if (status.running) {
            showToast(t('scan.already_running', {}, 'Scan is already running, please wait...'), 'warning');
            return;
        }
    } catch (_) {}

    showToast(t('scan.starting', {}, 'Starting scan...'));
    try {
        showLoading(true);
        await apiRequest('/api/scan', { method: 'POST', body: JSON.stringify({ incremental: true }) });
        // 启动请求完成后立即解除全屏遮罩，后续用轮询+提示反馈进度，避免页面长期“转圈”
        showLoading(false);
        await updateScanStatus();
    } catch (error) {
        showToast(t('scan.start_failed', { message: error.message || error }, `Failed to start scan: ${error.message || error}`), 'error');
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
                showToast(status.message || t('scan.completed', {}, 'Scan completed'));
                await loadDashboardData();
                await loadNotes();
                return;
            }

            if (Date.now() - startedAt > maxPollMs) {
                clearInterval(scanPollTimer);
                scanPollTimer = null;
                showToast(t('scan.background_running', {}, 'Scan is still running in background, please refresh later'), 'warning');
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

        showToast(t('repair.done', { repaired: result.repaired, failed: result.failed }, `Batch repair done: ${result.repaired} success, ${result.failed} failed`));
        await loadDashboardData();
        await loadNotes();
    } catch (error) {
        console.error('Batch repair failed:', error);
        showToast(t('repair.failed', {}, 'Batch repair failed'), 'error');
    } finally {
        showLoading(false);
    }
}

async function refreshData() {
    showToast(t('refresh.running', {}, 'Refreshing data...'));
    await loadDashboardData();
    await loadNotes();
    showToast(t('refresh.done', {}, 'Data refreshed'));
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
    return date.toLocaleDateString(state.i18n.locale || FALLBACK_LOCALE);
}

function formatDateTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString(state.i18n.locale || FALLBACK_LOCALE, {
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
        return t('duration.hours_minutes', { hours, minutes }, `${hours}h ${minutes}m`);
    }
    if (minutes > 0) {
        return t('duration.minutes_seconds', { minutes, seconds: secs }, `${minutes}m ${secs}s`);
    }
    return t('duration.seconds', { seconds: secs }, `${secs}s`);
}

// 启动
init();
