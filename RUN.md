# 质量智脑 Demo · 运行说明

## 直接打开（已构建）

服务已在本机 `8010` 端口运行，浏览器打开：

```
http://127.0.0.1:8010
```

## 启动 / 关闭

### 启动

```powershell
cd C:\code\weihua_zhiliang
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

也可以右键 `start.ps1` →「使用 PowerShell 运行」。窗口会一直开着，关掉窗口服务就停了。

`start.ps1` 会在 `frontend/dist` 不存在时先构建前端，再启动后端，然后输出：

```
[2/2] 启动质量智脑：http://127.0.0.1:8010
```

### 关闭

三种方式，任选一种：

```powershell
# 1. 在启动服务的窗口按 Ctrl+C

# 2. 另开一个 PowerShell 窗口，运行停止脚本
powershell -ExecutionPolicy Bypass -File .\stop.ps1

# 3. 直接按端口杀进程
Get-NetTCPConnection -LocalPort 8010 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

`stop.ps1` 默认只停 8010；要连开发模式的 5173 一起停：

```powershell
powershell -ExecutionPolicy Bypass -File .\stop.ps1 -Ports 8010,5173
```

### 确认是否在运行

浏览器打开 `http://127.0.0.1:8010/api/health`，返回 `{"ok":true,...}` 即为运行中。

## 开发模式（改前端代码即时生效）

开两个终端：

```powershell
# 终端 1：后端
python backend\server.py

# 终端 2：前端（Vite，自动代理 /api 到 8010）
cd frontend
pnpm dev
```

打开 `http://127.0.0.1:5173`；关闭时两个终端分别按 Ctrl+C。

## 接入 DeepSeek（问题库问答 + 档案问答）

1. 打开 `backend/.env`
2. **第 3 行** `DEEPSEEK_API_KEY=` 等号后面填 `sk-` 开头的 Key
3. 保存，重启后端（`start.ps1` 或 `python backend\server.py`）

```
# backend/.env 第 1～4 行
# DeepSeek 配置
# 【在这里填 API Key】把 sk- 开头的 Key 填到下面一行的等号后面，保存后重启 backend/server.py
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

不需要改代码。未填 Key 时自动回退「规则摘要」，页面会提示；填好后两个问答入口都是真实调用，模型名和耗时显示在回答上方。

## 目录

```
backend/
  server.py          # HTTP 服务（Python 标准库）
  engine.py          # 检索、研判、问答、三查、预警
  data/*.json        # 演示数据（改这里就能改演示内容）
frontend/            # React + Vite + TypeScript
docs/                # 产品设计文档
```

## 演示操作提示

- 售后问题质量库 → 打开 `QI-202611-0032`，看相似历史、根因假设、质量链。
- 问题库智能问答 → 输入「缓冲器和制动器各出现多少次？」，点「生成报表」，可选 Excel / PDF / Word；两个维度都会统计。
- 技术协议库 → 搜索并选中一份 PDF（如 `2001001111`），再提问；回答只返回该协议原文，点引用看页码。
- 不符合项核对 → 选择 `2001001111`，默认 `140 μm`，演示「不符合协议要求」（要求 ≥150μm）。
- 质量归因预警 → 「涂装制作问题聚集」预警可确认 / 转整改 / 误报；预警配置里可改阈值。
- 左下角「重置演示操作」可清掉确认、误报、核对记录。

### 新增技术协议 PDF

把 PDF 放进 `docs/`，重新生成索引：

```powershell
python backend/data/build_agreements.py
```

刷新技术协议库即可搜索到新协议。索引脚本只做原文抽取和分块，不做摘要或推导。

## 报表导出依赖

问题库的「生成报表」使用 `openpyxl`（Excel）、`python-docx`（Word）、`reportlab`（PDF）。
`start.ps1` 优先使用内置 Python 运行时（已安装这些库）；如果用系统 Python 直接运行 `python backend\server.py`，先执行：

```powershell
pip install -r backend\requirements.txt
```

## 说明

- 所有数据均为演示数据，接口未接 OA / SAP / PDM。
- 技术协议库只做原文检索，不调用大模型、不生成结论；问题库问答/预警建议可选 DeepSeek，未配置时用规则。
