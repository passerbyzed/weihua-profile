"""质量智脑 Demo —— HTTP 服务（Python 标准库，无第三方依赖）

启动：
    python backend/server.py
    # 默认 http://127.0.0.1:8010
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import engine
import llm
import reports

ROOT = Path(__file__).resolve().parent
DIST = ROOT.parent / "frontend" / "dist"
PORT = int(os.environ.get("PORT", "8010"))


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "QualityBrain/0.1"

    # ------------------------------------------------------------------ utils
    def log_message(self, fmt: str, *args) -> None:  # 安静一点
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise ApiError(400, f"请求体不是合法 JSON: {exc}") from exc

    # ------------------------------------------------------------------ routes
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self.route_get(path, query)
            else:
                self.serve_static(path)
        except ApiError as exc:
            self.json({"ok": False, "message": exc.message}, exc.status)
        except Exception as exc:  # noqa: BLE001
            self.json({"ok": False, "message": f"服务异常: {exc}"}, 500)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            self.route_post(path)
        except ApiError as exc:
            self.json({"ok": False, "message": exc.message}, exc.status)
        except Exception as exc:  # noqa: BLE001
            self.json({"ok": False, "message": f"服务异常: {exc}"}, 500)

    # ------------------------------------------------------------------ api
    def route_get(self, path: str, query: dict) -> None:
        if path == "/api/health":
            self.json({"ok": True, "today": engine.TODAY.isoformat(), "service": "quality-brain"})
            return

        if path == "/api/overview":
            self.json(engine.dashboard())
            return

        if path == "/api/machines":
            self.json(engine.list_machines())
            return

        if path.startswith("/api/machines/"):
            machine_no = path.split("/api/machines/", 1)[1]
            data = engine.machine_detail(machine_no)
            if not data:
                raise ApiError(404, "未找到该整机")
            self.json(data)
            return

        if path == "/api/issues":
            search = (query.get("search") or [""])[0]
            status = (query.get("status") or [""])[0]
            machine_no = (query.get("machine_id") or [""])[0]
            self.json(engine.list_issues(search, status, machine_no))
            return

        if path.startswith("/api/issues/"):
            rest = path.split("/api/issues/", 1)[1].split("/")
            try:
                issue_id = int(rest[0])
            except ValueError as exc:
                raise ApiError(400, "问题 ID 非法") from exc
            data = engine.analyze_issue(issue_id)
            if not data:
                raise ApiError(404, "未找到该问题")
            self.json(data)
            return

        if path == "/api/alerts":
            self.json(engine.list_alerts())
            return

        if path == "/api/alert-config":
            self.json(engine.load_alert_config())
            return

        if path == "/api/llm/status":
            self.json(llm.status())
            return

        if path == "/api/kb/agreements":
            self.json(engine.agreement_list())
            return

        if path == "/api/kb/agreement":
            doc_id = (query.get("doc_id") or [""])[0]
            if not doc_id:
                raise ApiError(400, "缺少 doc_id")
            doc = engine.agreement_info(doc_id)
            if not doc:
                raise ApiError(404, "技术协议不存在")
            self.json(doc)
            return

        if path == "/api/kb/documents":
            self.json(engine.agreement_list())
            return

        if path == "/api/standards":
            self.json(engine.STANDARDS)
            return

        if path == "/api/dictionaries":
            self.json(
                {
                    "machines": [{"product_no": m["product_no"], "label": f"{m['product_no']} · {m['spec']}"} for m in engine.MACHINES],
                    "components": sorted({i["component"] for i in engine.ISSUES}),
                    "causes": sorted({i["cause"] for i in engine.ISSUES}),
                    "teams": sorted({i["team"] for i in engine.ISSUES if i["team"]}),
                    "designers": sorted({i["designer"] for i in engine.ISSUES if i["designer"]}),
                    "suppliers": sorted({i["supplier"] for i in engine.ISSUES if i["supplier"]}),
                    "fault_types": engine.FAULT_TYPES,
                    "attributions": engine.ATTRIBUTIONS,
                    "alert_levels": ["红", "橙", "黄", "提示"],
                    "check_items": engine.CHECK_ITEMS,
                }
            )
            return

        raise ApiError(404, f"未知接口 {path}")

    def route_post(self, path: str) -> None:
        if path == "/api/issues/ask":
            payload = self.body()
            question = (payload.get("question") or "").strip()
            if not question:
                raise ApiError(400, "请输入问题")
            self.json(engine.answer_issue_question(question, (payload.get("machine_id") or "").strip()))
            return

        if path == "/api/issues/report":
            payload = self.body()
            question = (payload.get("question") or "").strip()
            fmt = (payload.get("format") or "").strip()
            if not question:
                raise ApiError(400, "请先输入问题，再生成报表")
            try:
                content, filename, mime = reports.generate_report(question, fmt)
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            ext = filename.rsplit(".", 1)[-1]
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"report.{ext}\"; filename*=UTF-8''{quote(filename)}",
            )
            self.end_headers()
            self.wfile.write(content)
            return

        if path == "/api/alert-config":
            payload = self.body()
            try:
                self.json(engine.save_alert_config(payload))
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            return

        if path == "/api/kb/ask":
            payload = self.body()
            doc_id = (payload.get("doc_id") or "").strip()
            question = (payload.get("question") or "").strip()
            if not doc_id or not question:
                raise ApiError(400, "请选择技术协议并输入问题")
            result = engine.answer_agreement_question(doc_id, question)
            if not result.get("ok"):
                raise ApiError(404, result.get("message", "问答失败"))
            self.json(result)
            return

        if path == "/api/kb/check":
            payload = self.body()
            doc_id = (payload.get("doc_id") or "").strip()
            item_code = (payload.get("item_code") or "").strip()
            try:
                measured = float(payload.get("measured"))
            except (TypeError, ValueError) as exc:
                raise ApiError(400, "实测值必须是数字") from exc
            result = engine.check_agreement(doc_id, item_code, measured)
            if not result.get("ok"):
                raise ApiError(400, result.get("message", "核对失败"))
            self.json(result)
            return

        if path == "/api/kb/review":
            payload = self.body()
            result = engine.add_review(
                (payload.get("document_id") or payload.get("machine_id") or "").strip(),
                (payload.get("question") or "").strip(),
                payload.get("action") or "confirm",
                payload.get("comment") or "",
            )
            self.json(result)
            return

        if path.startswith("/api/alerts/") and path.endswith("/suggest"):
            alert_no = path.split("/api/alerts/", 1)[1].rsplit("/suggest", 1)[0]
            self.json(engine.generate_alert_suggestion(alert_no))
            return

        if path.startswith("/api/alerts/") and path.endswith("/note"):
            alert_no = path.split("/api/alerts/", 1)[1].rsplit("/note", 1)[0]
            payload = self.body()
            result = engine.save_alert_note(alert_no, payload.get("note") or "")
            if not result.get("ok"):
                raise ApiError(400, result.get("message", "保存失败"))
            self.json(result)
            return

        if path.startswith("/api/alerts/") and path.endswith("/action"):
            alert_no = path.split("/api/alerts/", 1)[1].rsplit("/action", 1)[0]
            payload = self.body()
            result = engine.update_alert(
                alert_no,
                payload.get("action") or "",
                payload.get("reason") or "",
                payload.get("owner") or "质量工程师",
            )
            if not result.get("ok"):
                raise ApiError(400, result.get("message", "操作失败"))
            self.json(result)
            return

        if path == "/api/demo/reset":
            self.json(engine.reset_demo())
            return

        raise ApiError(404, f"未知接口 {path}")

    # ------------------------------------------------------------------ static
    def serve_static(self, path: str) -> None:
        if not DIST.exists():
            self._send(
                200,
                (
                    "<html><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
                    "<h2>前端尚未构建</h2><p>请先在 frontend 目录执行 <code>pnpm build</code>，"
                    "或使用 <code>pnpm dev</code> 启动开发服务器。</p></body></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        rel = path.lstrip("/") or "index.html"
        target = (DIST / rel).resolve()
        try:
            target.relative_to(DIST.resolve())
        except ValueError:
            raise ApiError(403, "禁止访问")

        if target.is_file():
            content = target.read_bytes()
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            self._send(200, content, ctype)
            return

        index = DIST / "index.html"
        if index.exists():
            self._send(200, index.read_bytes(), "text/html; charset=utf-8")
            return
        raise ApiError(404, "未找到静态文件")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[quality-brain] http://127.0.0.1:{PORT}  (today={engine.TODAY})")
    print(f"[quality-brain] dist={'ready' if DIST.exists() else 'missing'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
