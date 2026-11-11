import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Clock,
  FileSearch,
  Layers,
  Sparkles,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react';
import { getErrorMessage, getOverview } from '../api/client';
import type { Overview } from '../types';

const STATUS_CLASS: Record<string, string> = {
  研判中: 'status-研判中',
  整改中: 'status-整改中',
  已关闭: 'status-已关闭',
  待确认: 'status-待确认',
};

export default function DashboardPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    getOverview()
      .then(setData)
      .catch((err) => setError(getErrorMessage(err, '加载工作台失败')));
  }, []);

  const maxTrend = useMemo(
    () => Math.max(1, ...(data?.trend.map((t) => t.count) ?? [1])),
    [data]
  );
  const maxCause = useMemo(
    () => Math.max(1, ...(data?.by_cause.map((t) => t.count) ?? [1])),
    [data]
  );

  if (error) {
    return (
      <div className="page">
        <div className="error-box">{error}</div>
      </div>
    );
  }

  if (!data) {
    return <div className="loading">正在加载质量数据…</div>;
  }

  const k = data.kpis;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">质量工作台</h1>
          <p className="page-desc">
            一屏看清今天要处理的、最近发生的、以及需要关注的质量问题。覆盖 11 台整机、100 条报修单与 5 条预警规则。
          </p>
        </div>
        <div className="header-actions">
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/issues')}>
            <FileSearch size={15} />
            问题列表
          </button>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/kb')}>
            <Sparkles size={15} />
            查技术协议
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">
            <Layers size={14} />
            质量问题
          </div>
          <div className="kpi-value">
            {k.issue_total}
            <small>条</small>
          </div>
          <div className="kpi-foot">覆盖 {k.machine_total} 台整机 · 售后 / 检验 / 反馈函</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">
            <Clock size={14} />
            待处理问题
          </div>
          <div className="kpi-value">
            {k.issue_open}
            <small>条</small>
          </div>
          <div className="kpi-foot">研判中 / 整改中</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">
            <TriangleAlert size={14} />
            待确认预警
          </div>
          <div className="kpi-value">
            {k.alert_pending}
            <small>条</small>
          </div>
          <div className="kpi-foot">按故障类型 / 原因 / 厂家 / 部件归集</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">
            <TrendingUp size={14} />
            平均闭环
          </div>
          <div className="kpi-value">
            {k.avg_close_days}
            <small>天</small>
          </div>
          <div className="kpi-foot">质量链完整度 {k.chain_completeness}% · 条款 {k.clause_total} 条</div>
        </div>
      </div>

      <div className="dash-grid">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="section-title">质量问题趋势</div>
              <div className="section-sub">近 12 个月，按发现日期统计</div>
            </div>
            <span className="demo-tag">演示数据</span>
          </div>
          <div className="trend">
            {data.trend.map((t) => (
              <div className="trend-col" key={t.month}>
                <div
                  className="trend-bar"
                  style={{
                    height: t.count === 0 ? '2px' : `${10 + (t.count / maxTrend) * 120}px`,
                    opacity: t.count === 0 ? 0.35 : 1,
                    background: t.count === 0 ? '#cbd5e1' : undefined,
                  }}
                  title={`${t.month}：${t.count} 条`}
                >
                  {t.count > 0 && <span>{t.count}</span>}
                </div>
                <div className="trend-label">{t.month.slice(5)}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="section-title">原因分布</div>
              <div className="section-sub">归一后的责任类型</div>
            </div>
          </div>
          <div className="bar-list">
            {data.by_cause.map((c) => (
              <div className="bar-row" key={c.name}>
                <div className="bar-name">{c.name}</div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${(c.count / maxCause) * 100}%` }} />
                </div>
                <div className="bar-value">{c.count}</div>
              </div>
            ))}
          </div>
          <div className="card-header" style={{ marginTop: 18, marginBottom: 8 }}>
            <div className="section-title" style={{ fontSize: 13 }}>
              高频部件
            </div>
          </div>
          <div className="ask-chips">
            {data.top_components.map((c) => (
              <span className="chip" key={c.name}>
                {c.name} · {c.count}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="dash-bottom">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="section-title">最近质量问题</div>
              <div className="section-sub">点击查看 AI 研判与质量链</div>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/issues')}>
              全部 <ArrowRight size={13} />
            </button>
          </div>
          <div className="recent-list">
            {data.recent_issues.map((it) => (
              <div
                className="recent-item"
                key={it.id}
                onClick={() => navigate(`/issues/${it.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && navigate(`/issues/${it.id}`)}
              >
                <div className="recent-date">{it.date.slice(5)}</div>
                <div className="recent-main">
                  <div className="recent-title">
                    {it.machine_id} · {it.component} · {it.phenomenon}
                  </div>
                  <div className="recent-meta">
                    {it.repair_no} · {it.customer} · 原因：{it.cause}
                  </div>
                </div>
                <span className={`status-badge ${STATUS_CLASS[it.status] ?? 'status-待确认'}`}>{it.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="section-title">预警速览</div>
              <div className="section-sub">高频问题模式，需人工确认</div>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/alerts')}>
              全部 <ArrowRight size={13} />
            </button>
          </div>
          <div className="recent-list">
            {data.alerts.map((a) => (
              <div
                className="recent-item"
                key={a.alert_no}
                onClick={() => navigate('/alerts')}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && navigate('/alerts')}
              >
                <span className={`status-badge level-${a.level}`}>{a.level}</span>
                <div className="recent-main">
                  <div className="recent-title">{a.rule_name}</div>
                  <div className="recent-meta">{a.condition_text}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
