import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  Info,
  TriangleAlert,
} from 'lucide-react';
import { checkKb, getAgreements, getErrorMessage } from '../api/client';
import type { AgreementCheckResult, AgreementDoc } from '../types';

const ITEMS = [
  { code: 'paint_internal_dft', label: '箱梁内部漆膜总厚度', unit: 'μm', hint: '协议 §5：漆膜干燥总厚度≥150μm' },
  { code: 'steel_main_thickness', label: '主要承载构件板厚', unit: 'mm', hint: '协议 §2.2.1：对钢板或扁钢 ≥ 8mm' },
  { code: 'rope_safety', label: '钢丝绳安全系数', unit: '', hint: '协议 §3.8.1：安全系数不少于9' },
];

export default function KbCheckPage() {
  const [params] = useSearchParams();
  const [agreements, setAgreements] = useState<AgreementDoc[]>([]);
  const [docId, setDocId] = useState(params.get('doc') ?? '');
  const [itemCode, setItemCode] = useState('paint_internal_dft');
  const [measured, setMeasured] = useState('140');
  const [result, setResult] = useState<AgreementCheckResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const doc = agreements.find((item) => item.id === docId) ?? null;
  const supported = doc?.doc_no === '2001001111';
  const item = ITEMS.find((i) => i.code === itemCode) ?? ITEMS[0];

  useEffect(() => {
    getAgreements()
      .then((list) => {
        setAgreements(list);
        const id = params.get('doc');
        const preferred =
          (id && list.some((entry) => entry.id === id) ? id : '') ||
          list.find((entry) => entry.doc_no === '2001001111')?.id ||
          list[0]?.id ||
          '';
        setDocId(preferred);
      })
      .catch((err) => setError(getErrorMessage(err, '加载技术协议失败')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (code: string, raw: string) => {
    if (!supported || !docId) {
      setError('该协议暂未配置自动核对项，请返回协议问答查看原文。');
      setResult(null);
      return;
    }
    const value = Number(raw);
    if (Number.isNaN(value)) {
      setError('请输入数字实测值');
      return;
    }
    setLoading(true);
    setError('');
    setSaved(false);
    try {
      const res = await checkKb(docId, code, value);
      setResult(res);
    } catch (err) {
      setError(getErrorMessage(err, '核对失败'));
    } finally {
      setLoading(false);
    }
  };

  const submit = () => {
    void run(itemCode, measured);
  };

  useEffect(() => {
    if (supported) void run('paint_internal_dft', '140');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported, docId]);

  return (
    <div className="page">
      <Link className="back-link" to={doc ? `/kb?doc=${doc.id}` : '/kb'}>
        <ArrowLeft size={14} /> 返回技术协议库
      </Link>

      <div className="page-header">
        <div>
          <h1 className="page-title">不符合项核对</h1>
          <p className="page-desc">
            检验发现不符合时，直接对照技术协议条款：要求值、页码、原文一次摆出来，避免跨系统翻找。
          </p>
        </div>
        <div className="header-actions">
          <span className="demo-tag">{doc ? doc.title : '技术协议'}</span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <label className="label">技术协议</label>
        <select
          className="select"
          value={docId}
          onChange={(e) => {
            setDocId(e.target.value);
            setResult(null);
            setError('');
            setSaved(false);
          }}
        >
          {agreements.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {entry.title}（{entry.doc_no} · {entry.pages} 页）
            </option>
          ))}
        </select>
        {doc && !supported && (
          <div className="gap-banner" style={{ marginTop: 10 }}>
            <TriangleAlert size={14} />
            <div>该协议暂未配置自动核对项，请返回协议问答查看原文；核对项目前只覆盖 2001001111。</div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="check-form">
          <div>
            <label className="label">检查项</label>
            <select className="select" value={itemCode} onChange={(e) => setItemCode(e.target.value)}>
              {ITEMS.map((i) => (
                <option key={i.code} value={i.code}>
                  {i.label}（{i.unit}）
                </option>
              ))}
            </select>
            <div className="muted" style={{ marginTop: 4, fontSize: 11 }}>
              {item.hint}
            </div>
          </div>
          <div>
            <label className="label">实测值（{item.unit}）</label>
            <input
              className="input"
              value={measured}
              onChange={(e) => setMeasured(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
              placeholder={`输入${item.unit}`}
            />
          </div>
          <div>
            <label className="label">核对依据</label>
            <div className="muted" style={{ paddingTop: 10, fontSize: 11 }}>
              {doc ? `${doc.title} · ${doc.version}` : '技术协议'}
            </div>
          </div>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={loading || !supported}>
            <ClipboardCheck size={15} />
            {loading ? '核对中…' : '开始核对'}
          </button>
        </div>
      </div>

      {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}

      {result && (
        <>
          <div className={`verdict-banner ${result.severity}`}>
            {result.severity === 'ok' ? <CheckCircle2 size={20} /> : <TriangleAlert size={20} />}
            <div>
              {result.verdict}
              <div>
                <span>{result.reason}</span>
              </div>
            </div>
          </div>

          <div className="check-grid">
            <div className="check-col">
              <div className="check-col-head">
                <span>协议要求</span>
                <span className={`check-mark ${result.severity === 'ok' ? 'ok' : 'bad'}`}>
                  {result.requirement.display}
                </span>
              </div>
              <div className="check-val">{result.requirement.display}</div>
              <div className="check-source">
                {result.document.title} {result.document.version}
                <br />
                {result.requirement.source.clause_no} · 第 {result.requirement.source.page} 页
              </div>
            </div>

            <div className="check-col">
              <div className="check-col-head">
                <span>实测值</span>
                <span className={`check-mark ${result.severity === 'ok' ? 'ok' : 'bad'}`}>
                  {result.measured}
                  {result.item.unit ? ` ${result.item.unit}` : ''}
                </span>
              </div>
              <div className="check-val">
                {result.measured}
                {result.item.unit ? ` ${result.item.unit}` : ''}
              </div>
              <div className="check-source">
                {result.item.label}
                <br />
                检验记录 / 实测照片
              </div>
            </div>

            <div className="check-col">
              <div className="check-col-head">
                <span>判定</span>
                <span className={`check-mark ${result.severity === 'ok' ? 'ok' : 'bad'}`}>
                  {result.verdict}
                </span>
              </div>
              <div className="check-val" style={{ fontSize: 20 }}>
                {result.verdict}
              </div>
              <div className="check-source">
                按技术协议条款判定
                <br />
                规则计算，不依赖模型
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <div className="card-header">
              <div>
                <div className="section-title">判定依据与建议</div>
                <div className="section-sub">协议原文与条款页码</div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setSaved(true)}
              >
                <ClipboardCheck size={13} /> 生成核对记录
              </button>
            </div>
            {saved && <div className="success-box">核对记录已生成（演示：未写入后端），可随检验记录归档。</div>}

            <div className="alert-note">
              <strong>协议原文</strong>
              {result.requirement.source.text}
            </div>

            <div style={{ marginTop: 14 }}>
              <div className="section-title" style={{ fontSize: 13, marginBottom: 6 }}>
                <Info size={13} /> 建议动作
              </div>
              <ul style={{ paddingLeft: 18, fontSize: 13, color: 'var(--color-text-secondary)' }}>
                {result.suggestions.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </div>

            <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Link
                className="btn btn-secondary btn-sm"
                to={`/kb?q=${encodeURIComponent(`${result.item.label}在协议里怎么要求？`)}`}
              >
                <FileText size={13} /> 去看完整协议问答
              </Link>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
