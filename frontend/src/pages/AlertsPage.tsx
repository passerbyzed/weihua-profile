import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  Clock,
  Info,
  Settings2,
  ShieldAlert,
  Sparkles,
  Wrench,
  XCircle,
} from 'lucide-react';
import {
  getAlertConfig,
  getErrorMessage,
  listAlerts,
  saveAlertNote,
  suggestAlert,
  updateAlert,
} from '../api/client';
import type { Alert, AlertRule } from '../types';

const TABS = ['全部', '待确认', '已确认', '已关闭'] as const;

const STATUS_CLASS: Record<string, string> = {
  待确认: 'status-待确认',
  已确认: 'status-已确认',
  整改中: 'status-整改中',
  '已关闭（误报）': 'status-已关闭（误报）',
  已关闭: 'status-已关闭',
  提示: 'status-提示',
};

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<(typeof TABS)[number]>('全部');
  const [busy, setBusy] = useState('');
  const [suggesting, setSuggesting] = useState('');
  const [savingNote, setSavingNote] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    Promise.all([listAlerts(), getAlertConfig()])
      .then(([list, config]) => {
        setAlerts(list);
        setRules(config.rules);
        setNotes(Object.fromEntries(list.map((item) => [item.alert_no, item.note || ''])));
        setError('');
      })
      .catch((err) => setError(getErrorMessage(err, '加载预警失败')))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const filtered = useMemo(() => {
    if (tab === '全部') return alerts;
    if (tab === '已关闭') return alerts.filter((a) => a.status.startsWith('已关闭'));
    return alerts.filter((a) => a.status === tab);
  }, [alerts, tab]);

  const pending = alerts.filter((a) => a.status === '待确认').length;
  const orange = alerts.filter((a) => a.level === '橙').length;
  const yellow = alerts.filter((a) => a.level === '黄').length;

  const act = async (alert: Alert, action: 'confirm' | 'dismiss' | 'rectify') => {
    setBusy(alert.alert_no);
    setMessage('');
    try {
      const res = await updateAlert(alert.alert_no, action);
      setAlerts((list) =>
        list.map((a) =>
          a.alert_no === alert.alert_no
            ? { ...a, status: res.status, owner: '质量工程师' }
            : a
        )
      );
      setMessage(`${alert.rule_name} · ${alert.alert_no} 已更新为「${res.status}」`);
    } catch (err) {
      setError(getErrorMessage(err, '操作失败'));
    } finally {
      setBusy('');
    }
  };

  const generateAI = async (alert: Alert) => {
    setSuggesting(alert.alert_no);
    setMessage('');
    try {
      const res = await suggestAlert(alert.alert_no);
      if (res.mode === 'llm') {
        setAlerts((list) =>
          list.map((item) =>
            item.alert_no === alert.alert_no
              ? {
                  ...item,
                  ai_suggestion: res.suggestion,
                  ai_generated_at: '2026-11-10',
                  ai_model: res.model || '',
                }
              : item
          )
        );
        setMessage(`${alert.rule_name} 已生成 AI 建议`);
      } else {
        setMessage(res.error || '当前为规则建议，配置 DeepSeek Key 后可生成 AI 建议');
      }
    } catch (err) {
      setError(getErrorMessage(err, '生成 AI 建议失败'));
    } finally {
      setSuggesting('');
    }
  };

  const saveNote = async (alert: Alert) => {
    setSavingNote(alert.alert_no);
    setMessage('');
    try {
      const res = await saveAlertNote(alert.alert_no, notes[alert.alert_no] ?? '');
      setAlerts((list) =>
        list.map((item) => (item.alert_no === alert.alert_no ? { ...item, note: res.note } : item))
      );
      setNotes((prev) => ({ ...prev, [alert.alert_no]: res.note }));
      setMessage(`${alert.rule_name} 的备注已保存`);
    } catch (err) {
      setError(getErrorMessage(err, '保存备注失败'));
    } finally {
      setSavingNote('');
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">质量归因预警</h1>
          <p className="page-desc">
            按「故障类型 + 原因归属 + 厂家 + 问题部件」筛出一类问题，在时间窗口内达到次数阈值就预警。预警只是线索，确认、整改、关闭都要人来点。
          </p>
        </div>
        <div className="header-actions">
          <span className="status-badge level-橙">橙 {orange}</span>
          <span className="status-badge level-黄">黄 {yellow}</span>
          <span className="status-badge status-待确认">待确认 {pending}</span>
          <button type="button" className="btn btn-secondary" onClick={() => navigate('/alerts/config')}>
            <Settings2 size={14} />
            预警配置
          </button>
        </div>
      </div>

      {message && <div className="success-box">{message}</div>}
      {error && <div className="error-box">{error}</div>}

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={`tab${tab === t ? ' active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
            {t === '待确认' && pending > 0 ? ` ${pending}` : ''}
          </button>
        ))}
      </div>

      <div className="ask-chips" style={{ marginBottom: 14 }}>
        {rules
          .filter((r) => r.enabled)
          .map((r) => (
            <span
              className="chip"
              key={r.id}
              title={[r.fault_type, r.attribution, r.manufacturer, r.component, r.remark]
                .filter(Boolean)
                .join(' / ') || '全部问题'}
            >
              {r.name} · {r.window_days} 天 · ≥{r.threshold} 次
            </span>
          ))}
        <button type="button" className="chip" onClick={() => navigate('/alerts/config')}>
          <Settings2 size={12} /> 修改
        </button>
      </div>

      {loading && <div className="loading">正在计算归因与预警…</div>}

      {!loading && filtered.length === 0 && <div className="empty">该分类下暂时没有预警。</div>}

      {!loading &&
        filtered.map((a) => (
          <div className={`alert-card level-${a.level}`} key={a.alert_no}>
            <div className="alert-head">
              <span className={`status-badge level-${a.level}`}>{a.level}</span>
              <span className="alert-object">{a.rule_name}</span>
              <span className="muted">{a.alert_no}</span>
              <span className={`status-badge ${STATUS_CLASS[a.status] ?? 'status-待确认'}`} style={{ marginLeft: 'auto' }}>
                {a.status}
              </span>
            </div>

            <div className="alert-pattern">{a.condition_text}</div>
            <div className="alert-pattern" style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
              {a.pattern}
            </div>

            <div className="alert-metrics">
              <span className="metric-pill">
                问题数<strong>{a.metric.n}</strong>
              </span>
              <span className="metric-pill">
                阈值<strong>≥{a.threshold}</strong>
              </span>
              <span className="metric-pill">
                窗口<strong>{a.window_days} 天</strong>
              </span>
              <span className="metric-pill">
                涉及整机<strong>{a.metric.machine_count}</strong>
              </span>
              <span className="metric-pill">
                涉及客户<strong>{a.metric.customer_count}</strong>
              </span>
              {a.teams.length > 0 && <span className="metric-pill">班组：{a.teams.join('、')}</span>}
              {a.designers.length > 0 && <span className="metric-pill">设计：{a.designers.join('、')}</span>}
              {a.suppliers.length > 0 && <span className="metric-pill">厂家：{a.suppliers.join('、')}</span>}
            </div>

            <div className="alert-body-grid">
              <div className="alert-note">
                <strong>
                  <Sparkles size={11} /> 可能原因（自动归纳，供参考）
                </strong>
                {a.possible_cause}
              </div>
              <div className="alert-note">
                <strong>
                  <Sparkles size={11} /> AI 建议
                </strong>
                <div style={{ whiteSpace: 'pre-wrap' }}>
                  {a.ai_suggestion || a.suggested_action}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={suggesting === a.alert_no}
                    onClick={() => generateAI(a)}
                  >
                    <Sparkles size={12} />
                    {suggesting === a.alert_no
                      ? '生成中…'
                      : a.ai_suggestion
                        ? '重新生成 AI 建议'
                        : '生成 AI 建议'}
                  </button>
                  <span className="muted" style={{ fontSize: 11 }}>
                    {a.ai_suggestion
                      ? `${a.ai_model || 'DeepSeek'} · ${a.ai_generated_at}`
                      : '未生成时显示规则建议'}
                  </span>
                </div>
              </div>
            </div>

            <div className="alert-note" style={{ marginTop: 10 }}>
              <strong>人工备注</strong>
              <textarea
                className="textarea"
                rows={2}
                value={notes[a.alert_no] ?? ''}
                placeholder="记录处理意见、责任人、计划完成时间…"
                onChange={(e) =>
                  setNotes((prev) => ({ ...prev, [a.alert_no]: e.target.value }))
                }
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 6 }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={savingNote === a.alert_no}
                  onClick={() => saveNote(a)}
                >
                  {savingNote === a.alert_no ? '保存中…' : '保存备注'}
                </button>
              </div>
            </div>

            <div className="alert-evidence">
              <div className="muted" style={{ marginBottom: 4 }}>
                证据问题（{a.evidence_detail.length} 条）
              </div>
              {a.evidence_detail.map((it) => (
                <div
                  className="evidence-item"
                  key={it.id}
                  onClick={() => navigate(`/issues/${it.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/issues/${it.id}`)}
                >
                  <Clock size={12} />
                  <span className="mono">{it.repair_no}</span>
                  <span>
                    {it.machine_id} · {it.component} · {it.phenomenon}
                  </span>
                  <span className="muted" style={{ marginLeft: 'auto' }}>
                    {it.date}
                  </span>
                </div>
              ))}
            </div>

            {a.status === '已关闭（误报）' && a.reason && (
              <div className="gap-banner" style={{ marginTop: 10 }}>
                <Info size={14} />
                <div>误报原因：{a.reason}（{a.owner}）</div>
              </div>
            )}

            <div className="alert-actions">
              {a.status === '待确认' && (
                <>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busy === a.alert_no}
                    onClick={() => act(a, 'confirm')}
                  >
                    <CheckCircle2 size={13} /> 确认预警
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busy === a.alert_no}
                    onClick={() => act(a, 'rectify')}
                  >
                    <Wrench size={13} /> 转整改
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger-soft btn-sm"
                    disabled={busy === a.alert_no}
                    onClick={() => act(a, 'dismiss')}
                  >
                    <XCircle size={13} /> 误报
                  </button>
                </>
              )}

              {a.status === '已确认' && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={busy === a.alert_no}
                  onClick={() => act(a, 'rectify')}
                >
                  <Wrench size={13} /> 转整改
                </button>
              )}

              {a.status === '整改中' && (
                <span className="muted">
                  <ShieldAlert size={12} /> 整改任务跟踪中，验证有效后由质量工程师关闭。
                </span>
              )}

              {a.status.startsWith('已关闭') && <span className="muted">已归档，保留证据链供追溯。</span>}
            </div>
          </div>
        ))}
    </div>
  );
}
