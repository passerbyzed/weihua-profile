import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RotateCcw, Search, Sparkles } from 'lucide-react';
import { getErrorMessage, listIssues } from '../api/client';
import type { Issue } from '../types';

const FAULT_TYPES = ['其他类', '机械类', '电气类'];
const AFTER_SALES_STATUSES = ['待派工', '已派工-待完工', '已完工-待评价', '已完工-已评价', '已取消'];
const RESPONSIBILITY_STATUSES = ['未开始', '待定', '有责', '无责'];
const CHANNELS = ['云上卫4', 'oa', '电话', '微信'];
const DEPARTMENTS = ['售后部', '质量部', '客服部', '销售部'];

const AS_CLASS: Record<string, string> = {
  待派工: 'as-pending',
  '已派工-待完工': 'as-doing',
  '已完工-待评价': 'as-review',
  '已完工-已评价': 'as-done',
  已取消: 'as-cancel',
};

const RESP_CLASS: Record<string, string> = {
  未开始: 'resp-idle',
  待定: 'resp-wait',
  有责: 'resp-bad',
  无责: 'resp-ok',
};

interface Filters {
  search: string;
  faultType: string;
  afterSales: string;
  responsibility: string;
  channel: string;
  department: string;
}

const EMPTY_FILTERS: Filters = {
  search: '',
  faultType: '',
  afterSales: '',
  responsibility: '',
  channel: '',
  department: '',
};

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selected, setSelected] = useState<number[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    listIssues()
      .then((list) => {
        setIssues(list);
        setError('');
      })
      .catch((err) => setError(getErrorMessage(err, '加载报修单失败')))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const keyword = applied.search.trim().toLowerCase();
    return issues.filter((it) => {
      if (applied.faultType && it.fault_type !== applied.faultType) return false;
      if (applied.afterSales && it.after_sales_status !== applied.afterSales) return false;
      if (applied.responsibility && it.responsibility_status !== applied.responsibility) return false;
      if (applied.channel && it.source_channel !== applied.channel) return false;
      if (applied.department && it.department !== applied.department) return false;
      if (keyword) {
        const haystack = [
          it.repair_no,
          it.issue_no,
          it.customer,
          it.machine_id,
          it.component,
          it.phenomenon,
          it.contact_name,
          it.contact_phone,
          it.attribution_raw,
        ]
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(keyword)) return false;
      }
      return true;
    });
  }, [issues, applied]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const allSelected = pageItems.length > 0 && pageItems.every((it) => selected.includes(it.id));

  useEffect(() => {
    setPage(1);
  }, [applied, pageSize]);

  const query = () => {
    setApplied({ ...draft });
    setSelected([]);
  };

  const clear = () => {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setSelected([]);
  };

  const toggleAll = () => {
    if (allSelected) {
      const ids = new Set(pageItems.map((it) => it.id));
      setSelected((list) => list.filter((id) => !ids.has(id)));
    } else {
      setSelected((list) => Array.from(new Set([...list, ...pageItems.map((it) => it.id)])));
    }
  };

  const toggleOne = (id: number) => {
    setSelected((list) => (list.includes(id) ? list.filter((item) => item !== id) : [...list, id]));
  };

  const pageNumbers = useMemo(() => {
    const pages: number[] = [];
    const start = Math.max(1, Math.min(currentPage - 2, totalPages - 4));
    const end = Math.min(totalPages, start + 4);
    for (let p = start; p <= end; p += 1) pages.push(p);
    return pages;
  }, [currentPage, totalPages]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">售后问题质量库</h1>
          <p className="page-desc">
            报修单与质量问题统一归集，支持按售后状态、定责状态、来源、故障类型筛选；点任意一行进入 AI 研判与质量链。
          </p>
        </div>
        <div className="header-actions">
          <span className="demo-tag">共 {issues.length} 条</span>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/issues/ask')}>
            <Sparkles size={15} />
            AI 问问题库
          </button>
        </div>
      </div>

      <div className="filters issue-filters">
        <select
          className="filter-select"
          value={draft.faultType}
          onChange={(e) => setDraft({ ...draft, faultType: e.target.value })}
        >
          <option value="">全部类型</option>
          {FAULT_TYPES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <div className="search-box">
          <Search size={16} />
          <input
            value={draft.search}
            onChange={(e) => setDraft({ ...draft, search: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && query()}
            placeholder="报修单号、使用单位、联系人、部件、现象…"
          />
        </div>

        <select
          className="filter-select"
          value={draft.afterSales}
          onChange={(e) => setDraft({ ...draft, afterSales: e.target.value })}
        >
          <option value="">售后状态</option>
          {AFTER_SALES_STATUSES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          className="filter-select"
          value={draft.responsibility}
          onChange={(e) => setDraft({ ...draft, responsibility: e.target.value })}
        >
          <option value="">定责状态</option>
          {RESPONSIBILITY_STATUSES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          className="filter-select"
          value={draft.channel}
          onChange={(e) => setDraft({ ...draft, channel: e.target.value })}
        >
          <option value="">来源</option>
          {CHANNELS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          className="filter-select"
          value={draft.department}
          onChange={(e) => setDraft({ ...draft, department: e.target.value })}
        >
          <option value="">发起部门</option>
          {DEPARTMENTS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <button type="button" className="btn btn-primary" onClick={query}>
          查询
        </button>
        <button type="button" className="btn btn-secondary" onClick={clear}>
          <RotateCcw size={14} />
          清空
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card issue-table-card">
        {loading ? (
          <div className="loading">正在加载报修单…</div>
        ) : filtered.length === 0 ? (
          <div className="empty">没有符合条件的报修单，试试清空筛选。</div>
        ) : (
          <>
            <div className="table-hint">表格列较多，可左右滚动查看更多；点击任意一行进入 AI 研判。</div>
            <div className="table-wrap issue-table-wrap">
              <table className="data-table issue-table">
                <thead>
                  <tr>
                    <th style={{ width: 34 }}>
                      <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                    </th>
                    <th style={{ width: 46 }}>序号</th>
                    <th style={{ width: 126 }}>报修单号</th>
                    <th style={{ minWidth: 170 }}>使用单位</th>
                    <th style={{ width: 116 }}>售后状态</th>
                    <th style={{ width: 76 }}>定责状态</th>
                    <th style={{ width: 70 }}>故障类型</th>
                    <th style={{ width: 96 }}>原因归属</th>
                    <th style={{ minWidth: 128 }}>问题部件</th>
                    <th style={{ width: 70 }}>来源</th>
                    <th style={{ width: 70 }}>录入方式</th>
                    <th style={{ width: 120 }}>售后订单</th>
                    <th style={{ width: 122 }}>报修日期</th>
                    <th style={{ width: 66 }}>联系人</th>
                    <th style={{ width: 104 }}>联系电话</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((it, index) => (
                    <tr
                      key={it.id}
                      className="row-click"
                      onClick={() => navigate(`/issues/${it.id}`)}
                    >
                      <td onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected.includes(it.id)}
                          onChange={() => toggleOne(it.id)}
                        />
                      </td>
                      <td>{(currentPage - 1) * pageSize + index + 1}</td>
                      <td>
                        <span className="repair-no">{it.repair_no}</span>
                      </td>
                      <td>{it.customer}</td>
                      <td>
                        <span className={`status-badge ${AS_CLASS[it.after_sales_status] ?? 'as-pending'}`}>
                          {it.after_sales_status}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`status-badge ${RESP_CLASS[it.responsibility_status] ?? 'resp-idle'}`}
                        >
                          {it.responsibility_status}
                        </span>
                      </td>
                      <td>{it.fault_type}</td>
                      <td>{it.attribution_raw || '待归因'}</td>
                      <td>
                        <div className="cell-main">{it.component}</div>
                        <div className="cell-sub">{it.phenomenon}</div>
                      </td>
                      <td>{it.source_channel}</td>
                      <td>{it.entry_method}</td>
                      <td className="mono">{it.after_sales_order || '—'}</td>
                      <td>{`${it.date} ${it.report_time}`}</td>
                      <td>{it.contact_name}</td>
                      <td className="mono">{it.contact_phone}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pager">
              <span className="muted">
                共 {filtered.length} 条{selected.length > 0 ? ` · 已选 ${selected.length} 条` : ''}
              </span>
              <div className="pager-pages">
                <button
                  type="button"
                  className="pager-btn"
                  disabled={currentPage <= 1}
                  onClick={() => setPage(currentPage - 1)}
                >
                  上一页
                </button>
                {pageNumbers.map((p) => (
                  <button
                    type="button"
                    key={p}
                    className={`pager-btn${p === currentPage ? ' active' : ''}`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ))}
                <button
                  type="button"
                  className="pager-btn"
                  disabled={currentPage >= totalPages}
                  onClick={() => setPage(currentPage + 1)}
                >
                  下一页
                </button>
              </div>
              <select
                className="filter-select pager-size"
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
              >
                {[10, 20, 50, 100].map((size) => (
                  <option key={size} value={size}>
                    {size} 条/页
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
