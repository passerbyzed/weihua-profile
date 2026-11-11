import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  Check,
  Copy,
  FileText,
  Info,
  Layers,
  Search,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
  X,
} from 'lucide-react';
import { askKb, getAgreements, getErrorMessage, reviewAnswer } from '../api/client';
import type { AgreementDoc, Answer, AnswerItem, Citation } from '../types';

const DOC_SAMPLES: Record<string, string[]> = {
  '2001001111': [
    '2001001111技术协议对油漆、吊钩、钢板有什么要求？',
    '油漆的涂层体系和干膜厚度是多少？',
    '吊钩的配置和材料要求是什么？',
    '钢板材质和最小板厚是多少？',
    '质保期多长？',
    '钢丝绳安全系数要求是多少？',
  ],
};

const DEFAULT_SAMPLES = [
  '这份协议对油漆、吊钩、钢板有什么要求？',
  '质保期是怎么规定的？',
  '钢丝绳安全系数要求是多少？',
  '主要受力结构件用什么材质？',
];

const VERDICT_LABEL: Record<string, string> = {
  standard: '标准配置',
  non_standard: '非标',
  non_compliant: '不满足',
  vague: '模糊',
  not_mentioned: '未提及',
  conflict: '冲突',
  specified: '协议原文',
};

const CONFIDENCE_LABEL: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

function Highlight({ text }: { text: string }) {
  const parts = text.split(/(\d+(?:\.\d+)?\s*(?:μm|um|mm|kV|Hz|m\/s|t|m|个月|年|级|%)?)/g);
  return (
    <>
      {parts.map((part, idx) =>
        /^\d/.test(part) ? <mark key={idx}>{part}</mark> : <span key={idx}>{part}</span>
      )}
    </>
  );
}

export default function KbPage() {
  const [params, setParams] = useSearchParams();
  const [agreements, setAgreements] = useState<AgreementDoc[]>([]);
  const [docId, setDocId] = useState(params.get('doc') ?? '');
  const [search, setSearch] = useState('');
  const [question, setQuestion] = useState(params.get('q') ?? '');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeCite, setActiveCite] = useState<Citation | null>(null);
  const [reviewMsg, setReviewMsg] = useState('');
  const [copied, setCopied] = useState(false);

  const doc = agreements.find((item) => item.id === docId) ?? null;
  const samples = (doc && DOC_SAMPLES[doc.doc_no]) || DEFAULT_SAMPLES;
  const filtered = agreements.filter((item) => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return true;
    return (
      item.title.toLowerCase().includes(keyword) ||
      item.doc_no.toLowerCase().includes(keyword)
    );
  });

  useEffect(() => {
    getAgreements()
      .then((list) => {
        setAgreements(list);
        const q = params.get('q');
        const id = params.get('doc');
        if (id && list.some((item) => item.id === id)) {
          setDocId(id);
          if (q) void runAsk(id, q);
        }
      })
      .catch((err) => setError(getErrorMessage(err, '加载技术协议列表失败')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const citeMap = useMemo(() => {
    const map = new Map<string, Citation>();
    answer?.citations.forEach((c) => map.set(c.cid, c));
    return map;
  }, [answer]);

  const selectDoc = (id: string) => {
    setDocId(id);
    setQuestion('');
    setAnswer(null);
    setError('');
    setReviewMsg('');
    setParams({ doc: id }, { replace: true });
  };

  const clearDoc = () => {
    setDocId('');
    setQuestion('');
    setAnswer(null);
    setError('');
    setReviewMsg('');
    setParams({}, { replace: true });
  };

  const runAsk = async (targetId: string, text: string) => {
    const q = text.trim();
    if (!q) return;
    if (!targetId) {
      setError('请先搜索并选择一份技术协议');
      return;
    }
    setLoading(true);
    setError('');
    setReviewMsg('');
    setAnswer(null);
    try {
      const res = await askKb(targetId, q);
      setAnswer(res);
      setParams({ doc: targetId, q }, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, '问答失败，请稍后重试'));
    } finally {
      setLoading(false);
    }
  };

  const doReview = async (action: 'confirm' | 'dispute') => {
    if (!answer || !doc) return;
    try {
      const res = await reviewAnswer(doc.id, answer.question, action);
      setAnswer({ ...answer, review_status: res.status });
      setReviewMsg(action === 'confirm' ? '已记录核对结果：确认无误。' : '已记录异议，进入知识修订队列。');
    } catch (err) {
      setError(getErrorMessage(err, '提交核对结果失败'));
    }
  };

  const copyChecklist = async () => {
    if (!answer || !doc) return;
    const lines = [
      `技术协议核对单 · ${doc.title}（${doc.version}）`,
      `核对问题：${answer.question}`,
      '',
      ...answer.items.map(
        (i) =>
          `${i.object}：${VERDICT_LABEL[i.verdict] ?? i.verdict}\n  协议要求：${i.requirement}\n  引用：${i.citations.join('、')}`
      ),
      '',
      ...answer.gaps.map((g) => `缺口：${g}`),
      '',
      `引用：${answer.citations.map((c) => `${c.cid} ${c.clause_no} 第${c.page}页`).join('；')}`,
      '',
      '（由质量智脑生成，请核对引用原文）',
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
    }
  };

  const openCite = (cid: string) => {
    const cite = citeMap.get(cid);
    if (cite) setActiveCite(cite);
  };

  const isAgreement = answer?.answer_type === 'agreement_query';

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">技术协议库</h1>
          <p className="page-desc">
            用自然语言问技术协议。每条要求都逐字摘自协议原文，并标到「条款 + 页码」，点开即可核对；不做任何推导。
          </p>
        </div>
        <div className="header-actions">
          <button type="button" className="btn btn-secondary" onClick={copyChecklist} disabled={!answer}>
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? '已复制' : '生成核对单'}
          </button>
          <a className="btn btn-secondary" href={doc ? `/kb/check?doc=${doc.id}` : '/kb/check'}>
            <Search size={15} />
            不符合项核对
          </a>
        </div>
      </div>

      <div className="kb-hero">
        {!doc ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <h2>搜索技术协议</h2>
                <p>共 {agreements.length} 份 PDF 协议。输入编号或名称，选中一份后再提问；问答只返回该协议的原文。</p>
              </div>
              <span className="status-badge status-已关闭">PDF 原文库</span>
            </div>

            <div className="kb-question">
              <input
                className="input"
                value={search}
                placeholder="搜索协议编号或名称，如 200111777888"
                onChange={(e) => setSearch(e.target.value)}
              />
              <span className="agreement-count">{filtered.length} 份</span>
            </div>

            <div className="agreement-list">
              {filtered.map((item) => (
                <button
                  type="button"
                  className="agreement-item"
                  key={item.id}
                  onClick={() => selectDoc(item.id)}
                >
                  <div>
                    <div className="agreement-item-title">
                      <FileText size={14} /> {item.title}
                    </div>
                    <div className="agreement-item-meta">
                      {item.doc_no} · {item.pages} 页 · {item.clause_count} 条原文
                    </div>
                  </div>
                  <ArrowRight size={15} />
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="agreement-empty">没有匹配的协议，换个编号或名称试试。</div>
              )}
            </div>
          </>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <h2>{doc.title}</h2>
                <p>
                  {doc.version} · {doc.pages} 页 · {doc.clause_count} 条可检索原文
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <span className="status-badge status-已关闭">协议原文检索</span>
                <button type="button" className="btn btn-secondary btn-sm" onClick={clearDoc}>
                  <Search size={13} /> 换一份协议
                </button>
              </div>
            </div>

            <div className="kb-question">
              <input
                className="input"
                value={question}
                placeholder={`在《${doc.title}》中提问，例如：对油漆、吊钩、钢板有什么要求？`}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runAsk(doc.id, question)}
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => runAsk(doc.id, question)}
                disabled={loading}
              >
                <Sparkles size={15} />
                {loading ? '检索中…' : '提问'}
              </button>
            </div>

            <div className="kb-samples">
              {samples.map((s) => (
                <button
                  type="button"
                  className="chip"
                  key={s}
                  onClick={() => {
                    setQuestion(s);
                    void runAsk(doc.id, s);
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}

      {loading && (
        <div className="card">
          <div className="loading">正在检索协议原文 → 定位页码 → 拼接原文…</div>
        </div>
      )}

      {!loading && !answer && (
        <div className="card">
          <div className="empty">
            <BookOpen size={26} style={{ marginBottom: 8, opacity: 0.6 }} />
            <div>
              {doc
                ? '输入问题，或点上面的示例。回答只会逐字返回该协议的原文，并附页码。'
                : '先在上方搜索并选择一份技术协议，再开始提问。'}
            </div>
          </div>
        </div>
      )}

      {answer && (
        <div className="answer">
          <div className="card">
            <div className="answer-meta">
              <span className="ai-tag">
                <Sparkles size={11} />{' '}
                {answer.mode === 'retrieval+verbatim'
                  ? '协议原文检索（未使用模型生成）'
                  : '检索 + 规则引擎'}
              </span>
              <span className={`confidence confidence-${answer.confidence}`}>
                置信度 {CONFIDENCE_LABEL[answer.confidence] ?? answer.confidence}
              </span>
              {answer.document && (
                <span className="status-badge" style={{ background: '#f1f5f9', color: '#475569' }}>
                  {answer.document.title}
                </span>
              )}
              <span className="muted">
                引用 {answer.citations.length} 条
                {answer.llm?.elapsed_ms ? ` · ${(answer.llm.elapsed_ms / 1000).toFixed(1)}s` : ''}
              </span>
              <span className="review-status">核对状态：{answer.review_status}</span>
            </div>

            {answer.llm?.error && (
              <div className="gap-banner" style={{ marginBottom: 12 }}>
                <TriangleAlert size={14} />
                <div>{answer.llm.error}（已回退规则结论，可核对下方引用原文）</div>
              </div>
            )}

            <div className="answer-conclusion">{answer.conclusion}</div>

            {isAgreement && (
              <div className="gap-banner" style={{ marginTop: 12 }}>
                <Info size={14} />
                <div>以下内容逐字摘自协议原文，未做归纳、推算或补全；请以引用页码和原文为准。</div>
              </div>
            )}

            {answer.items.length > 0 && (
              <div className="answer-section">
                <div className="answer-section-title">
                  <Layers size={14} /> 逐项核对
                </div>
                <div className="table-wrap">
                  <table className="data-table answer-table">
                    <thead>
                      <tr>
                        <th style={{ width: 100 }}>项目</th>
                        <th style={{ width: 86 }}>结论</th>
                        <th>{isAgreement ? '协议原文（逐字引用）' : '协议要求'}</th>
                        {!isAgreement && <th>标准配置</th>}
                        {!isAgreement && <th>差异</th>}
                        <th style={{ width: 96 }}>引用</th>
                      </tr>
                    </thead>
                    <tbody>
                      {answer.items.map((item: AnswerItem) => (
                        <tr key={item.object}>
                          <td className="cell-main">{item.object}</td>
                          <td>
                            <span className={`verdict verdict-${item.verdict}`}>
                              {VERDICT_LABEL[item.verdict] ?? item.verdict}
                            </span>
                          </td>
                          <td style={isAgreement ? { whiteSpace: 'pre-wrap', lineHeight: 1.8 } : undefined}>
                            {item.requirement}
                            {item.notes.length > 0 && (
                              <div className="cell-sub">{item.notes.join('；')}</div>
                            )}
                          </td>
                          {!isAgreement && <td>{item.standard_value}</td>}
                          {!isAgreement && <td>{item.difference}</td>}
                          <td>
                            {item.citations.map((cid) => (
                              <button
                                type="button"
                                className="cite-ref"
                                key={cid}
                                onClick={() => openCite(cid)}
                                title={citeMap.get(cid)?.doc_title}
                              >
                                {cid}
                              </button>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {answer.conflicts.length > 0 && (
              <div className="answer-section">
                <div className="answer-section-title">
                  <TriangleAlert size={14} color="#b91c1c" /> 协议冲突（需确认）
                </div>
                {answer.conflicts.map((c) => (
                  <div className="conflict-card" key={c.object + c.description}>
                    <div className="conflict-title">
                      <TriangleAlert size={13} /> {c.object}
                      {c.citations.map((cid) => (
                        <button type="button" className="cite-ref" key={cid} onClick={() => openCite(cid)}>
                          {cid}
                        </button>
                      ))}
                    </div>
                    <div className="conflict-desc">{c.description}</div>
                    <div className="conflict-suggest">建议：{c.suggested}</div>
                  </div>
                ))}
              </div>
            )}

            {answer.gaps.length > 0 && (
              <div className="answer-section">
                <div className="answer-section-title">
                  <Info size={14} color="#92400e" /> 缺口与提示
                </div>
                <div className="gap-list">
                  {answer.gaps.map((g) => (
                    <div className="gap-item" key={g}>
                      {g}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {answer.citations.length > 0 && (
              <div className="answer-section">
                <div className="answer-section-title">
                  <FileText size={14} /> 引用清单（点击查看原文）
                </div>
                <div className="citation-list">
                  {answer.citations.map((c) => (
                    <div className="citation-card" key={c.cid} onClick={() => setActiveCite(c)}>
                      <div className="citation-head">
                        <span className="cite-id">{c.cid}</span>
                        <span className="citation-title">{c.doc_title}</span>
                        <span className="muted">第 {c.page} 页</span>
                      </div>
                      <div className="citation-meta">
                        {c.version} · {c.clause_no} · 生效 {c.effective_date} · {c.doc_type}
                      </div>
                      <div className="citation-snippet">{c.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="review-bar">
              <span className="muted">核对后记录，供追溯：</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => doReview('confirm')}>
                <ThumbsUp size={13} /> 确认无误
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => doReview('dispute')}>
                <ThumbsDown size={13} /> 有异议
              </button>
              <span className="muted">结论由 AI 基于协议条款生成，请核对引用原文后再使用。</span>
            </div>
            {reviewMsg && <div className="success-box" style={{ marginTop: 12, marginBottom: 0 }}>{reviewMsg}</div>}
          </div>
        </div>
      )}

      {activeCite && (
        <div className="modal-overlay" onClick={() => setActiveCite(null)} role="presentation">
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="modal-head">
              <div>
                <div className="modal-title">
                  {activeCite.cid} · {activeCite.doc_title}
                </div>
                <div className="modal-sub">
                  {activeCite.doc_type} · {activeCite.version} · {activeCite.clause_no} · 第{' '}
                  {activeCite.page} 页
                </div>
              </div>
              <button type="button" className="modal-close" onClick={() => setActiveCite(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="clause-text">
                <Highlight text={activeCite.text} />
              </div>
              <div className="meta-grid">
                <div className="meta-item">
                  文件编号<strong>{activeCite.doc_no}</strong>
                </div>
                <div className="meta-item">
                  版本<strong>{activeCite.version}</strong>
                </div>
                <div className="meta-item">
                  生效日期<strong>{activeCite.effective_date}</strong>
                </div>
                <div className="meta-item">
                  章节<strong>{activeCite.section}</strong>
                </div>
                <div className="meta-item">
                  条款号<strong>{activeCite.clause_no}</strong>
                </div>
                <div className="meta-item">
                  页码<strong>第 {activeCite.page} 页</strong>
                </div>
              </div>
              <div className="gap-item" style={{ marginTop: 14 }}>
                演示协议按条款切分，页码对应 PDF 第 {activeCite.page} 页；接入真实系统后直接定位 PDF 原文坐标。
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
