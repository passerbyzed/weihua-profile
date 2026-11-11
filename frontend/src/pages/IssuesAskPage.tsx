import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  Cpu,
  FileDown,
  FileSpreadsheet,
  FileText,
  ListChecks,
  Sparkles,
  TriangleAlert,
  X,
} from 'lucide-react';
import {
  askIssues,
  generateIssueReport,
  getErrorMessage,
  getLlmStatus,
  type ReportFormat,
} from '../api/client';
import type { IssueAskResult, LlmStatus } from '../types';

const SAMPLES = [
  '最近三个月涂装问题为什么反复出现？',
  '哪些问题属于同一根因？请归类说明',
  '设计类问题集中在谁、哪类部件？',
  '给我一份本月质量问题摘要，并指出最需要先处理的 3 条',
];

const REPORT_FORMATS: { value: ReportFormat; label: string; desc: string; icon: typeof FileText }[] = [
  { value: 'excel', label: 'Excel', desc: '.xlsx · 分维度汇总 + 柱状/饼图', icon: FileSpreadsheet },
  { value: 'pdf', label: 'PDF', desc: '.pdf · 适合打印和汇报', icon: FileText },
  { value: 'doc', label: 'Word', desc: '.docx · 可直接编辑', icon: FileText },
];

export default function IssuesAskPage() {
  const initialParams = new URLSearchParams(window.location.search);
  const initialQuestion = initialParams.get('q') ?? '';
  const [question, setQuestion] = useState(initialQuestion);
  const [result, setResult] = useState<IssueAskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [reportOpen, setReportOpen] = useState(
    initialParams.get('report') === '1' && Boolean(initialQuestion)
  );
  const [reportFormat, setReportFormat] = useState<ReportFormat>('excel');
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState('');
  const [reportMsg, setReportMsg] = useState('');

  useEffect(() => {
    getLlmStatus()
      .then(setLlmStatus)
      .catch(() => undefined);
  }, []);

  const openReport = () => {
    if (!question.trim()) {
      setError('请先输入问题，再生成报表');
      return;
    }
    setError('');
    setReportError('');
    setReportMsg('');
    setReportOpen(true);
  };

  const downloadReport = async () => {
    if (!question.trim()) return;
    setReportLoading(true);
    setReportError('');
    try {
      const { blob, filename } = await generateIssueReport(question.trim(), reportFormat);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setReportOpen(false);
      setReportMsg(`报表已生成：${filename}`);
    } catch (err) {
      setReportError(getErrorMessage(err, '生成报表失败'));
    } finally {
      setReportLoading(false);
    }
  };

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q) return;
    setQuestion(q);
    setLoading(true);
    setError('');
    try {
      const res = await askIssues(q);
      setResult(res);
    } catch (err) {
      setError(getErrorMessage(err, '提问失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <Link className="back-link" to="/issues">
        <ArrowLeft size={14} /> 返回问题列表
      </Link>

      <div className="page-header">
        <div>
          <h1 className="page-title">问题库智能问答</h1>
          <p className="page-desc">
            把问题库里全部 100 条问题交给 DeepSeek 整理：找共性、归因、排序、给处置建议。回答只依据问题清单，不编造库外数据。
          </p>
        </div>
        <div className="header-actions">
          <span className={`status-badge ${llmStatus?.configured ? 'status-已关闭' : 'status-待确认'}`}>
            <Cpu size={12} style={{ marginRight: 4 }} />
            {llmStatus?.configured ? `DeepSeek · ${llmStatus.model}` : '规则摘要模式'}
          </span>
        </div>
      </div>

      {llmStatus && !llmStatus.configured && (
        <div className="gap-banner" style={{ marginBottom: 14 }}>
          <TriangleAlert size={15} />
          <div>
            未检测到 DeepSeek API Key，当前返回规则摘要。把 Key 填到{' '}
            <code>backend/.env</code> 第 3 行 <code>DEEPSEEK_API_KEY=</code> 后面，保存后重启后端即可真实调用。
          </div>
        </div>
      )}

      <div className="card">
        <label className="label">问问题库</label>
        <textarea
          className="textarea"
          rows={3}
          value={question}
          placeholder="例如：最近三个月涂装问题为什么反复出现？"
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => ask(question)}
              disabled={loading}
            >
              <Sparkles size={15} />
              {loading ? 'DeepSeek 整理中…' : '提问'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={openReport}
              disabled={!question.trim() || loading}
              title="按提问中的维度统计出现次数，导出 Excel / PDF / Word"
            >
              <FileDown size={15} />
              生成报表
            </button>
          </div>
        </div>

        <div className="ask-chips">
          {SAMPLES.map((s) => (
            <button type="button" className="chip" key={s} onClick={() => ask(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
      {reportMsg && <div className="success-box" style={{ marginTop: 14 }}>{reportMsg}</div>}

      {!result && !loading && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="empty">
            还没有提问。点上面的示例，或输入自己的问题；问题库里全部 100 条会一起交给 DeepSeek 归纳。
          </div>
        </div>
      )}

      {loading && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="loading">正在上传全部问题 → DeepSeek 归纳共性 → 生成回答…</div>
        </div>
      )}

      {result && !loading && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="answer-meta">
            <span className="ai-tag">
              <Sparkles size={11} />
              {result.mode === 'llm' ? 'DeepSeek 生成' : '规则摘要'}
            </span>
            {result.model && <span className="status-badge" style={{ background: '#f1f5f9', color: '#475569' }}>{result.model}</span>}
            <span className="muted">
              全部问题 · 共 {result.issue_count} 条
              {result.elapsed_ms ? ` · ${(result.elapsed_ms / 1000).toFixed(1)}s` : ''}
            </span>
          </div>

          {result.error && (
            <div className="gap-banner" style={{ marginBottom: 12 }}>
              <TriangleAlert size={14} />
              <div>{result.error}</div>
            </div>
          )}

          <div className="answer-conclusion" style={{ whiteSpace: 'pre-wrap', fontWeight: 500 }}>
            {result.answer}
          </div>

          {result.related.length > 0 && (
            <div className="answer-section">
              <div className="answer-section-title">
                <ListChecks size={14} /> 关联问题（点击查看研判）
              </div>
              <div className="recent-list">
                {result.related.map((it) => (
                  <div className="recent-item" key={it.id}>
                    <div className="recent-date">{it.date.slice(5)}</div>
                    <div className="recent-main">
                      <Link className="recent-title" to={`/issues/${it.id}`}>
                        {it.repair_no} · {it.machine_id} · {it.component} · {it.phenomenon}
                      </Link>
                      <div className="recent-meta">
                        质量问题 {it.issue_no} · 原因：{it.cause} · 状态：{it.status} · {it.customer}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {reportOpen && (
        <div
          className="modal-overlay"
          role="presentation"
          onClick={() => {
            if (!reportLoading) setReportOpen(false);
          }}
        >
          <div className="modal report-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <div className="modal-title">生成统计报表</div>
                <div className="modal-sub">按提问中的维度统计出现次数；多个维度分别成表</div>
              </div>
              <button
                type="button"
                className="modal-close"
                onClick={() => setReportOpen(false)}
                disabled={reportLoading}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="report-question">
                <span className="muted">提问内容</span>
                <div>{question}</div>
              </div>

              <label className="label" style={{ marginTop: 16 }}>报表格式</label>
              <div className="report-formats">
                {REPORT_FORMATS.map((format) => {
                  const Icon = format.icon;
                  return (
                    <button
                      type="button"
                      key={format.value}
                      className={`report-format ${reportFormat === format.value ? 'active' : ''}`}
                      onClick={() => setReportFormat(format.value)}
                    >
                      <Icon size={20} />
                      <div>
                        <strong>{format.label}</strong>
                        <span>{format.desc}</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="gap-banner" style={{ marginTop: 14 }}>
                <FileDown size={14} />
                <div>
                  统计口径：按问题中的部件、故障类型、原因、客户等维度计数。
                  例如同时提问「缓冲器和制动器」，报表会分别给出两个维度，不会只取第一个。
                  每个维度配月度柱状图和原因饼图，不输出问题明细。
                </div>
              </div>

              {reportError && <div className="error-box" style={{ marginTop: 12 }}>{reportError}</div>}
            </div>

            <div className="modal-foot">
              <button type="button" className="btn btn-secondary" onClick={() => setReportOpen(false)} disabled={reportLoading}>
                取消
              </button>
              <button type="button" className="btn btn-primary" onClick={downloadReport} disabled={reportLoading}>
                <FileDown size={15} />
                {reportLoading ? '生成中…' : `生成 ${REPORT_FORMATS.find((f) => f.value === reportFormat)?.label}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
