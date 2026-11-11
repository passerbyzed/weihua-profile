import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Bell, Plus, RotateCcw, Save, Trash2, TriangleAlert } from 'lucide-react';
import {
  getAlertConfig,
  getDictionaries,
  getErrorMessage,
  listAlerts,
  saveAlertConfig,
} from '../api/client';
import type { Alert, AlertConfig, AlertRule, Dictionaries } from '../types';

const DEFAULT_RULES: AlertRule[] = [
  { id: 'paint_make', name: '涂装制作问题聚集', fault_type: '其他类', attribution: '制作问题', manufacturer: '', component: '涂装层', remark: '', window_days: 120, threshold: 3, level: '橙', enabled: true },
  { id: 'bearing_make', name: '卷筒轴承座装配问题', fault_type: '机械类', attribution: '制作问题', manufacturer: '', component: '卷筒轴承座', remark: '', window_days: 365, threshold: 3, level: '黄', enabled: true },
  { id: 'motor_outsource', name: '电机外协问题', fault_type: '电气类', attribution: '外协问题', manufacturer: '河南XX电机', component: '起升电机', remark: '', window_days: 365, threshold: 2, level: '橙', enabled: true },
  { id: 'wheel_design', name: '车轮设计问题重复', fault_type: '机械类', attribution: '设计问题', manufacturer: '', component: '车轮', remark: '', window_days: 540, threshold: 2, level: '黄', enabled: true },
  { id: 'paint_delivery', name: '涂装发货磕碰', fault_type: '其他类', attribution: '发货问题', manufacturer: '', component: '涂装层', remark: '', window_days: 180, threshold: 2, level: '提示', enabled: true },
];

const EMPTY_RULE: Omit<AlertRule, 'id'> = {
  name: '新预警规则',
  fault_type: '',
  attribution: '',
  manufacturer: '',
  component: '',
  remark: '',
  window_days: 90,
  threshold: 3,
  level: '黄',
  enabled: true,
};

export default function AlertConfigPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [dict, setDict] = useState<Dictionaries | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    Promise.all([getAlertConfig(), listAlerts(), getDictionaries()])
      .then(([config, list, dictionaries]) => {
        setRules(config.rules);
        setAlerts(list);
        setDict(dictionaries);
      })
      .catch((err) => setError(getErrorMessage(err, '加载预警配置失败')))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const update = (index: number, patch: Partial<AlertRule>) => {
    setRules((list) => list.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
    setMessage('');
  };

  const addRule = () => {
    setRules((list) => [...list, { ...EMPTY_RULE, id: `rule_${Date.now()}` }]);
    setMessage('');
  };

  const removeRule = (index: number) => {
    setRules((list) => list.filter((_, i) => i !== index));
    setMessage('');
  };

  const save = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const saved = await saveAlertConfig({ rules } as AlertConfig);
      setRules(saved.rules);
      const list = await listAlerts();
      setAlerts(list);
      setMessage(`已保存 ${saved.rules.length} 条规则，当前命中 ${list.length} 条预警。`);
    } catch (err) {
      setError(getErrorMessage(err, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  if (loading || !dict) return <div className="loading">正在加载预警配置…</div>;

  return (
    <div className="page">
      <Link className="back-link" to="/alerts">
        <ArrowLeft size={14} /> 返回预警中心
      </Link>

      <div className="page-header">
        <div>
          <h1 className="page-title">预警配置</h1>
          <p className="page-desc">
            按「故障类型 + 原因归属 + 厂家 + 问题部件 + 备注关键词」筛选一类问题，在时间窗口内达到次数阈值就告警。
          </p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setRules(DEFAULT_RULES.map((r) => ({ ...r })));
              setMessage('已恢复默认规则，点「保存并重算」生效。');
            }}
          >
            <RotateCcw size={14} />
            恢复默认
          </button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
            <Save size={14} />
            {saving ? '保存中…' : '保存并重算'}
          </button>
        </div>
      </div>

      {message && <div className="success-box">{message}</div>}
      {error && <div className="error-box">{error}</div>}

      <div className="gap-banner" style={{ marginBottom: 14 }}>
        <TriangleAlert size={15} />
        <div>
          命中条件：窗口内同时满足所选条件（AND）的问题数 ≥ 次数阈值。留空表示不限；问题部件按包含匹配；备注按空格/顿号拆词，命中现象、描述、根因或处置任一即算。
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-wrap">
          <table className="data-table config-table">
            <thead>
              <tr>
                <th style={{ minWidth: 130 }}>规则名称</th>
                <th style={{ minWidth: 90 }}>故障类型</th>
                <th style={{ minWidth: 120 }}>故障原因归属</th>
                <th style={{ minWidth: 100 }}>厂家</th>
                <th style={{ minWidth: 100 }}>问题部件</th>
                <th style={{ minWidth: 110 }}>备注</th>
                <th style={{ width: 80 }}>时间窗口（天）</th>
                <th style={{ width: 72 }}>次数阈值</th>
                <th style={{ width: 60 }}>等级</th>
                <th style={{ width: 44 }}>启用</th>
                <th style={{ width: 32 }} />
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, index) => (
                <tr key={rule.id}>
                  <td>
                    <input
                      className="input"
                      value={rule.name}
                      onChange={(e) => update(index, { name: e.target.value })}
                    />
                  </td>
                  <td>
                    <select
                      className="select"
                      value={rule.fault_type}
                      onChange={(e) => update(index, { fault_type: e.target.value })}
                    >
                      <option value="">不限</option>
                      {dict.fault_types.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="select"
                      value={rule.attribution}
                      onChange={(e) => update(index, { attribution: e.target.value })}
                    >
                      <option value="">不限</option>
                      {dict.attributions.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className="select"
                      value={rule.manufacturer}
                      onChange={(e) => update(index, { manufacturer: e.target.value })}
                    >
                      <option value="">不限</option>
                      {dict.suppliers.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="input"
                      list="component-options"
                      value={rule.component}
                      placeholder="如 涂装层"
                      onChange={(e) => update(index, { component: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      value={rule.remark}
                      placeholder="关键词，空格分隔"
                      onChange={(e) => update(index, { remark: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={730}
                      value={rule.window_days}
                      onChange={(e) => update(index, { window_days: Number(e.target.value) })}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={50}
                      value={rule.threshold}
                      onChange={(e) => update(index, { threshold: Number(e.target.value) })}
                    />
                  </td>
                  <td>
                    <select
                      className="select"
                      value={rule.level}
                      onChange={(e) => update(index, { level: e.target.value })}
                    >
                      {dict.alert_levels.map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      onChange={(e) => update(index, { enabled: e.target.checked })}
                      style={{ width: 16, height: 16, cursor: 'pointer' }}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => removeRule(index)}
                      title="删除规则"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <datalist id="component-options">
            {dict.components.map((component) => (
              <option key={component} value={component} />
            ))}
          </datalist>
        </div>

        <div style={{ padding: 14, borderTop: '1px solid var(--color-border)' }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={addRule}>
            <Plus size={14} /> 新增规则
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="section-title">
              <Bell size={15} /> 当前配置命中（{alerts.length} 条）
            </div>
            <div className="section-sub">保存后按新规则实时重算</div>
          </div>
          <Link className="btn btn-ghost btn-sm" to="/alerts">
            去预警中心
          </Link>
        </div>

        {alerts.length === 0 ? (
          <div className="empty">当前阈值下没有命中预警，可以调低次数阈值或放宽时间窗口再试。</div>
        ) : (
          <div className="recent-list">
            {alerts.map((a) => (
              <div className="recent-item" key={a.alert_key}>
                <span className={`status-badge level-${a.level}`}>{a.level}</span>
                <div className="recent-main">
                  <div className="recent-title">{a.rule_name}</div>
                  <div className="recent-meta">
                    {a.condition_text} · {a.window_days} 天内 {a.metric.n} 起（阈值 ≥{a.threshold}） · 涉及{' '}
                    {a.metric.machine_count} 台整机 / {a.metric.customer_count} 个客户
                  </div>
                </div>
                <span className={`status-badge ${a.status === '提示' ? 'status-提示' : 'status-待确认'}`}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
