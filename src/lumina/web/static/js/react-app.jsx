const { useEffect, useMemo, useRef, useState } = React;

const API_BASE = '';
const LOCALE_KEY = 'lumina.locale';

async function requestJson(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = '';
    try {
      const err = await response.json();
      detail = err?.error || err?.message || '';
    } catch (_) {
      detail = '';
    }
    throw new Error(`HTTP ${response.status}: ${response.statusText}${detail ? ` - ${detail}` : ''}`);
  }
  return response.json();
}

function formatDateTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  return dt.toLocaleString();
}

function interpolateTemplate(template, vars = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (_, key) => {
    return vars[key] === undefined || vars[key] === null ? '' : String(vars[key]);
  });
}

function tr(key, vars = {}, fallback = '') {
  if (typeof window.luminaTranslate === 'function') {
    return window.luminaTranslate(key, vars, fallback);
  }
  return interpolateTemplate(fallback || key, vars);
}

function useDashboardData() {
  const [stats, setStats] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [statsData, scanData] = await Promise.all([
        requestJson('/api/stats'),
        requestJson('/api/scan/status'),
      ]);
      setStats(statsData || {});
      setScanStatus(scanData || {});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    const timer = setInterval(async () => {
      try {
        const scanData = await requestJson('/api/scan/status');
        setScanStatus(scanData || {});
      } catch (_) {
        // ignore transient polling errors
      }
    }, 2000);

    const onScanEvent = (evt) => {
      setScanStatus(evt?.detail || {});
    };
    window.addEventListener('lumina:scan-status', onScanEvent);

    return () => {
      clearInterval(timer);
      window.removeEventListener('lumina:scan-status', onScanEvent);
    };
  }, []);

  return { stats, scanStatus, loading, reload: loadAll };
}

function DashboardView() {
  const { stats, scanStatus, loading, reload } = useDashboardData();
  const processedFiles = stats?.recent_processed_files || [];
  const fileCounts = scanStatus?.file_counts || {};

  const statusText = useMemo(() => {
    if (!scanStatus) return '等待处理...';
    if (scanStatus.running) return scanStatus.message || '处理中...';
    if (scanStatus.last_status === 'completed') return '最近一次扫描已完成';
    if (scanStatus.last_status === 'failed') return '最近一次扫描含失败项';
    return scanStatus.message || '等待处理...';
  }, [scanStatus]);

  return (
    <div id="dashboard-view" className="view active">
      <h1 className="page-title" data-i18n="view.dashboard.title">📊 仪表板</h1>

      <div className="stats-grid">
        <div className="stat-card"><div className="stat-icon">📝</div><div className="stat-content"><div className="stat-value">{stats?.total_notes || 0}</div><div className="stat-label" data-i18n="stats.total_notes">总笔记数</div></div></div>
        <div className="stat-card"><div className="stat-icon">✅</div><div className="stat-content"><div className="stat-value">{stats?.total_files_processed || 0}</div><div className="stat-label" data-i18n="stats.processed_files">处理文件数</div></div></div>
        <div className="stat-card"><div className="stat-icon">⭐</div><div className="stat-content"><div className="stat-value">{Number(stats?.avg_score || 0).toFixed(2)}</div><div className="stat-label" data-i18n="stats.avg_score">平均质量</div></div></div>
        <div className="stat-card"><div className="stat-icon">🔮</div><div className="stat-content"><div className="stat-value">{stats?.vector_store?.total_documents || 0}</div><div className="stat-label" data-i18n="stats.vector_docs">向量文档</div></div></div>
      </div>

      <div className="panel">
        <h2 className="panel-title" data-i18n="panel.processing_status">📌 处理状态</h2>
        <div id="status-display" className="queue-summary queue-summary-static">
          <div className="queue-summary-top">
            <div className={`status-active ${scanStatus?.running ? 'running' : 'stopped'}`}>
              <span className="status-indicator"></span>
              {scanStatus?.running ? 'Processing' : 'Stopped'}
            </div>
            <div className="queue-message">{loading ? 'Loading...' : statusText}</div>
          </div>
          <div className="queue-counters secondary">
            <span>Scanned {fileCounts.scanned || fileCounts.total || 0}</span>
            <span>Processed {fileCounts.processed || 0}</span>
            <span>Failed {fileCounts.failed || 0}</span>
            <span>Skipped {fileCounts.skipped || 0}</span>
          </div>
          {scanStatus?.last_completed_at ? (
            <div className="queue-last-run">Updated {formatDateTime(scanStatus.last_completed_at)}</div>
          ) : null}
        </div>
      </div>

      <div className="panel">
        <h2 className="panel-title" data-i18n="panel.processed_files">🗂️ 全部已处理原文件</h2>
        <div id="processed-files-list">
          {!processedFiles.length ? <p className="hint" data-i18n="common.no_records">暂无记录</p> : processedFiles.map((item, idx) => (
            <div className="processed-file-item" key={`${item.file_path || item.file_name || 'file'}-${idx}`}>
              <div className="processed-file-main">
                <div className="processed-file-name">{item.file_name || 'unknown'}</div>
              </div>
              <div className="processed-file-meta">
                <div className="processed-file-time">{formatDateTime(item.last_processed_time)}</div>
                <div className="processed-file-version">v{item.processing_version || 0}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2 className="panel-title" data-i18n="panel.quick_actions">⚡ 快速操作</h2>
        <div className="quick-actions">
          <button className="btn btn-primary" onClick={() => window.scanDirectory && window.scanDirectory()}>扫描目录</button>
          <button className="btn btn-warning" onClick={() => window.batchRepair && window.batchRepair()}>批量修复</button>
          <button className="btn btn-secondary" onClick={reload}>刷新数据</button>
        </div>
      </div>
    </div>
  );
}

function SearchView() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');

  const onSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true);
    setError('');
    try {
      const data = await requestJson('/api/search', {
        method: 'POST',
        body: JSON.stringify({ query: trimmed, n_results: 10 }),
      });
      setResults(Array.isArray(data?.results) ? data.results : []);
    } catch (err) {
      setError(err.message || 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const onResultClick = (item) => {
    if (!item) return;
    const noteId = item.id || '';
    const sourcePath = item.source || '';
    if (window.openNoteDetail) {
      window.openNoteDetail(noteId, sourcePath);
    }
  };

  return (
    <div id="search-view" className="view active">
      <h1 className="page-title" data-i18n="view.search.title">🔍 语义搜索</h1>
      <div className="search-box">
        <input
          type="text"
          className="search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSearch()}
          placeholder="输入搜索内容..."
          data-i18n-placeholder="search.input_placeholder"
        />
        <button className="btn btn-primary" onClick={onSearch} disabled={loading}>搜索</button>
      </div>
      <div className="search-results" id="search-results">
        {loading ? <p className="loading">加载中...</p> : null}
        {!loading && !error && results.length === 0 ? <p className="hint" data-i18n="search.start_hint">输入关键词开始搜索</p> : null}
        {!loading && error ? <p className="hint">{error}</p> : null}
        {!loading && !error ? results.map((result, idx) => (
          <div
            key={`${result.id || result.source || 'result'}-${idx}`}
            className="search-result"
            onClick={() => onResultClick(result)}
          >
            <div className="result-title">{result.title}</div>
            <div className="result-preview">{result.content_preview}</div>
            <div className="result-meta">
              <span className="result-score">⭐ {((result.score || 0) * 100).toFixed(1)}%</span>
              <span>{result.source}</span>
              <span>{Array.isArray(result.tags) ? result.tags.join(', ') : ''}</span>
            </div>
          </div>
        )) : null}
      </div>
    </div>
  );
}

function ReactGraphView({ active }) {
  const [minSimilarity, setMinSimilarity] = useState(0.7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [graphData, setGraphData] = useState(null);
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  const loadGraphData = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await requestJson(`/api/graph?min_similarity=${minSimilarity}`);
      setGraphData(data || { nodes: [], edges: [] });
    } catch (err) {
      setError(err.message || 'Failed to load graph');
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) {
      loadGraphData();
    }
  }, [active]);

  useEffect(() => {
    if (!active) return;
    if (!graphData || !containerRef.current) return;

    if (networkRef.current) {
      networkRef.current.destroy();
      networkRef.current = null;
    }

    const nodes = Array.isArray(graphData.nodes) ? graphData.nodes : [];
    const edges = Array.isArray(graphData.edges) ? graphData.edges : [];

    if (!nodes.length) return;
    if (!window.vis || !window.vis.DataSet || !window.vis.Network) return;

    const visNodes = new window.vis.DataSet(
      nodes.map((node) => ({
        id: node.id,
        label: node.title || node.id,
        title: `Score: ${node.score?.toFixed ? node.score.toFixed(2) : node.score ?? 'N/A'}`,
        color: {
          background: '#1565c0',
          border: '#0d47a1',
        },
      }))
    );

    const visEdges = new window.vis.DataSet(
      edges.map((edge) => ({
        from: edge.source,
        to: edge.target,
        value: edge.weight,
        title: `Similarity: ${edge.weight?.toFixed ? edge.weight.toFixed(2) : edge.weight ?? 'N/A'}`,
      }))
    );

    const options = {
      nodes: {
        shape: 'dot',
        size: 16,
        font: {
          color: '#ffffff',
          size: 14,
        },
      },
      edges: {
        color: {
          color: '#90a4ae',
          highlight: '#1565c0',
        },
        smooth: {
          type: 'continuous',
        },
      },
      physics: {
        stabilization: false,
        barnesHut: {
          gravitationalConstant: -2000,
          centralGravity: 0.3,
          springLength: 95,
          springConstant: 0.04,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
      },
    };

    const network = new window.vis.Network(
      containerRef.current,
      { nodes: visNodes, edges: visEdges },
      options
    );
    networkRef.current = network;

    network.on('click', (params) => {
      if (!params?.nodes?.length) return;
      const noteId = params.nodes[0];
      if (window.openNoteDetail) {
        window.openNoteDetail(noteId);
      }
    });

    return () => {
      if (networkRef.current) {
        networkRef.current.destroy();
        networkRef.current = null;
      }
    };
  }, [active, graphData]);

  return (
    <div id="graph-view" className={`view ${active ? 'active' : ''}`}>
      <h1 className="page-title" data-i18n="view.graph.title">🕸️ 知识图谱</h1>
      <div className="panel">
        <div className="graph-controls">
          <label>
            <span data-i18n="graph.min_similarity">最小相似度:</span>
            <input
              type="range"
              min="0.5"
              max="0.95"
              step="0.05"
              value={minSimilarity}
              onChange={(e) => setMinSimilarity(Number(e.target.value || 0.7))}
            />
            <span>{minSimilarity.toFixed(2)}</span>
          </label>
          <button className="btn btn-secondary" data-i18n="action.refresh" onClick={loadGraphData} disabled={loading}>
            刷新
          </button>
        </div>
        <div ref={containerRef} className="graph-container"></div>
        {!loading && error ? <p className="hint">{error}</p> : null}
        {!loading && !error && graphData && Array.isArray(graphData.nodes) && graphData.nodes.length === 0 ? (
          <p className="hint">No graph data available</p>
        ) : null}
      </div>
    </div>
  );
}

function splitNotesByDirectory(notes) {
  const groups = new Map();
  (notes || []).forEach((note) => {
    const id = String(note?.id || '');
    const idx = id.lastIndexOf('/');
    const dir = idx > 0 ? id.slice(0, idx) : '(root)';
    if (!groups.has(dir)) {
      groups.set(dir, []);
    }
    groups.get(dir).push(note);
  });

  return Array.from(groups.entries())
    .map(([dir, items]) => ({
      dir,
      items: items.slice().sort((a, b) => String(a?.title || '').localeCompare(String(b?.title || ''))),
    }))
    .sort((a, b) => {
      if (a.dir === '(root)') return -1;
      if (b.dir === '(root)') return 1;
      return a.dir.localeCompare(b.dir);
    });
}

function ReactNotesView({ active }) {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sourcePath, setSourcePath] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [hint, setHint] = useState('');

  const loadNotesData = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await requestJson('/api/notes');
      setNotes(Array.isArray(data?.notes) ? data.notes : []);
    } catch (err) {
      setError(err.message || 'Failed to load notes');
      setNotes([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) {
      loadNotesData();
    }
  }, [active]);

  const grouped = useMemo(() => splitNotesByDirectory(notes), [notes]);

  const onOpenNote = (note) => {
    if (!note) return;
    if (window.openNoteDetail) {
      window.openNoteDetail(note.id || '');
    }
  };

  const onRegenerateBySource = async () => {
    const value = String(sourcePath || '').trim();
    if (!value) {
      setHint('请先输入源文件路径');
      return;
    }

    setSubmitting(true);
    setHint('');
    try {
      const result = await requestJson('/api/regenerate-source', {
        method: 'POST',
        body: JSON.stringify({ source_path: value }),
      });

      if (result?.success) {
        setHint('重新生成成功');
        await loadNotesData();
      } else {
        setHint(`重新生成失败: ${result?.message || 'Unknown error'}`);
      }
    } catch (err) {
      setHint(`重新生成失败: ${err.message || 'Unknown error'}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div id="notes-view" className={`view ${active ? 'active' : ''}`}>
      <h1 className="page-title" data-i18n="view.notes.title">📝 笔记管理</h1>

      <div className="panel">
        <h2 className="panel-title" data-i18n="notes.regenerate_source_title">🎯 按指定源文件重新生成</h2>
        <div className="source-regenerate-row">
          <input
            type="text"
            id="source-file-input"
            className="search-input"
            placeholder="输入源文件绝对路径，例如 /Users/xxx/Desktop/xxx.txt"
            data-i18n-placeholder="notes.source_input_placeholder"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onRegenerateBySource();
              }
            }}
          />
          <button
            className="btn btn-primary"
            id="btn-regenerate-source"
            data-i18n="notes.regenerate_source_action"
            onClick={onRegenerateBySource}
            disabled={submitting}
          >
            重新生成该文件笔记
          </button>
        </div>
        <p className="hint source-regenerate-hint" data-i18n="notes.source_regenerate_hint">仅支持当前 input.sources 配置范围内且扩展名受支持的源文件。</p>
        {hint ? <p className="hint">{hint}</p> : null}
      </div>

      <div className="notes-grid" id="notes-grid">
        {loading ? <p className="loading" data-i18n="common.loading">加载中...</p> : null}
        {!loading && error ? <p className="hint">{error}</p> : null}
        {!loading && !error && grouped.length === 0 ? <p className="hint" data-i18n="common.no_records">暂无记录</p> : null}

        {!loading && !error
          ? grouped.map((group) => (
              <div className="panel" key={group.dir}>
                <h2 className="panel-title">📁 {group.dir} ({group.items.length})</h2>
                <div className="search-results">
                  {group.items.map((note) => (
                    <div className="note-card" key={note.id} onClick={() => onOpenNote(note)}>
                      <div className="note-title">{note.title}</div>
                      <div className="note-meta">
                        <span>{note.id}</span>
                        <span>{formatDateTime(note.modified)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          : null}
      </div>
    </div>
  );
}

function ReactConfigView({ active }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [hint, setHint] = useState('');

  const [rawYaml, setRawYaml] = useState('');
  const [snapshotText, setSnapshotText] = useState('{}');

  const [maxIterations, setMaxIterations] = useState('3');
  const [qualityThreshold, setQualityThreshold] = useState('0.8');
  const [incremental, setIncremental] = useState(true);
  const [parallel, setParallel] = useState(true);
  const [maxWorkers, setMaxWorkers] = useState('4');
  const [enableVectorStore, setEnableVectorStore] = useState(true);
  const [logRetentionDays, setLogRetentionDays] = useState('15');

  const [llmSharedText, setLlmSharedText] = useState('{}');
  const [llmPlannerText, setLlmPlannerText] = useState('{}');
  const [llmExecutorText, setLlmExecutorText] = useState('{}');
  const [llmValidatorText, setLlmValidatorText] = useState('{}');

  const [supportedExtensionsText, setSupportedExtensionsText] = useState('[]');
  const [inputSourcesText, setInputSourcesText] = useState('[]');
  const [defaultRecursive, setDefaultRecursive] = useState(true);
  const [outputPlugin, setOutputPlugin] = useState('obsidian');
  const [outputBaseDir, setOutputBaseDir] = useState('');
  const [outputVaultPath, setOutputVaultPath] = useState('');
  const [outputStructureText, setOutputStructureText] = useState('{}');
  const [outputNamingText, setOutputNamingText] = useState('{}');
  const [noteOrganizationText, setNoteOrganizationText] = useState('{}');

  const loadConfigData = async () => {
    setLoading(true);
    setError('');
    setHint('');
    try {
      const data = await requestJson('/api/config');
      const currentSnapshot = data?.current_snapshot || {};
      const rawUserConfig = data?.raw_user_config || '';
      const systemCfg = data?.system_config || {};
      const serviceCfg = systemCfg.service || {};
      const agentCfg = (data?.agent_config || {}).user_defined || {};
      const harnessCfg = currentSnapshot.harness || agentCfg.harness || {};
      const inputPref = currentSnapshot.input || (data?.user_preferences || {}).input || {};
      const outputPref = currentSnapshot.output || (data?.user_preferences || {}).output || {};

      setRawYaml(rawUserConfig || '# Empty user config');
      setSnapshotText(JSON.stringify(currentSnapshot, null, 2));

      setMaxIterations(String(harnessCfg.max_iterations ?? 3));
      setQualityThreshold(String(harnessCfg.quality_threshold ?? 0.8));
      setIncremental(Boolean(harnessCfg.incremental ?? true));
      setParallel(Boolean(harnessCfg.parallel ?? true));
      setMaxWorkers(String(harnessCfg.max_workers ?? 4));
      setEnableVectorStore(Boolean(harnessCfg.enable_vector_store ?? true));
      setLogRetentionDays(String(serviceCfg.log_retention_days ?? 15));

      setLlmSharedText(JSON.stringify(currentSnapshot.llm || agentCfg.llm_shared || {}, null, 2));
      setLlmPlannerText(JSON.stringify(currentSnapshot.llm_planner || agentCfg.llm_planner || {}, null, 2));
      setLlmExecutorText(JSON.stringify(currentSnapshot.llm_executor || agentCfg.llm_executor || {}, null, 2));
      setLlmValidatorText(JSON.stringify(currentSnapshot.llm_validator || agentCfg.llm_validator || {}, null, 2));

      setSupportedExtensionsText(JSON.stringify(inputPref.supported_extensions || [], null, 2));
      setInputSourcesText(JSON.stringify(inputPref.sources || [], null, 2));
      setDefaultRecursive(Boolean(inputPref.default_recursive ?? true));

      setOutputPlugin(outputPref.plugin || 'obsidian');
      setOutputBaseDir(outputPref.base_dir || '');
      setOutputVaultPath(outputPref.vault_path || '');
      setOutputStructureText(JSON.stringify(outputPref.structure || {}, null, 2));
      setOutputNamingText(JSON.stringify(outputPref.naming || {}, null, 2));
      setNoteOrganizationText(JSON.stringify(outputPref.note_organization || {}, null, 2));
    } catch (err) {
      setError(err?.message || tr('config.load_failed', {}, 'Failed to load config'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (active) {
      loadConfigData();
    }
  }, [active]);

  const parseJsonField = (value, fallback, label) => {
    const raw = String(value || '').trim();
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch (_) {
      throw new Error(tr('config.invalid_json_field', { field: label }, '{field} is not valid JSON'));
    }
  };

  const saveRawYaml = async () => {
    setSaving(true);
    setHint('');
    setError('');
    try {
      await requestJson('/api/config', {
        method: 'POST',
        body: JSON.stringify({ raw_user_config: rawYaml }),
      });
      setHint(tr('config.raw_saved', {}, 'YAML config saved and reloaded'));
      await loadConfigData();
    } catch (err) {
      const message = err?.message || tr('common.unknown_error', {}, 'Unknown error');
      setError(tr('error.request_failed', { message }, `Request failed: ${message}`));
    } finally {
      setSaving(false);
    }
  };

  const saveStructuredConfig = async () => {
    setSaving(true);
    setHint('');
    setError('');
    try {
      const payload = {
        system_config: {
          service: {
            log_retention_days: Number(logRetentionDays || 15),
          },
        },
        agent_config: {
          user_defined: {
            harness: {
              max_iterations: Number(maxIterations || 3),
              quality_threshold: Number(qualityThreshold || 0.8),
              incremental,
              parallel,
              max_workers: Number(maxWorkers || 4),
              enable_vector_store: enableVectorStore,
            },
            llm_shared: parseJsonField(llmSharedText, {}, 'Shared LLM Config'),
            llm_planner: parseJsonField(llmPlannerText, {}, 'Planner LLM Override'),
            llm_executor: parseJsonField(llmExecutorText, {}, 'Executor LLM Override'),
            llm_validator: parseJsonField(llmValidatorText, {}, 'Validator LLM Override'),
          },
        },
        user_preferences: {
          input: {
            default_recursive: defaultRecursive,
            supported_extensions: parseJsonField(supportedExtensionsText, [], 'Supported Extensions'),
            sources: parseJsonField(inputSourcesText, [], 'Input Source List'),
          },
          output: {
            plugin: outputPlugin,
            base_dir: outputBaseDir,
            vault_path: outputVaultPath,
            structure: parseJsonField(outputStructureText, {}, 'Output Structure'),
            naming: parseJsonField(outputNamingText, {}, 'Output Naming'),
            note_organization: parseJsonField(noteOrganizationText, {}, 'Note Organization'),
          },
        },
      };

      await requestJson('/api/config', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setHint(tr('config.saved', {}, 'Configuration saved and hot reloaded'));
      await loadConfigData();
    } catch (err) {
      if (err?.message) {
        setError(err.message);
      } else {
        setError(tr('config.save_failed', {}, 'Failed to save config, please check JSON format'));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div id="config-view" className={`view ${active ? 'active' : ''}`}>
      <h1 className="page-title" data-i18n="view.config.title">⚙️ 配置</h1>

      {loading ? <p className="loading" data-i18n="config.loading">加载配置...</p> : null}
      {!loading && error ? <p className="hint">{error}</p> : null}
      {!loading && hint ? <p className="hint">{hint}</p> : null}

      <div className="panel">
        <h2 className="panel-title" data-i18n="config.page.current_config.snapshot">当前配置快照</h2>
        <pre className="json-preview config-tall-preview">{snapshotText}</pre>
      </div>

      <div className="panel">
        <h2 className="panel-title" data-i18n="config.page.current_config.raw_yaml">YAML 配置（直接编辑）</h2>
        <textarea className="form-input json-input config-tall-preview" value={rawYaml} onChange={(e) => setRawYaml(e.target.value)} />
        <div className="quick-actions">
          <button className="btn btn-secondary" onClick={saveRawYaml} disabled={saving} data-i18n="config.page.actions.save_yaml">保存 YAML 配置</button>
        </div>
      </div>

      <div className="panel">
        <h2 className="panel-title" data-i18n="config.page.current_config.title">结构化配置</h2>

        <div className="config-grid-2">
          <div className="config-card">
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.agent.max_iterations">Harness Max Iterations</label>
              <input className="form-input" type="number" min="1" max="10" value={maxIterations} onChange={(e) => setMaxIterations(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.agent.quality_threshold">Harness Quality Threshold</label>
              <input className="form-input" type="number" min="0" max="1" step="0.05" value={qualityThreshold} onChange={(e) => setQualityThreshold(e.target.value)} />
            </div>
            <div className="form-group form-checkbox">
              <input type="checkbox" checked={incremental} onChange={(e) => setIncremental(e.target.checked)} />
              <label data-i18n="config.page.agent.incremental">Incremental Processing</label>
            </div>
            <div className="form-group form-checkbox">
              <input type="checkbox" checked={parallel} onChange={(e) => setParallel(e.target.checked)} />
              <label data-i18n="config.page.agent.parallel">Parallel Processing</label>
            </div>
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.agent.max_workers">Parallel Worker Count</label>
              <input className="form-input" type="number" min="1" max="32" value={maxWorkers} onChange={(e) => setMaxWorkers(e.target.value)} />
            </div>
            <div className="form-group form-checkbox">
              <input type="checkbox" checked={enableVectorStore} onChange={(e) => setEnableVectorStore(e.target.checked)} />
              <label data-i18n="config.page.agent.enable_vector_store">Enable Vector Store</label>
            </div>
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.system.log_retention_days">Log Retention Days</label>
              <input className="form-input" type="number" min="0" value={logRetentionDays} onChange={(e) => setLogRetentionDays(e.target.value)} />
            </div>
          </div>

          <div className="config-card">
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.user.output_plugin">Output Plugin</label>
              <select className="form-input" value={outputPlugin} onChange={(e) => setOutputPlugin(e.target.value)}>
                <option value="obsidian">Obsidian</option>
                <option value="plain">Plain Markdown</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.user.output_dir">Output Directory</label>
              <input className="form-input" type="text" value={outputBaseDir} onChange={(e) => setOutputBaseDir(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label" data-i18n="config.page.user.vault_path">Vault Path</label>
              <input className="form-input" type="text" value={outputVaultPath} onChange={(e) => setOutputVaultPath(e.target.value)} />
            </div>
            <div className="form-group form-checkbox">
              <input type="checkbox" checked={defaultRecursive} onChange={(e) => setDefaultRecursive(e.target.checked)} />
              <label data-i18n="config.page.user.default_recursive">Default Recursive for Input Sources</label>
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" data-i18n="config.page.agent.llm_shared">Shared LLM Config (JSON)</label>
          <textarea className="form-input json-input" rows="6" value={llmSharedText} onChange={(e) => setLlmSharedText(e.target.value)} />
        </div>
        <div className="config-grid-2">
          <div className="form-group">
            <label className="form-label" data-i18n="config.page.agent.llm_planner">Planner LLM Override (JSON)</label>
            <textarea className="form-input json-input" rows="5" value={llmPlannerText} onChange={(e) => setLlmPlannerText(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" data-i18n="config.page.agent.llm_executor">Executor LLM Override (JSON)</label>
            <textarea className="form-input json-input" rows="5" value={llmExecutorText} onChange={(e) => setLlmExecutorText(e.target.value)} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label" data-i18n="config.page.agent.llm_validator">Validator LLM Override (JSON)</label>
          <textarea className="form-input json-input" rows="5" value={llmValidatorText} onChange={(e) => setLlmValidatorText(e.target.value)} />
        </div>

        <div className="config-grid-2">
          <div className="form-group">
            <label className="form-label" data-i18n="config.page.user.supported_extensions">Supported Extensions (JSON Array)</label>
            <textarea className="form-input json-input" rows="5" value={supportedExtensionsText} onChange={(e) => setSupportedExtensionsText(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" data-i18n="config.page.user.input_sources">Input Source List (JSON)</label>
            <textarea className="form-input json-input" rows="5" value={inputSourcesText} onChange={(e) => setInputSourcesText(e.target.value)} />
          </div>
        </div>

        <div className="config-grid-2">
          <div className="form-group">
            <label className="form-label" data-i18n="config.page.user.output_structure">Output Structure (JSON)</label>
            <textarea className="form-input json-input" rows="4" value={outputStructureText} onChange={(e) => setOutputStructureText(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" data-i18n="config.page.user.naming_rules">Naming Rules (JSON)</label>
            <textarea className="form-input json-input" rows="4" value={outputNamingText} onChange={(e) => setOutputNamingText(e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" data-i18n="config.page.user.note_organization">Note Organization Rules (JSON)</label>
          <textarea className="form-input json-input" rows="8" value={noteOrganizationText} onChange={(e) => setNoteOrganizationText(e.target.value)} />
        </div>

        <div className="quick-actions">
          <button className="btn btn-primary" onClick={saveStructuredConfig} disabled={saving} data-i18n="config.page.actions.save_all">保存结构化配置</button>
        </div>
      </div>
    </div>
  );
}

function ReactTemplatesView({ active }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hint, setHint] = useState('');
  const [selectedName, setSelectedName] = useState('');
  const [detail, setDetail] = useState(null);
  const [editName, setEditName] = useState('');
  const [editContent, setEditContent] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTags, setEditTags] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewVars, setPreviewVars] = useState({});
  const [previewOutput, setPreviewOutput] = useState('');
  const [previewMissing, setPreviewMissing] = useState([]);
  const [versions, setVersions] = useState([]);
  const [tagFilter, setTagFilter] = useState('');

  const loadTemplates = async (focusName) => {
    setLoading(true);
    setError('');
    try {
      const query = tagFilter ? `?tag=${encodeURIComponent(tagFilter)}` : '';
      const data = await requestJson(`/api/templates${query}`);
      const list = Array.isArray(data?.templates) ? data.templates : [];
      setTemplates(list);
      if (focusName && list.some((t) => t.name === focusName)) {
        await loadDetail(focusName);
      } else if (!selectedName && list.length > 0) {
        await loadDetail(list[0].name);
      }
    } catch (err) {
      setError(err.message || 'Failed to load templates');
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (name) => {
    if (!name) return;
    setError('');
    try {
      const data = await requestJson(`/api/templates/${encodeURIComponent(name)}`);
      setSelectedName(name);
      setDetail(data);
      setEditName(data.name || '');
      setEditContent(data.content || '');
      setEditDescription(data.description || '');
      setEditTags(Array.isArray(data.tags) ? data.tags.join(', ') : '');
      setIsCreating(false);
      const initialVars = {};
      (data.variables || []).forEach((v) => {
        initialVars[v.name] = v.default_value || '';
      });
      setPreviewVars(initialVars);
      setPreviewOutput('');
      setPreviewMissing([]);

      try {
        const verData = await requestJson(`/api/templates/${encodeURIComponent(name)}/versions`);
        setVersions(Array.isArray(verData?.versions) ? verData.versions : []);
      } catch (_) {
        setVersions([]);
      }
    } catch (err) {
      setError(err.message || 'Failed to load template');
      setDetail(null);
    }
  };

  useEffect(() => {
    if (active) {
      loadTemplates();
    }
  }, [active]);

  useEffect(() => {
    if (active) {
      loadTemplates(selectedName);
    }
  }, [tagFilter]);

  const onCreateNew = () => {
    setIsCreating(true);
    setSelectedName('');
    setDetail(null);
    setEditName('');
    setEditContent('');
    setEditDescription('');
    setEditTags('');
    setPreviewVars({});
    setPreviewOutput('');
    setPreviewMissing([]);
    setVersions([]);
  };

  const onSave = async () => {
    setSaving(true);
    setHint('');
    setError('');
    try {
      const tagsArr = String(editTags || '')
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);

      if (isCreating) {
        if (!editName.trim()) {
          setError('Template name is required');
          setSaving(false);
          return;
        }
        const created = await requestJson('/api/templates', {
          method: 'POST',
          body: JSON.stringify({
            name: editName.trim(),
            content: editContent,
            description: editDescription,
            tags: tagsArr,
          }),
        });
        setHint(`Created template: ${created.name}`);
        await loadTemplates(created.name);
      } else {
        if (!selectedName) {
          setError('No template selected');
          setSaving(false);
          return;
        }
        const updated = await requestJson(`/api/templates/${encodeURIComponent(selectedName)}`, {
          method: 'PUT',
          body: JSON.stringify({
            content: editContent,
            description: editDescription,
            tags: tagsArr,
          }),
        });
        setHint(`Updated template: ${updated.name} (v${updated.version})`);
        await loadTemplates(selectedName);
      }
    } catch (err) {
      setError(err.message || 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!selectedName) return;
    if (!window.confirm(`Delete template "${selectedName}"? This cannot be undone.`)) {
      return;
    }
    setSaving(true);
    setHint('');
    setError('');
    try {
      await requestJson(`/api/templates/${encodeURIComponent(selectedName)}`, {
        method: 'DELETE',
      });
      setHint(`Deleted: ${selectedName}`);
      setSelectedName('');
      setDetail(null);
      await loadTemplates();
    } catch (err) {
      setError(err.message || 'Failed to delete template');
    } finally {
      setSaving(false);
    }
  };

  const onPreview = async () => {
    if (!selectedName) return;
    setError('');
    setHint('');
    setPreviewOutput('');
    setPreviewMissing([]);
    try {
      const data = await requestJson(`/api/templates/${encodeURIComponent(selectedName)}/preview`, {
        method: 'POST',
        body: JSON.stringify({ variables: previewVars }),
      });
      setPreviewOutput(data?.rendered || '');
    } catch (err) {
      let parsed = null;
      try {
        const match = String(err.message || '').match(/\{.*\}$/);
        if (match) parsed = JSON.parse(match[0]);
      } catch (_) {
        parsed = null;
      }
      if (parsed && Array.isArray(parsed.missing_variables)) {
        setPreviewMissing(parsed.missing_variables);
      }
      setError(err.message || 'Preview failed');
    }
  };

  const onRollback = async (version) => {
    if (!selectedName || !version) return;
    if (!window.confirm(`Rollback "${selectedName}" to v${version}?`)) {
      return;
    }
    setSaving(true);
    setHint('');
    setError('');
    try {
      await requestJson(`/api/templates/${encodeURIComponent(selectedName)}/rollback`, {
        method: 'POST',
        body: JSON.stringify({ version }),
      });
      setHint(`Rolled back to v${version}`);
      await loadDetail(selectedName);
    } catch (err) {
      setError(err.message || 'Rollback failed');
    } finally {
      setSaving(false);
    }
  };

  const tagSet = useMemo(() => {
    const all = new Set();
    templates.forEach((t) => (t.tags || []).forEach((tag) => all.add(tag)));
    return Array.from(all).sort();
  }, [templates]);

  return (
    <div id="templates-view" className={`view ${active ? 'active' : ''}`}>
      <h1 className="page-title" data-i18n="view.templates.title">📋 提示词模板</h1>

      {loading ? <p className="loading">Loading templates...</p> : null}
      {!loading && error ? <p className="hint">{error}</p> : null}
      {!loading && hint ? <p className="hint">{hint}</p> : null}

      <div className="config-grid-2">
        <div className="panel">
          <h2 className="panel-title">📚 模板列表 ({templates.length})</h2>
          <div className="quick-actions">
            <button className="btn btn-primary" onClick={onCreateNew}>+ 新建模板</button>
            <button className="btn btn-secondary" onClick={() => loadTemplates(selectedName)}>刷新</button>
          </div>
          <div className="form-group">
            <label className="form-label">Filter by tag</label>
            <select className="form-input" value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
              <option value="">All tags</option>
              {tagSet.map((tag) => (
                <option key={tag} value={tag}>{tag}</option>
              ))}
            </select>
          </div>
          <div className="search-results">
            {templates.map((t) => (
              <div
                key={t.name}
                className={`note-card ${selectedName === t.name ? 'active' : ''}`}
                onClick={() => loadDetail(t.name)}
              >
                <div className="note-title">{t.name}</div>
                <div className="note-meta">
                  <span>v{t.version}</span>
                  <span>{(t.tags || []).join(', ')}</span>
                </div>
                {t.description ? <div className="result-preview">{t.description}</div> : null}
              </div>
            ))}
            {templates.length === 0 && !loading ? <p className="hint">暂无模板</p> : null}
          </div>
        </div>

        <div className="panel">
          <h2 className="panel-title">
            {isCreating ? '🆕 新建模板' : (selectedName ? `✏️ 编辑: ${selectedName}` : '请选择模板')}
          </h2>

          {(isCreating || selectedName) ? (
            <div>
              {isCreating ? (
                <div className="form-group">
                  <label className="form-label">Name</label>
                  <input
                    className="form-input"
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="my_template_name"
                  />
                </div>
              ) : null}
              <div className="form-group">
                <label className="form-label">Description</label>
                <input
                  className="form-input"
                  type="text"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Tags (comma-separated)</label>
                <input
                  className="form-input"
                  type="text"
                  value={editTags}
                  onChange={(e) => setEditTags(e.target.value)}
                  placeholder="extraction, custom"
                />
              </div>
              <div className="form-group">
                <label className="form-label">
                  Content (use {'{{var_name}}'} for variables)
                </label>
                <textarea
                  className="form-input json-input config-tall-preview"
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                />
              </div>
              <div className="quick-actions">
                <button className="btn btn-primary" onClick={onSave} disabled={saving}>
                  {isCreating ? '创建模板' : '保存（生成新版本）'}
                </button>
                {!isCreating ? (
                  <button className="btn btn-warning" onClick={onDelete} disabled={saving}>
                    删除模板
                  </button>
                ) : null}
              </div>
            </div>
          ) : (
            <p className="hint">在左侧选择一个模板进行编辑，或点击"新建模板"创建。</p>
          )}
        </div>
      </div>

      {detail && !isCreating ? (
        <div className="config-grid-2">
          <div className="panel">
            <h2 className="panel-title">🧪 变量预览</h2>
            {(detail.variables || []).length === 0 ? (
              <p className="hint">此模板没有变量</p>
            ) : (
              <div>
                {(detail.variables || []).map((v) => (
                  <div className="form-group" key={v.name}>
                    <label className="form-label">
                      {v.name}{v.required ? ' *' : ''}
                      {previewMissing.includes(v.name) ? <span style={{ color: 'crimson' }}> (missing)</span> : null}
                    </label>
                    <textarea
                      className="form-input"
                      rows="2"
                      value={previewVars[v.name] || ''}
                      onChange={(e) => setPreviewVars({ ...previewVars, [v.name]: e.target.value })}
                      placeholder={v.default_value || ''}
                    />
                  </div>
                ))}
                <div className="quick-actions">
                  <button className="btn btn-primary" onClick={onPreview}>渲染预览</button>
                </div>
              </div>
            )}
            {previewOutput ? (
              <div className="form-group">
                <label className="form-label">渲染结果</label>
                <pre className="json-preview config-tall-preview">{previewOutput}</pre>
              </div>
            ) : null}
          </div>

          <div className="panel">
            <h2 className="panel-title">📜 版本历史 ({versions.length})</h2>
            {versions.length === 0 ? (
              <p className="hint">暂无版本历史</p>
            ) : (
              <div className="search-results">
                {versions.map((v, idx) => (
                  <div className="note-card" key={`${v.version}-${idx}`}>
                    <div className="note-title">
                      v{v.version} {v.is_active ? '✅' : ''}
                    </div>
                    <div className="note-meta">
                      <span>{formatDateTime(v.created_at_iso)}</span>
                      {v.author ? <span>by {v.author}</span> : null}
                    </div>
                    {v.change_log ? <div className="result-preview">{v.change_log}</div> : null}
                    {!v.is_active ? (
                      <div className="quick-actions">
                        <button className="btn btn-secondary btn-sm" onClick={() => onRollback(v.version)}>
                          回滚到此版本
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LuminaShell() {
  const [view, setView] = useState('dashboard');
  const [locale, setLocale] = useState(localStorage.getItem(LOCALE_KEY) || 'auto');

  useEffect(() => {
    window.dispatchEvent(new CustomEvent('lumina:locale-preference-changed', { detail: { value: locale } }));
  }, [locale]);

  const navItems = [
    { key: 'dashboard', label: '仪表板', i18n: 'nav.dashboard' },
    { key: 'search', label: '搜索', i18n: 'nav.search' },
    { key: 'graph', label: '知识图谱', i18n: 'nav.graph' },
    { key: 'notes', label: '笔记管理', i18n: 'nav.notes' },
    { key: 'templates', label: '提示词', i18n: 'nav.templates' },
    { key: 'config', label: '配置', i18n: 'nav.config' },
  ];

  return (
    <div className="app">
      <nav className="navbar">
        <div className="logo">
          <span className="logo-icon material-symbols-outlined">auto_awesome</span>
          <span className="logo-text">Lumina</span>
        </div>
        <div className="nav-links">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={`nav-btn ${view === item.key ? 'active' : ''}`}
              onClick={() => setView(item.key)}
              data-i18n={item.i18n}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="nav-controls">
          <label className="locale-label" htmlFor="locale-selector" data-i18n="locale.label">Language</label>
          <select
            id="locale-selector"
            className="locale-selector"
            aria-label="Language selector"
            value={locale}
            onChange={(e) => {
              const value = String(e.target.value || 'auto');
              localStorage.setItem(LOCALE_KEY, value);
              setLocale(value);
            }}
          >
            <option value="auto">Auto (Follow Browser)</option>
            <option value="en">English</option>
            <option value="zh-CN">简体中文</option>
            <option value="zh-TW">繁体中文</option>
            <option value="hi">हिन्दी</option>
            <option value="es">Español</option>
            <option value="fr">Français</option>
            <option value="ar">العربية</option>
            <option value="bn">বাংলা</option>
            <option value="pt">Português</option>
            <option value="ru">Русский</option>
            <option value="ur">اردو</option>
            <option value="ja">日本語</option>
            <option value="ko">한국어</option>
          </select>
        </div>
      </nav>

      <main className="main-content">
        {view === 'dashboard' ? <DashboardView /> : null}
        {view === 'search' ? <SearchView /> : null}
        <ReactGraphView active={view === 'graph'} />
        <ReactNotesView active={view === 'notes'} />
        <ReactTemplatesView active={view === 'templates'} />
        <ReactConfigView active={view === 'config'} />
      </main>

      <div id="note-modal" className="modal hidden">
        <div className="modal-content">
          <div className="modal-header">
            <h2 id="modal-title" data-i18n="notes.modal_title">笔记详情</h2>
            <button className="modal-close" id="btn-close-modal">&times;</button>
          </div>
          <div className="modal-body" id="modal-body"></div>
          <div className="modal-footer">
            <button className="btn btn-secondary" id="btn-close-modal-2" data-i18n="action.close">关闭</button>
            <button className="btn btn-primary" id="btn-regenerate" data-i18n="action.regenerate">重新生成</button>
          </div>
        </div>
      </div>

      <div id="failure-modal" className="modal hidden">
        <div className="modal-content modal-content-narrow">
          <div className="modal-header">
            <h2 data-i18n="failure.modal.title">失败详情</h2>
            <button className="modal-close" id="btn-close-failure-modal">&times;</button>
          </div>
          <div className="modal-body">
            <div className="failure-toolbar">
              <label className="failure-select-all">
                <input type="checkbox" id="failure-select-all" />
                <span data-i18n="failure.select_all">全选</span>
              </label>
              <div className="failure-toolbar-actions">
                <input type="text" id="failure-tag-input" className="form-input failure-tag-input" placeholder="输入标签，逗号分隔" data-i18n-placeholder="failure.tag_input_placeholder" />
                <button className="btn btn-secondary btn-sm" id="btn-failure-tag" data-i18n="failure.batch_tag">批量打标签</button>
                <button className="btn btn-secondary btn-sm" id="btn-failure-export" data-i18n="action.export">导出</button>
                <button className="btn btn-warning btn-sm" id="btn-failure-regenerate" data-i18n="failure.batch_regenerate">批量重生成</button>
                <button className="btn btn-secondary btn-sm" id="btn-failure-delete" data-i18n="action.delete">删除记录</button>
              </div>
            </div>
            <div id="failure-modal-body"></div>
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary" id="btn-close-failure-modal-2" data-i18n="action.close">关闭</button>
          </div>
        </div>
      </div>

      <div id="loading-overlay" className="overlay hidden">
        <div className="spinner"></div>
        <p className="loading-text" data-i18n="scan.running">处理中...</p>
      </div>

      <div id="toast" className="toast hidden">
        <span id="toast-message"></span>
      </div>
    </div>
  );
}

window.__LUMINA_REACT_MODE__ = true;

const root = ReactDOM.createRoot(document.getElementById('react-root'));
root.render(<LuminaShell />);

window.__LUMINA_REACT_READY__ = true;
window.dispatchEvent(new CustomEvent('lumina:react-ready'));
