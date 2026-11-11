import { useState, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import {
  BookOpen,
  Factory,
  LayoutDashboard,
  ListChecks,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react';
import { resetDemo } from '../api/client';
import './Layout.css';

const NAV = [
  { to: '/', label: '质量工作台', icon: LayoutDashboard, end: true },
  { to: '/issues', label: '售后问题质量库', icon: ListChecks, end: false },
  { to: '/kb', label: '技术协议库', icon: BookOpen, end: false },
  { to: '/alerts', label: '质量归因预警', icon: ShieldAlert, end: false },
];

export default function Layout({ children }: { children: ReactNode }) {
  const [resetting, setResetting] = useState(false);

  const doReset = async () => {
    setResetting(true);
    try {
      await resetDemo();
      window.location.reload();
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Factory size={22} />
          </div>
          <div>
            <div className="brand-title">质量智脑</div>
            <div className="brand-subtitle">产品质量智能平台</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="demo-note">
            <span className="demo-tag">演示数据</span>
            <p>问题、协议、预警均为按真实业务结构构造的演示数据。</p>
          </div>
          <div className="sidebar-version">
            <button type="button" className="reset-btn" onClick={doReset} disabled={resetting}>
              <RotateCcw size={12} />
              {resetting ? '重置中…' : '重置演示操作'}
            </button>
            <div style={{ marginTop: 8 }}>v0.1 · 2026-11</div>
          </div>
        </div>
      </aside>

      <div className="shell">
        <header className="topbar">
          <div className="topbar-title">产品质量智能平台</div>
          <div className="topbar-right">
            <span className="demo-tag">演示环境 · 数据为构造数据</span>
          </div>
        </header>

        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
