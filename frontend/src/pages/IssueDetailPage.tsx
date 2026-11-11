import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Check,
  Copy,
  Lightbulb,
  Link2,
  Sparkles,
  TriangleAlert,
} from 'lucide-react';
import { getErrorMessage, getIssueAnalysis } from '../api/client';
import type { Analysis, Similar } from '../types';

const CONFIDENCE_LABEL: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

const STATUS_CLASS: Record<string, string> = {
  '待派工': 'as-pending',
  '已派工-待完工': 'as-doing',
  '已完工-待评价': 'as-review',
  '已完工-已评价': 'as-done',
  '已取消': 'as-cancel',
};

function tierLabel(tier: string): string {
  return { A: 'A', B: 'B', C: 'C', D: 'D' }[tier] ?? '·';
}

function SimilarCard({ s, onOpen }: { s: Similar; onOpen: () => void }) {
  return (
    <div
      className="similar-card"
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
    >
      <div className="similar-head">
        <span className={`tier tier-${s.tier}`}>{tierLabel(s.tier)}</span>
        <div className="similar-title">
          {s.issue.issue_no} · {s.issue.phenomenon}
        </div>
        <div className="similar-score">{Math.round(s.score * 100)}%</div>
      </div>
      <div className="reasons">
        {s.reasons.map((r) => (
          <span className="reason-chip" key={r}>
            {r}
          </span>
        ))}
      </div>
      <div className="similar-foot">
        {s.issue.date} · {s.issue.machine_id} · 处置：{s.issue.handling || '—'}
        <br />
        归因：{s.issue.cause}
        {s.issue.cause_detail ? ` / ${s.issue.cause_detail}` : ''}
      </div>
    </div>
  );
}

export default function IssueDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Analysis | null>(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    setData(null);
    getIssueAnalysis(Number(id))
      .then(setData)
      .catch((err) => setError(getErrorMessage(err, '加载研判失败')));
  }, [id]);

  const copyReport = async () => {
    if (!data) return;
    const lines = [
      `质量问题分析：${data.issue.repair_no}（${data.issue.issue_no}）`,
      `整机：${data.issue.machine_id}（${data.issue.spec}） 客户：${data.issue.customer}`,
      `现象：${data.issue.phenomenon}`,
      `描述：${data.issue.description}`,
      '',
      `相似历史（${data.similar.length} 条）：`,
      ...data.similar.map(
        (s) =>
          `- ${s.issue.issue_no}（相似度 ${Math.round(s.score * 100)}%）：${s.issue.phenomenon}；处置：${s.issue.handling || '—'}；原因：${s.issue.cause}`
      ),
      '',
      `根因假设：`,
      ...data.hypotheses.map((h) => `- ${h.cause}（置信度 ${CONFIDENCE_LABEL[h.confidence] ?? h.confidence}）验证：${h.verify}`),
      '',
      `处置建议：`,
      ...data.suggestions.map((s) => `- ${s.measure}（${s.history}）`),
      '',
      `质量链：${data.chain.completeness}/${data.chain.total}`,
      ...data.chain.gaps.map((g) => `- 断点：${g}`),
      '',
      '（本结论由 AI 基于历史问题与档案生成，请核对证据后使用）',
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
    }
  };

  if (error) {
    return (
      <div className="page">
        <Link className="back-link" to="/issues">
          <ArrowLeft size={14} /> 返回问题列表
        </Link>
        <div className="error-box">{error}</div>
      </div>
    );
  }

  if (!data) {
    return <div className="loading">正在生成 AI 研判…</div>;
  }

  const { issue, machine, chain } = data;
  const strongSimilar = data.similar.filter((s) => s.tier !== 'D');
  const weakSimilar = data.similar.filter((s) => s.tier === 'D');

  return (
    <div className="page">
      <Link className="back-link" to="/issues">
        <ArrowLeft size={14} /> 返回问题列表
      </Link>

      <div className="detail-head">
        <div>
          <h1 className="detail-title">
            {issue.repair_no} · {issue.phenomenon}
          </h1>
          <div className="detail-sub">
            质量问题 {issue.issue_no} · {issue.customer} · {issue.machine_id}（{machine?.model_name}{' '}
            {machine?.spec}） · 报修 {issue.date} {issue.report_time} · 来源 {issue.source_channel}
          </div>
          <div className="tag-row">
            <span className={`status-badge ${STATUS_CLASS[issue.after_sales_status] ?? 'as-pending'}`}>
              {issue.after_sales_status}
            </span>
            <span className="status-badge" style={{ background: '#f1f5f9', color: '#475569' }}>
              定责：{issue.responsibility_status}
            </span>
            <span className="status-badge" style={{ background: '#eff6ff', color: '#1d4ed8' }}>
              质量：{issue.status}
            </span>
            <span className="status-badge" style={{ background: '#f1f5f9', color: '#475569' }}>
              {issue.component}
            </span>
            <span className="status-badge" style={{ background: '#f1f5f9', color: '#475569' }}>
              原因：{issue.cause}
            </span>
            {issue.recurrence_of && (
              <span className="status-badge" style={{ background: '#fef2f2', color: '#b91c1c' }}>
                疑似复发 #{issue.recurrence_of}
              </span>
            )}
            <span className="ai-tag">
              <Sparkles size={11} /> AI 研判 · 置信度 {CONFIDENCE_LABEL[data.confidence] ?? data.confidence}
            </span>
          </div>
        </div>
        <div className="header-actions">
          <button type="button" className="btn btn-secondary" onClick={copyReport}>
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? '已复制' : '生成分析报告'}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() =>
              navigate(`/kb?q=${encodeURIComponent('2001001111技术协议对油漆、吊钩、钢板有什么要求？')}`)
            }
          >
            <BookOpen size={15} />
            查技术协议要求
          </button>
        </div>
      </div>

      {copied && <div className="success-box">分析报告已复制到剪贴板，可直接粘贴到反馈函或邮件。</div>}

      <div className="detail-grid">
        <div className="card">
          <div className="card-header">
            <div className="section-title">问题事实</div>
            <span className="muted">售后订单 {issue.after_sales_order || '—'}</span>
          </div>
          <div className="fact-list">
            <div className="fact-row">
              <div className="fact-label">质量问题</div>
              <div className="fact-value mono">{issue.issue_no}</div>
            </div>
            <div className="fact-row">
              <div className="fact-label">客户</div>
              <div className="fact-value">{issue.customer}</div>
            </div>
            <div className="fact-row">
              <div className="fact-label">联系人</div>
              <div className="fact-value">
                {issue.contact_name}
                <span className="muted"> · {issue.contact_phone}</span>
              </div>
            </div>
            <div className="fact-row">
              <div className="fact-label">受理</div>
              <div className="fact-value">
                {issue.source_channel} · {issue.entry_method} · {issue.department}
              </div>
            </div>
            <div className="fact-row">
              <div className="fact-label">整机</div>
              <div className="fact-value">
                {issue.machine_id}
                <div className="cell-sub">
                  {machine?.model_name} · {machine?.spec}
                </div>
              </div>
            </div>
            <div className="fact-row">
              <div className="fact-label">部件</div>
              <div className="fact-value">
                {issue.component}
                <span className="muted">（{issue.component_code}）</span>
              </div>
            </div>
            <div className="fact-row">
              <div className="fact-label">故障类型</div>
              <div className="fact-value">{issue.fault_type || '—'}</div>
            </div>
            <div className="fact-row">
              <div className="fact-label">发现阶段</div>
              <div className="fact-value">{issue.stage}</div>
            </div>
            <div className="fact-row">
              <div className="fact-label">责任对象</div>
              <div className="fact-value">
                {[issue.team, issue.designer, issue.supplier].filter(Boolean).join(' / ') || '—'}
              </div>
            </div>
            <div className="fact-row">
              <div className="fact-label">批次</div>
              <div className="fact-value mono">{issue.batch || '—'}</div>
            </div>
            <div className="fact-row">
              <div className="fact-label">质保</div>
              <div className="fact-value">
                {machine?.warranty_months} 个月 · 至 {machine?.warranty_end}
              </div>
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div className="section-title" style={{ fontSize: 13, marginBottom: 6 }}>
              问题描述
            </div>
            <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
              {issue.description}
            </p>
          </div>

          {issue.cause_detail && (
            <div style={{ marginTop: 14 }}>
              <div className="section-title" style={{ fontSize: 13, marginBottom: 6 }}>
                原因说明
              </div>
              <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>{issue.cause_detail}</p>
            </div>
          )}

          {issue.handling && (
            <div style={{ marginTop: 14 }}>
              <div className="section-title" style={{ fontSize: 13, marginBottom: 6 }}>
                处置记录
              </div>
              <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                {issue.handling}
                {issue.duration_days != null && ` · ${issue.duration_days} 天闭环`}
              </p>
            </div>
          )}
        </div>

        <div className="ai-panel">
          <div className="ai-head">
            <div className="ai-head-left">
              <Sparkles size={16} color="#4338ca" />
              <div>
                <div className="section-title">AI 研判</div>
                <div className="section-sub">检索 + 规则引擎 · 每条结论可回溯证据</div>
              </div>
            </div>
            <div className="tag-row" style={{ marginTop: 0 }}>
              <span className={`confidence confidence-${data.confidence}`}>
                置信度 {CONFIDENCE_LABEL[data.confidence] ?? data.confidence}
              </span>
              <span className="muted">质量链 {data.summary.chain_completeness}</span>
            </div>
          </div>

          <div className="ai-section">
            <div className="ai-section-title">
              <Link2 size={14} /> 相似历史
              <span className="count">{data.similar.length} 条 · 命中 {data.summary.high_count} 条高度相似</span>
            </div>
            {data.similar.length === 0 && <div className="empty">未找到历史同类问题。</div>}
            {strongSimilar.map((s) => (
              <SimilarCard key={s.issue.id} s={s} onOpen={() => navigate(`/issues/${s.issue.id}`)} />
            ))}
            {weakSimilar.length > 0 && (
              <details className="more-similar">
                <summary>查看更多弱相关（{weakSimilar.length} 条）</summary>
                {weakSimilar.map((s) => (
                  <SimilarCard key={s.issue.id} s={s} onOpen={() => navigate(`/issues/${s.issue.id}`)} />
                ))}
              </details>
            )}
          </div>

          <div className="ai-section">
            <div className="ai-section-title">
              <Lightbulb size={14} /> 根因假设
              <span className="count">按证据强度排序</span>
            </div>
            {data.hypotheses.map((h, idx) => (
              <div className="hypo" key={h.cause}>
                <div className="hypo-index">{idx + 1}</div>
                <div className="hypo-body">
                  <div className="hypo-cause">
                    {h.cause}
                    <span className={`confidence confidence-${h.confidence}`} style={{ marginLeft: 8 }}>
                      {CONFIDENCE_LABEL[h.confidence] ?? h.confidence}
                    </span>
                  </div>
                  <div className="hypo-verify">验证方法：{h.verify}</div>
                  {h.evidence.length > 0 && (
                    <div className="reasons">
                      {h.evidence.map((e) => (
                        <span className="reason-chip" key={e}>
                          证据 {e}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="ai-section">
            <div className="ai-section-title">
              <Sparkles size={14} /> 处置建议
              <span className="count">按历史有效性排序</span>
            </div>
            {data.suggestions.length === 0 && (
              <div className="empty">暂无足够相似的历史处置可推荐。</div>
            )}
            {data.suggestions.map((s) => (
              <div className="suggestion" key={s.measure}>
                <ArrowUpRight size={15} color="#2563eb" style={{ flexShrink: 0, marginTop: 2 }} />
                <div className="suggestion-body">
                  <div className="suggestion-measure">{s.measure}</div>
                  <div className="suggestion-history">
                    {s.history} · 来源 {s.evidence.join('、')}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="section-title">质量链</div>
            <div className="section-sub">
              从需求到售后的七段证据链 · {chain.completeness}/{chain.total} 段有证据
            </div>
          </div>
          {chain.gaps.length > 0 && (
            <span className="status-badge" style={{ background: '#fffbeb', color: '#92400e' }}>
              {chain.gaps.length} 个断点
            </span>
          )}
        </div>

        <div className="chain">
          {chain.stages.map((stage) => (
            <div className={`chain-stage${stage.status === 'missing' ? ' missing' : ''}`} key={stage.stage}>
              <div className={`chain-dot ${stage.status}`}>{stage.status === 'ok' ? '✓' : '!'}</div>
              <div className="chain-name">{stage.stage}</div>
              <div className="chain-summary">{stage.summary}</div>
            </div>
          ))}
        </div>

        {chain.gaps.map((gap) => (
          <div className="gap-banner" key={gap}>
            <TriangleAlert size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <div>{gap}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
