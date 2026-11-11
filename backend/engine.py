"""质量智脑 Demo —— 分析引擎（纯标准库）

设计原则：
- 检索、比对、判定用确定性规则，结果可解释、可复现；
- 所有结论挂证据（历史问题编号 / 档案条款编号）；
- 没有依据时明确返回 not_mentioned，不编造。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import llm

DATA_DIR = Path(__file__).parent / "data"
TODAY = date(2026, 11, 10)


def _load(name: str) -> Any:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


MACHINES = _load("machines.json")
DOCUMENTS = _load("documents.json")
AGREEMENT = _load("agreement.json")
AGREEMENTS = _load("agreements.json")
AGREEMENTS_BY_ID = {doc["id"]: doc for doc in AGREEMENTS}
ISSUES = _load("issues.json")
INSPECTIONS = _load("inspections.json")
TRACES = _load("traces.json")
STANDARDS = _load("standards.json")
BASELINES = _load("baselines.json")

MACHINE_BY_NO = {m["product_no"]: m for m in MACHINES}
ISSUE_BY_ID = {i["id"]: i for i in ISSUES}
ISSUE_BY_NO = {i["issue_no"]: i for i in ISSUES}

# ---------------------------------------------------------------------------
# 字典
# ---------------------------------------------------------------------------

PRIORITY = {"ECN": 4, "TA": 3, "DWG": 2, "HT": 1}

ITEMS = [
    {
        "key": "paint",
        "label": "油漆 / 涂装",
        "aliases": ["油漆", "涂装", "面漆", "底漆", "漆膜", "膜厚", "涂层", "颜色", "色差", "盐雾"],
        "component": "涂装层",
        "keys": ["paint_dft", "paint_salt", "paint_color", "paint_prep"],
        "short": "高于标准配置",
    },
    {
        "key": "hook",
        "label": "吊钩",
        "aliases": ["吊钩", "钩头", "吊钩组", "钩"],
        "component": "吊钩组",
        "keys": ["hook_material", "hook_lock", "hook_doc"],
        "short": "为指定材质与配置",
    },
    {
        "key": "steel",
        "label": "钢板 / 主梁",
        "aliases": ["钢板", "板材", "翼缘", "板厚", "Q355", "材质"],
        "component": "主梁",
        "keys": ["steel_flange", "steel_deviation", "steel_ut"],
        "short": "高于标准配置",
    },
    {
        "key": "cabinet",
        "label": "电控柜",
        "aliases": ["电控柜", "电气柜", "控制箱", "配电箱", "防护等级", "IP"],
        "component": "电控柜",
        "keys": ["cabinet_ip"],
        "short": "高于标准配置",
    },
    {
        "key": "warranty",
        "label": "质保期",
        "aliases": ["质保", "保修", "三包"],
        "component": "",
        "keys": ["warranty"],
        "short": "长于标准配置",
    },
    {
        "key": "rope",
        "label": "钢丝绳",
        "aliases": ["钢丝绳", "钢绳", "换绳"],
        "component": "钢丝绳",
        "keys": [],
        "short": "",
    },
]

FAULT_MODE_RULES = [
    ("异响", ["异响", "响声", "噪音"]),
    ("啃轨", ["啃轨", "跑偏", "摩擦"]),
    ("起泡", ["起泡", "鼓包", "脱落"]),
    ("色差", ["色差", "颜色不一致"]),
    ("膜厚", ["膜厚", "厚度不足", "漆膜"]),
    ("卡滞", ["卡滞", "卡阻", "不动作"]),
    ("焊缝", ["焊缝", "未熔合", "裂纹"]),
    ("板厚", ["板厚", "钢板厚度", "负偏差"]),
    ("漏油", ["漏油", "渗油"]),
    ("电气故障", ["烧毁", "进水", "绝缘", "跳闸", "失电", "参数错误"]),
]


def fault_mode(text: str) -> str:
    for mode, words in FAULT_MODE_RULES:
        if any(w in text for w in words):
            return mode
    return "其他"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def months_between(a: date, b: date) -> float:
    return abs((a - b).days) / 30.44


def bigrams(text: str) -> set[str]:
    text = re.sub(r"[\s，。、；：,.!?！？]", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)} or {text}


def jaccard(a: str, b: str) -> float:
    sa, sb = bigrams(a), bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(m.group()) if m else None


def clamp(value: float, low: float = 0.0, high: float = 0.99) -> float:
    return max(low, min(high, value))


def pct(value: float) -> int:
    return int(round(value * 100))


# ---------------------------------------------------------------------------
# 整机与问题
# ---------------------------------------------------------------------------

def list_machines() -> list[dict]:
    result = []
    for m in MACHINES:
        docs = [d for d in DOCUMENTS if d.get("machine_id") == m["product_no"]]
        issues = [i for i in ISSUES if i["machine_id"] == m["product_no"]]
        result.append(
            {
                **m,
                "doc_count": len(docs),
                "issue_count": len(issues),
                "docs": [
                    {
                        "id": d["id"],
                        "type": d["type"],
                        "title": d["title"],
                        "version": d["version"],
                        "doc_no": d["doc_no"],
                        "effective_date": d["effective_date"],
                        "clause_count": len(d["clauses"]),
                    }
                    for d in docs
                ],
            }
        )
    return result


def issue_summary(issue: dict) -> dict:
    machine = MACHINE_BY_NO.get(issue["machine_id"], {})
    days = None
    if issue.get("closed_at"):
        days = (parse_date(issue["closed_at"]) - parse_date(issue["date"])).days
    return {
        **issue,
        "model_code": machine.get("model_code", ""),
        "model_name": machine.get("model_name", ""),
        "spec": machine.get("spec", ""),
        "duration_days": days,
    }


def list_issues(search: str = "", status: str = "", machine_id: str = "") -> list[dict]:
    items = ISSUES
    if status:
        items = [i for i in items if i["status"] == status]
    if machine_id:
        items = [i for i in items if i["machine_id"] == machine_id]
    if search:
        q = search.lower()
        items = [
            i
            for i in items
            if any(
                q in str(i.get(f, "")).lower()
                for f in ("issue_no", "customer", "machine_id", "component", "phenomenon", "cause")
            )
        ]
    return [issue_summary(i) for i in sorted(items, key=lambda x: x["date"], reverse=True)]


def get_issue(issue_id: int) -> dict | None:
    issue = ISSUE_BY_ID.get(issue_id)
    if not issue:
        return None
    return issue_summary(issue)


# ---------------------------------------------------------------------------
# 相似问题召回
# ---------------------------------------------------------------------------

def similar_issues(issue_id: int, limit: int = 6) -> list[dict]:
    current = ISSUE_BY_ID.get(issue_id)
    if not current:
        return []
    cur_mode = fault_mode(current["phenomenon"] + current["description"])
    cur_model = MACHINE_BY_NO.get(current["machine_id"], {}).get("model_code", "")
    scored = []
    for other in ISSUES:
        if other["id"] == issue_id:
            continue
        sim = max(
            jaccard(current["phenomenon"], other["phenomenon"]),
            jaccard(current["phenomenon"] + current["description"], other["phenomenon"] + other["description"]),
        )
        comp = 1.0 if other["component_code"] == current["component_code"] else 0.0
        model = 1.0 if MACHINE_BY_NO.get(other["machine_id"], {}).get("model_code") == cur_model else 0.0
        customer = 1.0 if other["customer"] == current["customer"] else 0.0
        decay = math.exp(-months_between(parse_date(current["date"]), parse_date(other["date"])) / 18)
        mode = 1.0 if fault_mode(other["phenomenon"] + other["description"]) == cur_mode else 0.0
        score = 0.30 * sim + 0.40 * comp + 0.10 * model + 0.10 * customer + 0.10 * decay + 0.05 * mode
        if comp and mode:
            score += 0.10
        score = clamp(score)
        reasons = []
        if customer:
            reasons.append("同客户")
        if model:
            reasons.append("同机型")
        if comp:
            reasons.append("同部件")
        if mode:
            reasons.append(f"同故障模式 · {cur_mode}")
        if sim >= 0.3:
            reasons.append(f"现象相似 {pct(sim)}%")
        if not reasons:
            reasons.append("历史关联")
        tier = "A" if score >= 0.85 else "B" if score >= 0.62 else "C" if score >= 0.5 else "D"
        scored.append(
            {
                "issue": issue_summary(other),
                "score": round(score, 3),
                "tier": tier,
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


# ---------------------------------------------------------------------------
# 质量链
# ---------------------------------------------------------------------------

def quality_chain(issue: dict) -> dict:
    machine_no = issue["machine_id"]
    machine = MACHINE_BY_NO.get(machine_no, {})
    docs = [d for d in DOCUMENTS if d.get("machine_id") == machine_no]
    traces = [t for t in TRACES if t["machine_id"] == machine_no]
    inspections = [x for x in INSPECTIONS if x["machine_id"] == machine_no]

    stages = []

    ta = next((d for d in docs if d["type_code"] == "TA"), None)
    stages.append(
        {
            "stage": "需求 / 合同",
            "status": "ok" if ta else "missing",
            "summary": (
                "技术协议要求面漆 ≥240μm、吊钩 35CrMo、上翼缘 25mm"
                if ta and machine_no == "LD5-2024-0316"
                else (f"已归档{len(docs)}份档案" if docs else "未找到合同/技术协议")
            ),
            "refs": [d["id"] for d in docs if d["type_code"] in ("TA", "HT", "ECN")],
        }
    )

    dwg = [d for d in docs if d["type_code"] == "DWG"]
    stages.append(
        {
            "stage": "设计",
            "status": "ok" if dwg else "missing",
            "summary": (
                f"{dwg[0]['title']} {dwg[0]['version']}，设计人 {machine.get('designer', '—')}"
                if dwg
                else "未找到图纸"
            ),
            "refs": [d["id"] for d in dwg],
        }
    )

    steel_trace = next((t for t in traces if "主梁" in t["component"]), None)
    stages.append(
        {
            "stage": "来料",
            "status": "ok" if steel_trace else "missing",
            "summary": (
                f"{steel_trace['supplier']} · 炉批号 {steel_trace['batch']}"
                if steel_trace
                else "未找到来料批次记录"
            ),
            "refs": [steel_trace["batch"]] if steel_trace else [],
        }
    )

    team_trace = next((t for t in traces if t["component"] == issue["component"]), None) or steel_trace
    stages.append(
        {
            "stage": "制造",
            "status": "ok" if team_trace else "missing",
            "summary": (
                f"{team_trace['team']} · {team_trace['process']} · {team_trace['date']}"
                if team_trace
                else "未找到班组/工序记录"
            ),
            "refs": [team_trace["batch"]] if team_trace else [],
        }
    )

    assembly = [x for x in inspections if x["item_code"] == "ASM"]
    if assembly:
        inspection_summary = f"装配检验记录 {len(assembly)} 条"
    elif inspections:
        inspection_summary = f"未找到整机装配检验记录（仅有 {len(inspections)} 条单项抽检）"
    else:
        inspection_summary = "未找到检验记录"
    stages.append(
        {
            "stage": "检验",
            "status": "ok" if assembly else "missing",
            "summary": inspection_summary,
            "refs": [x["item_name"] for x in inspections[:3]],
        }
    )

    stages.append(
        {
            "stage": "交付",
            "status": "ok" if machine.get("delivery_date") else "missing",
            "summary": f"出厂 {machine.get('manufacture_date', '—')} · 交付 {machine.get('delivery_date', '—')}",
            "refs": [machine.get("serial_no", "")],
        }
    )

    stages.append(
        {
            "stage": "售后",
            "status": "ok",
            "summary": f"{issue['issue_no']} · {issue['phenomenon']} · {issue['status']}",
            "refs": [issue["issue_no"]],
        }
    )

    filled = sum(1 for s in stages if s["status"] == "ok")
    gaps = [f"{s['stage']}段缺失：{s['summary']}" for s in stages if s["status"] == "missing"]
    return {"stages": stages, "completeness": filled, "total": len(stages), "gaps": gaps}


# ---------------------------------------------------------------------------
# 根因假设与处置建议
# ---------------------------------------------------------------------------

HYPOTHESIS_LIBRARY: dict[tuple[str, str], list[dict]] = {
    ("卷筒轴承座", "异响"): [
        {
            "cause": "卷筒轴承座同轴度超差",
            "verify": "复测轴承座与卷筒同轴度，图纸要求 ≤0.1 mm",
            "keywords": ["同轴度", "轴承座"],
        },
        {
            "cause": "轴承磨损或润滑不足",
            "verify": "检查轴承游隙、滚道与润滑脂状态",
            "keywords": ["磨损", "游隙", "润滑"],
        },
        {
            "cause": "安装螺栓松动",
            "verify": "按扭矩要求复紧轴承座安装螺栓",
            "keywords": ["螺栓", "松动"],
        },
    ],
    ("涂装层", "起泡"): [
        {
            "cause": "前处理未达 Sa2.5",
            "verify": "核查除锈等级与表面粗糙度记录",
            "keywords": ["前处理", "Sa2.5", "除锈"],
        },
        {
            "cause": "除锈后待涂时间超 4 h",
            "verify": "核查涂装施工记录与当班湿度",
            "keywords": ["待涂", "湿度"],
        },
        {
            "cause": "漆膜过厚导致溶剂残留",
            "verify": "测厚并核查每道涂层间隔",
            "keywords": ["膜厚", "遍数"],
        },
    ],
    ("涂装层", "膜厚"): [
        {
            "cause": "喷涂遍数不足",
            "verify": "按协议膜厚复核施工遍数与湿膜厚度",
            "keywords": ["遍数", "膜厚"],
        },
        {
            "cause": "未按项目非标膜厚执行",
            "verify": "核对技术协议与图纸标注差异",
            "keywords": ["协议", "图纸", "非标"],
        },
    ],
    ("涂装层", "色差"): [
        {
            "cause": "调漆比例偏差",
            "verify": "核对调漆记录与色板比对记录",
            "keywords": ["调漆", "色板"],
        }
    ],
    ("车轮", "啃轨"): [
        {
            "cause": "轨距公差标注偏大",
            "verify": "复核图纸轨距公差与工艺能力",
            "keywords": ["轨距", "公差"],
        },
        {
            "cause": "车轮同位差超差",
            "verify": "测量同一端梁两车轮同位差",
            "keywords": ["同位差", "车轮"],
        },
    ],
    ("小车运行机构", "啃轨"): [
        {
            "cause": "小车轨距公差标注与工艺不匹配",
            "verify": "复核小车轨距公差标注",
            "keywords": ["轨距", "公差"],
        }
    ],
    ("主梁", "板厚"): [
        {
            "cause": "钢板负偏差超差",
            "verify": "按炉批号复验板厚与材质证明",
            "keywords": ["负偏差", "钢板"],
        }
    ],
    ("主梁", "焊缝"): [
        {
            "cause": "未按 WPS 施焊",
            "verify": "核查焊接工艺记录、预热与层间温度",
            "keywords": ["WPS", "预热", "焊工"],
        }
    ],
}


def hypotheses(issue: dict, similar: list[dict]) -> list[dict]:
    mode = fault_mode(issue["phenomenon"] + issue["description"])
    library = HYPOTHESIS_LIBRARY.get((issue["component"], mode))
    if not library:
        library = [
            {
                "cause": "装配精度不满足要求",
                "verify": "按图纸复测相关装配尺寸",
                "keywords": ["装配", "精度"],
            },
            {
                "cause": "来料/外协件质量波动",
                "verify": "追溯批次并复验关键尺寸",
                "keywords": ["来料", "外协", "批次"],
            },
        ]
    result = []
    for idx, item in enumerate(library):
        evidence = []
        for hit in similar:
            other = hit["issue"]
            if any(k in (other.get("cause_detail") or "") for k in item["keywords"]):
                evidence.append(other["issue_no"])
        confidence = "high" if len(evidence) >= 1 and idx == 0 else "medium" if idx == 0 else "low"
        if len(evidence) >= 2:
            confidence = "high"
        result.append(
            {
                "cause": item["cause"],
                "verify": item["verify"],
                "evidence": evidence[:3],
                "confidence": confidence,
            }
        )
    return result


def suggestions(issue: dict, similar: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for hit in similar:
        if hit["tier"] not in ("A", "B"):
            continue
        other = hit["issue"]
        measure = other.get("handling") or ""
        if not measure:
            continue
        bucket = buckets.setdefault(
            measure,
            {"measure": measure, "count": 0, "resolved": 0, "days": [], "evidence": [], "score": 0.0},
        )
        bucket["count"] += 1
        bucket["resolved"] += 1 if other.get("resolved") else 0
        if other.get("duration_days"):
            bucket["days"].append(other["duration_days"])
        bucket["evidence"].append(other["issue_no"])
        bucket["score"] += hit["score"]
    result = []
    for bucket in buckets.values():
        avg_days = int(sum(bucket["days"]) / len(bucket["days"])) if bucket["days"] else 0
        history = f"采用 {bucket['count']} 次 · 解决 {bucket['resolved']} 次"
        if avg_days:
            history += f" · 平均 {avg_days} 天闭环"
        result.append(
            {
                "measure": bucket["measure"],
                "score": round(bucket["score"] / max(bucket["count"], 1), 3),
                "history": history,
                "evidence": bucket["evidence"][:3],
            }
        )
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:4]


# ---------------------------------------------------------------------------
# 研判汇总
# ---------------------------------------------------------------------------

def analyze_issue(issue_id: int) -> dict | None:
    issue = get_issue(issue_id)
    if not issue:
        return None
    machine = MACHINE_BY_NO.get(issue["machine_id"], {})
    similar = similar_issues(issue_id)
    chain = quality_chain(issue)
    hyps = hypotheses(issue, similar)
    sugg = suggestions(issue, similar)
    strong = [s for s in similar if s["tier"] in ("A", "B")]
    confidence = "high" if strong and any(h["confidence"] == "high" for h in hyps) else "medium"
    extraction = {
        "machine_no": {"value": issue["machine_id"], "confidence": 0.98},
        "customer": {"value": issue["customer"], "confidence": 0.96},
        "component": {"value": issue["component"], "confidence": 0.94},
        "fault_mode": {"value": fault_mode(issue["phenomenon"]), "confidence": 0.92},
        "phenomenon": {"value": issue["phenomenon"], "confidence": 0.93},
        "stage": {"value": issue["stage"], "confidence": 0.95},
    }
    return {
        "issue": issue,
        "machine": machine,
        "similar": similar,
        "chain": chain,
        "hypotheses": hyps,
        "suggestions": sugg,
        "extraction": extraction,
        "confidence": confidence,
        "summary": {
            "similar_count": len(similar),
            "high_count": len([s for s in similar if s["tier"] == "A"]),
            "chain_completeness": f"{chain['completeness']}/{chain['total']}",
        },
    }


# ---------------------------------------------------------------------------
# 档案知识库
# ---------------------------------------------------------------------------

def machine_documents(machine_no: str) -> list[dict]:
    docs = []
    for d in DOCUMENTS:
        if d.get("machine_id") != machine_no:
            continue
        docs.append(
            {
                "id": d["id"],
                "type": d["type"],
                "type_code": d["type_code"],
                "title": d["title"],
                "doc_no": d["doc_no"],
                "version": d["version"],
                "effective_date": d["effective_date"],
                "status": d["status"],
                "pages": d["pages"],
                "summary": d.get("summary", ""),
                "clause_count": len(d["clauses"]),
            }
        )
    return docs


AGREEMENT_ITEM_DEFS = [
    {
        "key": "paint",
        "label": "油漆 / 涂装",
        "aliases": ["油漆", "涂装", "防腐", "漆膜", "面漆", "底漆", "涂层"],
        "keys": [
            "paint_coat",
            "paint_internal_dft",
            "paint_prep",
            "paint_warranty",
            "paint_color",
        ],
    },
    {
        "key": "hook",
        "label": "吊钩",
        "aliases": ["吊钩", "钩头", "吊钩组"],
        "keys": ["hook_qty", "hook_forging", "hook_cert"],
    },
    {
        "key": "steel",
        "label": "钢板 / 钢材",
        "aliases": ["钢板", "钢材", "板材", "板厚", "材质", "Q345", "Q355"],
        "keys": ["steel_grade", "steel_main_thickness", "steel_secondary_thickness"],
    },
    {
        "key": "power",
        "label": "供电",
        "aliases": ["电源", "供电", "电压", "10kV"],
        "keys": ["power"],
    },
    {
        "key": "warranty",
        "label": "质保期",
        "aliases": ["质保", "保修"],
        "keys": ["warranty"],
    },
    {
        "key": "rope",
        "label": "钢丝绳",
        "aliases": ["钢丝绳", "钢绳"],
        "keys": ["rope_safety"],
    },
    {
        "key": "wheel",
        "label": "车轮",
        "aliases": ["车轮", "走轮"],
        "keys": ["wheel_hardness", "wheel_life"],
    },
    {
        "key": "parameter",
        "label": "整机参数",
        "aliases": ["起重量", "幅度", "起升高度", "轨距", "工作速度"],
        "keys": ["capacity_hook", "capacity_grab", "rail"],
    },
]

AGREEMENT_CHECK_ITEMS = {
    "paint_internal_dft": {
        "label": "箱梁内部漆膜总厚度",
        "unit": "μm",
        "minimum": 150,
        "clause_id": "CL-AG-5.2",
    },
    "steel_main_thickness": {
        "label": "主要承载构件板厚",
        "unit": "mm",
        "minimum": 8,
        "clause_id": "CL-AG-2.2.1b",
    },
    "rope_safety": {
        "label": "钢丝绳安全系数",
        "unit": "",
        "minimum": 9,
        "clause_id": "CL-AG-3.8.1",
    },
}


def agreement_list() -> list[dict]:
    return [agreement_info(doc["id"]) for doc in AGREEMENTS]


def agreement_info(doc_id: str | None = None) -> dict | None:
    if not doc_id or doc_id == AGREEMENT["id"]:
        doc = {key: value for key, value in AGREEMENT.items() if key != "clauses"}
        doc["clause_count"] = len(AGREEMENT["clauses"])
        raw = AGREEMENTS_BY_ID.get(AGREEMENT["id"])
        doc["chunk_count"] = raw["chunk_count"] if raw else len(AGREEMENT["clauses"])
        return doc
    raw = AGREEMENTS_BY_ID.get(doc_id)
    if not raw:
        return None
    return {
        "id": raw["id"],
        "type": "技术协议",
        "type_code": "TA",
        "title": raw["title"],
        "doc_no": raw["doc_no"],
        "version": "PDF 原文件",
        "machine_id": "",
        "contract_no": "",
        "library": "agreement",
        "effective_date": "",
        "status": "生效",
        "pages": raw["pages"],
        "file_name": raw["file_name"],
        "summary": f"PDF 原文件，共 {raw['pages']} 页；问答只返回原文摘录。",
        "clause_count": raw["chunk_count"],
        "chunk_count": raw["chunk_count"],
    }


def _agreement_entries(keys: list[str]) -> dict[str, list[dict]]:
    entries: dict[str, list[dict]] = {key: [] for key in keys}
    for clause in AGREEMENT["clauses"]:
        for key, value in (clause.get("values") or {}).items():
            if key in entries:
                entries[key].append({"clause": clause, "value": value})
    return entries


def detect_agreement_items(question: str) -> list[dict]:
    found = []
    for item in AGREEMENT_ITEM_DEFS:
        positions = [question.find(alias) for alias in item["aliases"] if alias in question]
        if positions:
            found.append((min(positions), item))
    found.sort(key=lambda pair: pair[0])
    return [item for _, item in found]


def _agreement_citation(clause: dict, cid: str) -> dict:
    return {
        "cid": cid,
        "doc_id": AGREEMENT["id"],
        "doc_title": AGREEMENT["title"],
        "doc_no": AGREEMENT["doc_no"],
        "doc_type": AGREEMENT["type"],
        "version": AGREEMENT["version"],
        "effective_date": AGREEMENT["effective_date"],
        "clause_id": clause["id"],
        "clause_no": clause["clause_no"],
        "section": clause["section"],
        "page": clause["page"],
        "text": clause["text"],
        "verify_status": "待核对",
    }


def _answer_structured_agreement(question: str) -> dict:
    document = agreement_info(AGREEMENT["id"])
    items = detect_agreement_items(question)
    if not items:
        return {
            "ok": True,
            "answer_type": "need_object",
            "question": question,
            "document": document,
            "conclusion": "没有识别到具体要问的项，请指明对象（如油漆、吊钩、钢板、质保期、钢丝绳）。",
            "items": [],
            "conflicts": [],
            "gaps": [],
            "citations": [],
            "confidence": "low",
            "mode": "retrieval+rule",
            "review_status": _review_status(AGREEMENT["id"], question),
        }

    citations: list[dict] = []
    cid_map: dict[str, str] = {}

    def cite(clause: dict) -> str:
        cid = cid_map.get(clause["id"])
        if cid:
            return cid
        cid = f"C{len(citations) + 1}"
        cid_map[clause["id"]] = cid
        citations.append(_agreement_citation(clause, cid))
        return cid

    answer_items = []
    gaps = []
    for item in items:
        entries = _agreement_entries(item["keys"])
        clauses: list[dict] = []
        for key in item["keys"]:
            for entry in entries.get(key) or []:
                if all(clause["id"] != entry["clause"]["id"] for clause in clauses):
                    clauses.append(entry["clause"])
        item_cites = [cite(clause) for clause in clauses]
        requirement = "\n\n".join(clause["text"] for clause in clauses)
        notes = [clause["notes"] for clause in clauses if clause.get("notes")]
        if clauses:
            verdict = "specified"
        else:
            verdict = "not_mentioned"
            gaps.append(f"协议中未找到关于「{item['label']}」的条款。")
        answer_items.append(
            {
                "object": item["label"],
                "verdict": verdict,
                "requirement": requirement or "协议未提及",
                "standard_value": "—",
                "difference": "—",
                "citations": item_cites,
                "confidence": "high" if clauses else "low",
                "notes": notes,
            }
        )

    mentioned = [item for item in answer_items if item["verdict"] == "specified"]
    if mentioned:
        conclusion = (
            "以下为协议原文摘录，未做归纳、推算或补全："
            + "、".join(item["object"] for item in mentioned)
            + "。请逐条核对引用页码与原文。"
        )
    else:
        conclusion = "未在技术协议中找到与该问题相关的条款。"

    confidence = "high" if mentioned and all(i["verdict"] != "not_mentioned" for i in answer_items) else "medium"
    return {
        "ok": True,
        "answer_type": "agreement_query",
        "question": question,
        "document": document,
        "conclusion": conclusion,
        "items": answer_items,
        "conflicts": [],
        "gaps": gaps,
        "citations": citations,
        "confidence": confidence,
        "mode": "retrieval+verbatim",
        "llm": {},
        "review_status": _review_status(AGREEMENT["id"], question),
    }


def _chunk_citation(document: dict, chunk: dict, cid: str) -> dict:
    return {
        "cid": cid,
        "doc_id": document["id"],
        "doc_title": document["title"],
        "doc_no": document["doc_no"],
        "doc_type": "技术协议",
        "version": document["version"],
        "effective_date": document["effective_date"],
        "clause_id": chunk["id"],
        "clause_no": f"第 {chunk['page']} 页",
        "section": "",
        "page": chunk["page"],
        "text": chunk["text"],
        "verify_status": "待核对",
    }


def _search_agreement_chunks(doc: dict, terms: list[str], limit: int = 2) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    for chunk in doc["chunks"]:
        text = chunk["text"]
        if len(text) < 40 or "......" in text:
            continue
        score = 0.0
        for term in terms:
            count = text.count(term)
            if count:
                score += count * 4
                if term in text[:80]:
                    score += 3
        if score <= 0:
            continue
        # 标准清单、目录类文本降权，避免答非所问
        if text.count("JB/T") + text.count("GB/T") >= 3:
            score -= 4
        if text.count("\n") > 14:
            score -= 1
        scored.append((score, chunk))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["page"]))
    picked: list[dict] = []
    seen: set[str] = set()
    for _, chunk in scored:
        fingerprint = chunk["text"][:60]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        picked.append(chunk)
        if len(picked) >= limit:
            break
    return picked


def _generic_agreement_answer(document: dict, question: str) -> dict:
    raw = AGREEMENTS_BY_ID[document["id"]]
    items = detect_agreement_items(question)
    if not items:
        return {
            "ok": True,
            "answer_type": "need_object",
            "question": question,
            "document": document,
            "conclusion": "没有识别到具体要问的项，请指明对象（如油漆、吊钩、钢板、质保期、钢丝绳）。",
            "items": [],
            "conflicts": [],
            "gaps": [],
            "citations": [],
            "confidence": "low",
            "mode": "retrieval+verbatim",
            "review_status": _review_status(document["id"], question),
        }

    citations: list[dict] = []
    cid_map: dict[str, str] = {}

    def cite(chunk: dict) -> str:
        cid = cid_map.get(chunk["id"])
        if cid:
            return cid
        cid = f"C{len(citations) + 1}"
        cid_map[chunk["id"]] = cid
        citations.append(_chunk_citation(document, chunk, cid))
        return cid

    answer_items = []
    gaps = []
    for item in items:
        chunks = _search_agreement_chunks(raw, item["aliases"], limit=2)
        item_cites = [cite(chunk) for chunk in chunks]
        if chunks:
            verdict = "specified"
        else:
            verdict = "not_mentioned"
            gaps.append(f"该协议中未检索到关于「{item['label']}」的原文。")
        answer_items.append(
            {
                "object": item["label"],
                "verdict": verdict,
                "requirement": "\n\n".join(chunk["text"] for chunk in chunks) or "协议未提及",
                "standard_value": "—",
                "difference": "—",
                "citations": item_cites,
                "confidence": "high" if chunks else "low",
                "notes": [],
            }
        )

    mentioned = [item for item in answer_items if item["verdict"] == "specified"]
    if mentioned:
        conclusion = (
            "以下为协议原文摘录，未做归纳、推算或补全："
            + "、".join(item["object"] for item in mentioned)
            + "。请逐条核对引用页码与原文。"
        )
    else:
        conclusion = "未在该技术协议中检索到与该问题相关的原文。"

    confidence = "high" if mentioned and all(i["verdict"] != "not_mentioned" for i in answer_items) else "medium"
    return {
        "ok": True,
        "answer_type": "agreement_query",
        "question": question,
        "document": document,
        "conclusion": conclusion,
        "items": answer_items,
        "conflicts": [],
        "gaps": gaps,
        "citations": citations,
        "confidence": confidence,
        "mode": "retrieval+verbatim",
        "llm": {},
        "review_status": _review_status(document["id"], question),
    }


def answer_agreement_question(doc_id: str, question: str) -> dict:
    document = agreement_info(doc_id)
    if not document:
        return {"ok": False, "message": "技术协议不存在"}
    if document["doc_no"] == AGREEMENT["doc_no"]:
        return _answer_structured_agreement(question)
    return _generic_agreement_answer(document, question)


def check_agreement(doc_id: str, item_code: str, measured: float) -> dict:
    document = agreement_info(doc_id)
    if not document:
        return {"ok": False, "message": "技术协议不存在"}
    if document["doc_no"] != AGREEMENT["doc_no"]:
        return {"ok": False, "message": "该协议暂未配置自动核对项，请到协议问答查看原文。"}
    item = AGREEMENT_CHECK_ITEMS.get(item_code)
    if not item:
        return {"ok": False, "message": "不支持的检查项"}
    clause = next((c for c in AGREEMENT["clauses"] if c["id"] == item["clause_id"]), None)
    if not clause:
        return {"ok": False, "message": "协议条款缺失"}
    minimum = item["minimum"]
    passed = measured >= minimum
    unit_suffix = f" {item['unit']}" if item["unit"] else ""
    return {
        "ok": True,
        "document": document,
        "item": {"label": item["label"], "unit": item["unit"], "code": item_code},
        "measured": measured,
        "requirement": {
            "value": minimum,
            "display": f"≥{minimum:g}{unit_suffix}",
            "source": {
                "doc_title": document["title"],
                "version": document["version"],
                "doc_no": document["doc_no"],
                "doc_id": document["id"],
                "clause_id": clause["id"],
                "clause_no": clause["clause_no"],
                "page": clause["page"],
                "text": clause["text"],
            },
        },
        "verdict": "符合协议要求" if passed else "不符合协议要求",
        "severity": "ok" if passed else "bad",
        "reason": (
            f"实测 {measured:g}{unit_suffix}；协议原文要求 {item['label']} ≥{minimum:g}{unit_suffix}。"
        ),
        "suggestions": (
            ["实测值满足协议要求，按批次留证归档。"]
            if passed
            else [
                "按协议要求返工或更换，复测后留存记录",
                "如确需让步接收，须取得招标方书面同意",
                "同步核查同批次产品，避免批量超差",
            ]
        ),
        "review_status": "待核对",
    }


def detect_items(question: str) -> list[dict]:
    found = []
    for item in ITEMS:
        positions = [question.find(a) for a in item["aliases"] if a in question]
        if positions:
            found.append((min(positions), item))
    found.sort(key=lambda x: x[0])
    return [item for _, item in found]


def _clause_entries(machine_no: str, keys: list[str]) -> dict[str, list[dict]]:
    entries: dict[str, list[dict]] = {k: [] for k in keys}
    for doc in DOCUMENTS:
        if doc.get("machine_id") != machine_no:
            continue
        for clause in doc["clauses"]:
            for key, value in (clause.get("values") or {}).items():
                if key in keys:
                    entries[key].append(
                        {
                            "doc": doc,
                            "clause": clause,
                            "value": value,
                            "priority": PRIORITY.get(doc["type_code"], 0),
                        }
                    )
    for key in entries:
        entries[key].sort(key=lambda e: (-e["priority"], e["doc"]["effective_date"]))
    return entries


def _format_number(value: float, unit: str) -> str:
    text = f"{value:g}"
    return f"{text} {unit}".strip()


def answer_question(machine_no: str, question: str) -> dict:
    machine = MACHINE_BY_NO.get(machine_no)
    if not machine:
        return {
            "ok": False,
            "message": "未找到该产品编号对应的整机档案",
            "question": question,
            "machine": None,
        }
    docs = machine_documents(machine_no)
    if not docs:
        return {
            "ok": True,
            "answer_type": "refusal",
            "question": question,
            "machine": machine,
            "conclusion": f"该整机（{machine_no}）尚未上传合同、技术协议或图纸，无法核对。",
            "items": [],
            "conflicts": [],
            "gaps": ["请先在「知识库文档管理」补充该整机的档案，再发起核对。"],
            "citations": [],
            "confidence": "low",
            "mode": "retrieval+rule",
            "review_status": _review_status(machine_no, question),
        }

    items = detect_items(question)
    if not items:
        return {
            "ok": True,
            "answer_type": "need_object",
            "question": question,
            "machine": machine,
            "conclusion": "没有识别到具体要核对的项，请指明对象（如油漆、吊钩、钢板、电控柜、质保期）。",
            "items": [],
            "conflicts": [],
            "gaps": [],
            "citations": [],
            "confidence": "low",
            "mode": "retrieval+rule",
            "review_status": _review_status(machine_no, question),
        }

    citations: list[dict] = []
    cid_map: dict[str, str] = {}

    def cite(doc: dict, clause: dict) -> str:
        cid = cid_map.get(clause["id"])
        if cid:
            return cid
        cid = f"C{len(citations) + 1}"
        cid_map[clause["id"]] = cid
        citations.append(
            {
                "cid": cid,
                "doc_id": doc["id"],
                "doc_title": doc["title"],
                "doc_no": doc["doc_no"],
                "doc_type": doc["type"],
                "version": doc["version"],
                "effective_date": doc["effective_date"],
                "clause_id": clause["id"],
                "clause_no": clause["clause_no"],
                "section": clause["section"],
                "page": clause["page"],
                "text": clause["text"],
                "verify_status": "待核对",
            }
        )
        return cid

    answer_items = []
    conflicts = []
    gaps = []
    non_std_labels = []

    for item in items:
        if not item["keys"]:
            answer_items.append(
                {
                    "object": item["label"],
                    "verdict": "not_mentioned",
                    "requirement": "未在档案中找到相关规定",
                    "standard_value": "—",
                    "difference": "—",
                    "citations": [],
                    "confidence": "low",
                    "notes": [f"已检索{len(docs)}份档案，未找到{item['label']}相关条款。"],
                }
            )
            gaps.append(f"未在已入库档案中找到关于「{item['label']}」的要求。")
            continue

        entries = _clause_entries(machine_no, item["keys"])
        req_parts, std_parts, diff_parts, notes, item_cites = [], [], [], [], []
        verdicts = []
        item_entries: list[dict] = []

        for key in item["keys"]:
            key_entries = entries.get(key) or []
            if not key_entries:
                continue
            item_entries.extend(key_entries)
            auth = key_entries[0]
            std = STANDARDS.get(key)
            value = auth["value"]
            cid = cite(auth["doc"], auth["clause"])
            item_cites.append(cid)
            req_parts.append(value.get("text") or str(value.get("value")))

            if std:
                std_parts.append(std["display"])
                if std["compare"] == "min":
                    a, s = numeric(value.get("value")), numeric(std["value"])
                    if a is not None and s is not None:
                        if a > s:
                            verdicts.append("non_standard")
                            diff_parts.append(f"+{a - s:g} {std.get('unit', '')}".strip())
                        elif a < s:
                            verdicts.append("non_compliant")
                            diff_parts.append(f"-{s - a:g} {std.get('unit', '')}".strip())
                        else:
                            verdicts.append("standard")
                elif std["compare"] == "max":
                    a, s = numeric(value.get("value")), numeric(std["value"])
                    if a is not None and s is not None:
                        if a < s:
                            verdicts.append("non_standard")
                            diff_parts.append(f"比标准严 {s - a:g} {std.get('unit', '')}".strip())
                        elif a > s:
                            verdicts.append("non_compliant")
                            diff_parts.append(f"比标准宽 {a - s:g} {std.get('unit', '')}".strip())
                        else:
                            verdicts.append("standard")
                else:
                    if str(value.get("value")) == str(std["value"]):
                        verdicts.append("standard")
                    else:
                        verdicts.append("non_standard")
            else:
                verdicts.append("non_standard")

            # 同 key 的其他来源：ECN 覆盖或冲突
            for other in key_entries[1:]:
                if other["doc"]["type_code"] == "ECN":
                    continue
                if str(other["value"].get("value")) != str(value.get("value")):
                    if other["doc"]["type_code"] == "DWG" and auth["doc"]["type_code"] == "TA":
                        cid2 = cite(other["doc"], other["clause"])
                        item_cites.append(cid2)
                        conflicts.append(
                            {
                                "object": std["label"] if std else key,
                                "description": f"{auth['doc']['type']}要求 {value.get('text')}，{other['doc']['type']}写 {other['value'].get('text')}",
                                "citations": [cid, cid2],
                                "suggested": f"按{auth['doc']['type']}执行并请技术确认，同步修订{other['doc']['type']}",
                                "need_confirm": True,
                            }
                        )

            # 变更单覆盖
            ecn_entries = [
                e
                for e in key_entries
                if e["doc"]["type_code"] == "ECN" and e is not auth
            ]
            if auth["doc"]["type_code"] == "ECN":
                origin = [e for e in key_entries if e["doc"]["type_code"] == "TA"]
                if origin:
                    cid2 = cite(origin[0]["doc"], origin[0]["clause"])
                    item_cites.append(cid2)
                    notes.append(
                        f"原{auth['doc']['type']}约定为 {origin[0]['value'].get('text')}，已由变更单（{auth['doc']['effective_date']} 生效）覆盖。"
                    )
            _ = ecn_entries

        # 图纸未标注细节的提示
        if item["key"] == "hook":
            ref = _clause_entries(machine_no, ["hook_ref"]).get("hook_ref") or []
            if ref:
                cid2 = cite(ref[0]["doc"], ref[0]["clause"])
                item_cites.append(cid2)
                notes.append("总图未标注吊钩材质，仅注明「见技术协议第 5 章」，属图纸未细化。")
                gaps.append("总图未标注吊钩材质，仅注明见技术协议，建议设计补图。")

        if not item_cites:
            answer_items.append(
                {
                    "object": item["label"],
                    "verdict": "not_mentioned",
                    "requirement": "未在档案中找到相关规定",
                    "standard_value": "—",
                    "difference": "—",
                    "citations": [],
                    "confidence": "low",
                    "notes": [],
                }
            )
            gaps.append(f"未在已入库档案中找到关于「{item['label']}」的要求。")
            continue

        verdict = (
            "non_compliant"
            if "non_compliant" in verdicts
            else "non_standard"
            if "non_standard" in verdicts
            else "standard"
        )
        if verdict == "non_standard":
            non_std_labels.append(item["label"])

        diff_text = "；".join(dict.fromkeys(diff_parts))
        if not diff_text:
            diff_text = "与标准配置不同" if verdict != "standard" else "与标准一致"

        answer_items.append(
            {
                "object": item["label"],
                "verdict": verdict,
                "requirement": "；".join(dict.fromkeys(req_parts)),
                "standard_value": "；".join(dict.fromkeys(std_parts)) or "—",
                "difference": diff_text,
                "citations": list(dict.fromkeys(item_cites)),
                "confidence": "medium" if conflicts else "high",
                "notes": notes,
            }
        )

    conflict_items = {c["object"] for c in conflicts}
    mentioned = [i for i in answer_items if i["verdict"] != "not_mentioned"]
    if not mentioned:
        conclusion = "未在已入库档案中找到与该问题相关的要求。"
    elif non_std_labels:
        same_short = [i for i in answer_items if i["verdict"] == "non_standard" and i["object"] in non_std_labels]
        reasons = []
        seen = set()
        for i in same_short:
            short = next((x["short"] for x in ITEMS if x["label"] == i["object"]), "")
            if short and short not in seen:
                seen.add(short)
                reasons.append((short, i["object"]))
        grouped: dict[str, list[str]] = {}
        for short, label in reasons:
            grouped.setdefault(short, []).append(label)
        reason_text = "，".join(
            f"{'、'.join(v)}{'均' if len(v) > 1 else ''}{k}" for k, v in grouped.items()
        )
        reason_text = reason_text.replace(" / ", "/")
        if len(non_std_labels) == len(answer_items):
            conclusion = f"{len(non_std_labels)} 项均有非标要求：{reason_text}。"
        else:
            conclusion = f"{'、'.join(non_std_labels)} 有非标要求：{reason_text}；其余项按标准配置执行。"
    else:
        conclusion = "未发现非标要求，各项与公司标准配置一致。"
    if conflicts:
        conclusion = conclusion.rstrip("。") + "；其中存在文档间不一致，需技术确认。"

    # 真实调用 DeepSeek 润色结论；失败或数字不可溯源时回退规则结论
    llm_meta: dict[str, Any] = {}
    mode = "retrieval+rule"
    if mentioned and llm.status()["configured"]:
        facts = {
            "整机": {"产品编号": machine_no, "型号": machine.get("spec"), "客户": machine.get("customer")},
            "问题": question,
            "逐项结论": [
                {
                    "项目": i["object"],
                    "判定": i["verdict"],
                    "客户要求": i["requirement"],
                    "标准配置": i["standard_value"],
                    "差异": i["difference"],
                }
                for i in answer_items
            ],
            "冲突": conflicts,
            "缺口": gaps,
        }
        try:
            result = llm.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是起重机质量档案分析助手。请根据给定事实，写 2-4 句中文结论。"
                            "要求：先给总体判断，再点出最关键的非标差异；如事实中有冲突，必须说明需技术确认；"
                            "只能使用给定事实，不得新增数字或结论；不要输出引用编号，不要使用 Markdown。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": "事实：" + json.dumps(facts, ensure_ascii=False) + "\n请写结论。",
                    },
                ],
                temperature=0.2,
                max_tokens=400,
            )
            candidate = result["content"].strip().strip('"').replace("\n", " ")
            allowed_numbers = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(facts, ensure_ascii=False)))
            used_numbers = set(re.findall(r"\d+(?:\.\d+)?", candidate))
            if candidate and used_numbers.issubset(allowed_numbers):
                conclusion = candidate
                mode = "llm+retrieval"
                llm_meta = {
                    "model": result["model"],
                    "elapsed_ms": result["elapsed_ms"],
                    "usage": result.get("usage", {}),
                }
            else:
                llm_meta = {"error": "模型结论包含未在档案中出现的数字，已回退规则结论"}
        except llm.LLMError as exc:
            llm_meta = {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            llm_meta = {"error": f"调用异常：{exc}"}

    confidence = "low" if not mentioned else "high" if not conflicts and all(i["verdict"] != "not_mentioned" for i in answer_items) else "medium"
    return {
        "ok": True,
        "answer_type": "non_standard_check",
        "question": question,
        "machine": machine,
        "documents": docs,
        "conclusion": conclusion,
        "items": answer_items,
        "conflicts": conflicts,
        "gaps": gaps,
        "citations": citations,
        "confidence": confidence,
        "mode": mode,
        "llm": llm_meta,
        "review_status": _review_status(machine_no, question),
        "conflict_objects": sorted(conflict_items),
    }


# ---------------------------------------------------------------------------
# 不符合项三查
# ---------------------------------------------------------------------------

CHECK_ITEMS = {
    "paint_dft": {"label": "面漆干膜厚度", "unit": "μm", "compare": "min"},
    "steel_flange": {"label": "主梁上翼缘板厚", "unit": "mm", "compare": "min"},
    "paint_salt": {"label": "耐盐雾", "unit": "h", "compare": "min"},
}


def check_nonconformance(machine_no: str, item_code: str, measured: float) -> dict:
    machine = MACHINE_BY_NO.get(machine_no)
    item = CHECK_ITEMS.get(item_code)
    std = STANDARDS.get(item_code)
    if not machine or not item or not std:
        return {"ok": False, "message": "参数不完整或不支持该检查项"}

    entries = _clause_entries(machine_no, [item_code]).get(item_code, [])
    by_type: dict[str, dict] = {}
    for e in entries:
        by_type.setdefault(e["doc"]["type_code"], e)

    ta = by_type.get("TA")
    dwg = by_type.get("DWG")
    drawing_value = numeric(dwg["value"]["value"]) if dwg else None
    agreement_value = numeric(ta["value"]["value"]) if ta else None
    standard_value = numeric(std["value"])

    def clause_ref(entry: dict | None) -> dict | None:
        if not entry:
            return None
        return {
            "doc_title": entry["doc"]["title"],
            "version": entry["doc"]["version"],
            "doc_no": entry["doc"]["doc_no"],
            "clause_no": entry["clause"]["clause_no"],
            "page": entry["clause"]["page"],
            "text": entry["clause"]["text"],
            "doc_id": entry["doc"]["id"],
            "clause_id": entry["clause"]["id"],
            "value": entry["value"]["text"],
        }

    pass_drawing = drawing_value is None or measured >= drawing_value
    pass_agreement = agreement_value is None or measured >= agreement_value
    pass_standard = standard_value is None or measured >= standard_value

    if pass_drawing and pass_agreement and pass_standard:
        verdict = "合格"
        reason = "实测值满足图纸、技术协议及标准配置要求。"
        severity = "ok"
    elif (not pass_agreement) and pass_drawing:
        verdict = "不符合技术协议；符合总图"
        reason = "图纸未同步技术协议的非标要求，属「非标未传递到图纸」。"
        severity = "warn"
    elif (not pass_drawing) and (not pass_agreement):
        verdict = "不合格"
        reason = "实测值同时低于图纸与技术协议要求。"
        severity = "bad"
    else:
        verdict = "不符合总图；符合技术协议"
        reason = "图纸要求高于技术协议，需核对图纸版本。"
        severity = "warn"

    suggestions = [
        "请技术确认膜厚要求，并按技术协议补图" if not pass_agreement else "按图纸要求返工并复检",
        "返工后按协议要求复检并留存膜厚记录",
        "如需让步接收，须取得客户书面同意",
    ]

    return {
        "ok": True,
        "machine": machine,
        "item": {**item, "code": item_code},
        "measured": measured,
        "verdict": verdict,
        "severity": severity,
        "reason": reason,
        "columns": {
            "drawing": {"value": drawing_value, "display": f"{drawing_value:g} {item['unit']}" if drawing_value is not None else "—", "source": clause_ref(dwg)},
            "agreement": {"value": agreement_value, "display": f"{agreement_value:g} {item['unit']}" if agreement_value is not None else "—", "source": clause_ref(ta)},
            "standard": {"value": standard_value, "display": std["display"], "source": None},
        },
        "checks": {"drawing": pass_drawing, "agreement": pass_agreement, "standard": pass_standard},
        "suggestions": suggestions,
        "review_status": "待核对",
    }


# ---------------------------------------------------------------------------
# 预警与驾驶舱
# ---------------------------------------------------------------------------

def _state_path() -> Path:
    return DATA_DIR / "state.json"


def load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {"alerts": {}, "reviews": []}


def save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _review_status(machine_no: str, question: str) -> str:
    state = load_state()
    for review in reversed(state.get("reviews", [])):
        if review.get("machine_id") == machine_no and review.get("question") == question:
            return review.get("status", "待核对")
    return "待核对"


ALERT_CONFIG_PATH = DATA_DIR / "alert_config.json"

FAULT_TYPES = ["其他类", "机械类", "电气类"]
ATTRIBUTIONS = [
    "制作问题",
    "发货问题",
    "外协问题",
    "客户（质保内）",
    "客户（质保外）",
    "设计问题",
    "技术支持",
    "公司自营",
    "其他",
]

DEFAULT_ALERT_RULES = [
    {
        "id": "paint_make",
        "name": "涂装制作问题聚集",
        "fault_type": "其他类",
        "attribution": "制作问题",
        "manufacturer": "",
        "component": "涂装层",
        "remark": "",
        "window_days": 120,
        "threshold": 3,
        "level": "橙",
        "enabled": True,
    },
    {
        "id": "bearing_make",
        "name": "卷筒轴承座装配问题",
        "fault_type": "机械类",
        "attribution": "制作问题",
        "manufacturer": "",
        "component": "卷筒轴承座",
        "remark": "",
        "window_days": 365,
        "threshold": 3,
        "level": "黄",
        "enabled": True,
    },
    {
        "id": "motor_outsource",
        "name": "电机外协问题",
        "fault_type": "电气类",
        "attribution": "外协问题",
        "manufacturer": "河南XX电机",
        "component": "起升电机",
        "remark": "",
        "window_days": 365,
        "threshold": 2,
        "level": "橙",
        "enabled": True,
    },
    {
        "id": "wheel_design",
        "name": "车轮设计问题重复",
        "fault_type": "机械类",
        "attribution": "设计问题",
        "manufacturer": "",
        "component": "车轮",
        "remark": "",
        "window_days": 540,
        "threshold": 2,
        "level": "黄",
        "enabled": True,
    },
    {
        "id": "paint_delivery",
        "name": "涂装发货磕碰",
        "fault_type": "其他类",
        "attribution": "发货问题",
        "manufacturer": "",
        "component": "涂装层",
        "remark": "",
        "window_days": 180,
        "threshold": 2,
        "level": "提示",
        "enabled": True,
    },
]

ALERT_PLAYBOOK = {
    ("制作问题", "涂装层"): (
        "前处理、除锈后待涂时间与雨季湿度控制不稳定，补漆未按色板和遍数执行。",
        "核查涂装班组前处理与待涂时间记录；雨季增加除湿；补漆执行色板比对与遍数确认。",
    ),
    ("制作问题", "卷筒轴承座"): (
        "轴承座同轴度与装配找正不到位，装配后未复测。",
        "复测轴承座同轴度并核查装配工艺；补齐整机装配检验记录。",
    ),
    ("制作问题", "主梁"): (
        "焊接工艺执行不到位，预热与层间温度未按 WPS 控制。",
        "核查焊工持证与 WPS 执行记录，重要焊缝增加过程见证。",
    ),
    ("外协问题", "起升电机"): (
        "外协电机绝缘与防护等级不满足项目要求，来料检验未覆盖。",
        "约谈电机供应商，加严绝缘耐压与防护等级复验，按批次留样。",
    ),
    ("外协问题", "起升减速机"): (
        "外协件油封批次质量不稳定。",
        "要求供应商提供批次复检报告，关键密封件增加入库抽检。",
    ),
    ("外协问题", "主梁"): (
        "钢板负偏差与材质证明不符。",
        "按炉批号加严来料复验，超差批次整批退换。",
    ),
    ("设计问题", "车轮"): (
        "轨距与车轮同位差公差标注超出工艺能力，整改后图纸未同步。",
        "复核该设计人员图纸中的轨距与同位差标注，整改后强制版本校验。",
    ),
    ("发货问题", "涂装层"): (
        "包装固定与运输防护不到位，端梁等外露部位易磕碰。",
        "复核包装方案，增加软质护角与固定点，发运前拍照留证。",
    ),
    ("技术支持", ""): (
        "指导口径、参数表版本与现场机型不一致。",
        "统一参数表版本并按机型归档，远程指导前先核对整机编号。",
    ),
    ("公司自营", ""): (
        "安装调试未按调试大纲执行，关键间隙未复测。",
        "复核安装调试记录并复训，关键项增加签字确认。",
    ),
    ("其他", ""): (
        "流程或标识环节存在疏漏。",
        "复核相关流程与模板，增加打印前复核点。",
    ),
}

FALLBACK_PLAYBOOK = {
    "制作问题": ("制作过程控制不稳定。", "核查责任班组的作业记录与过程检验，确认共性工序问题。"),
    "外协问题": ("外协件质量存在波动。", "约谈供应商并加严来料复验。"),
    "设计问题": ("图纸或选型存在共性缺陷。", "复核相关图纸与设计校审记录。"),
    "发货问题": ("包装或运输防护不足。", "复核包装方案与运输固定方式。"),
    "客户（质保内）": ("客户使用工况超出约定。", "现场复核使用方式并书面告知额定工况。"),
    "客户（质保外）": ("设备老化或维保缺失。", "提供有偿维修与维保建议。"),
    "技术支持": ("指导口径或资料版本不一致。", "统一参数表与指导口径。"),
    "公司自营": ("安装调试未按大纲执行。", "复核安装调试记录并复训。"),
    "其他": ("流程或标识环节存在疏漏。", "复核相关流程并补充检查点。"),
}

LEVEL_RANK = {"红": 0, "橙": 1, "黄": 2, "提示": 3}


def _condition_text(rule: dict) -> str:
    parts = []
    if rule.get("fault_type"):
        parts.append(f"故障类型={rule['fault_type']}")
    if rule.get("attribution"):
        parts.append(f"原因归属={rule['attribution']}")
    if rule.get("manufacturer"):
        parts.append(f"厂家={rule['manufacturer']}")
    if rule.get("component"):
        parts.append(f"部件含「{rule['component']}」")
    if rule.get("remark"):
        parts.append(f"备注关键词={rule['remark']}")
    return "，".join(parts) if parts else "全部问题"


def load_alert_config() -> dict:
    if not ALERT_CONFIG_PATH.exists():
        config = {"rules": json.loads(json.dumps(DEFAULT_ALERT_RULES))}
        save_alert_config(config)
        return config
    try:
        data = json.loads(ALERT_CONFIG_PATH.read_text(encoding="utf-8"))
        rules = data.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("rules empty")
        if any("fault_type" not in rule or "attribution" not in rule for rule in rules):
            raise ValueError("legacy rules")
        return data
    except Exception:
        config = {"rules": json.loads(json.dumps(DEFAULT_ALERT_RULES))}
        save_alert_config(config)
        return config


def save_alert_config(config: dict) -> dict:
    rules = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(config.get("rules", [])):
        fault_type = (raw.get("fault_type") or "").strip()
        attribution = (raw.get("attribution") or "").strip()
        level = (raw.get("level") or "").strip()
        if fault_type and fault_type not in FAULT_TYPES:
            raise ValueError(f"不支持的故障类型：{fault_type}")
        if attribution and attribution not in ATTRIBUTIONS:
            raise ValueError(f"不支持的原因归属：{attribution}")
        if level not in LEVEL_RANK:
            raise ValueError(f"不支持的预警等级：{level}")
        try:
            window_days = int(raw.get("window_days"))
            threshold = int(raw.get("threshold"))
        except (TypeError, ValueError) as exc:
            raise ValueError("时间窗口和次数阈值必须是整数") from exc
        if not 1 <= window_days <= 730:
            raise ValueError("时间窗口需在 1～730 天之间")
        if not 1 <= threshold <= 50:
            raise ValueError("次数阈值需在 1～50 之间")
        rule_id = (raw.get("id") or f"rule_{index + 1}").strip()
        while rule_id in seen_ids:
            rule_id = f"{rule_id}_x"
        seen_ids.add(rule_id)
        rules.append(
            {
                "id": rule_id,
                "name": (raw.get("name") or "").strip() or f"规则 {index + 1}",
                "fault_type": fault_type,
                "attribution": attribution,
                "manufacturer": (raw.get("manufacturer") or "").strip(),
                "component": (raw.get("component") or "").strip(),
                "remark": (raw.get("remark") or "").strip()[:200],
                "window_days": window_days,
                "threshold": threshold,
                "level": level,
                "enabled": bool(raw.get("enabled", True)),
            }
        )
    if not rules:
        raise ValueError("至少保留一条预警规则")
    payload = {"rules": rules}
    ALERT_CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _match_issue(issue: dict, rule: dict) -> bool:
    if rule.get("fault_type") and issue.get("fault_type") != rule["fault_type"]:
        return False
    if rule.get("attribution") and issue.get("attribution_raw") != rule["attribution"]:
        return False
    if rule.get("manufacturer") and (issue.get("supplier") or "") != rule["manufacturer"]:
        return False
    component = (rule.get("component") or "").strip()
    if component and component not in (issue.get("component") or ""):
        return False
    remark = (rule.get("remark") or "").strip()
    if remark:
        keywords = [k for k in re.split(r"[\s,，、;；]+", remark) if k]
        text = " ".join(
            str(issue.get(key) or "")
            for key in ("phenomenon", "description", "cause_detail", "handling")
        )
        if keywords and not any(keyword in text for keyword in keywords):
            return False
    return True


def _alert_texts(rule: dict, evidence: list[dict]) -> tuple[str, str, str]:
    components = Counter(issue["component"] for issue in evidence)
    modes = Counter(fault_mode(issue["phenomenon"]) for issue in evidence)
    top = components.most_common(2)
    pattern = "、".join(f"{name} {count} 起" for name, count in top)
    if modes:
        pattern += "（" + "、".join(name for name, _ in modes.most_common(3)) + "）"

    key = (rule.get("attribution") or "", rule.get("component") or "")
    cause, action = ALERT_PLAYBOOK.get(key) or FALLBACK_PLAYBOOK.get(
        rule.get("attribution") or "",
        ("同类问题在时间窗口内集中出现。", "复核相关记录，确认共性原因后制定整改措施。"),
    )
    possible = (
        f"近 {rule['window_days']} 天，满足「{_condition_text(rule)}」的问题 "
        f"{len(evidence)} 起，涉及 {len({i['machine_id'] for i in evidence})} 台整机。{cause}"
    )
    return pattern, possible, action


def _compute_alerts() -> list[dict]:
    config = load_alert_config()
    state = load_state()
    overrides = state.get("alerts", {})
    alerts: list[dict] = []
    for rule in config["rules"]:
        if not rule.get("enabled"):
            continue
        start = date.fromordinal(TODAY.toordinal() - int(rule["window_days"]))
        evidence = [
            issue
            for issue in ISSUES
            if parse_date(issue["date"]) >= start and _match_issue(issue, rule)
        ]
        if len(evidence) < int(rule["threshold"]):
            continue
        evidence.sort(key=lambda issue: issue["date"], reverse=True)
        pattern, possible, action = _alert_texts(rule, evidence)
        override = overrides.get(rule["id"], {})
        status = override.get("status") or ("提示" if rule["level"] == "提示" else "待确认")
        alerts.append(
            {
                "alert_key": rule["id"],
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "level": rule["level"],
                "fault_type": rule["fault_type"],
                "attribution": rule["attribution"],
                "manufacturer": rule["manufacturer"],
                "component": rule["component"],
                "remark": rule["remark"],
                "condition_text": _condition_text(rule),
                "window_days": int(rule["window_days"]),
                "threshold": int(rule["threshold"]),
                "pattern": pattern,
                "metric": {
                    "n": len(evidence),
                    "machine_count": len({i["machine_id"] for i in evidence}),
                    "customer_count": len({i["customer"] for i in evidence}),
                },
                "evidence": [issue["id"] for issue in evidence],
                "machines": sorted({i["machine_id"] for i in evidence}),
                "customers": sorted({i["customer"] for i in evidence}),
                "teams": sorted({i["team"] for i in evidence if i["team"]}),
                "designers": sorted({i["designer"] for i in evidence if i["designer"]}),
                "suppliers": sorted({i["supplier"] for i in evidence if i["supplier"]}),
                "possible_cause": possible,
                "suggested_action": action,
                "status": status,
                "owner": override.get("owner", ""),
                "reason": override.get("reason", ""),
                "note": override.get("note", ""),
                "ai_suggestion": override.get("ai_suggestion", ""),
                "ai_generated_at": override.get("ai_generated_at", ""),
                "ai_model": override.get("ai_model", ""),
                "created_at": "2026-11-09",
                "closed_at": override.get("closed_at"),
            }
        )
    alerts.sort(key=lambda alert: (LEVEL_RANK.get(alert["level"], 9), -alert["metric"]["n"], alert["rule_name"]))
    for index, alert in enumerate(alerts, start=1):
        alert["alert_no"] = f"QA-{TODAY.strftime('%Y%m')}-{index:04d}"
    return alerts


def list_alerts() -> list[dict]:
    alerts = _compute_alerts()
    for alert in alerts:
        alert["evidence_detail"] = [
            issue_summary(ISSUE_BY_ID[i]) for i in alert["evidence"] if i in ISSUE_BY_ID
        ]
    status_rank = {"待确认": 0, "已确认": 1, "整改中": 2, "提示": 3}

    def sort_key(alert: dict) -> tuple:
        rank = 4 if alert["status"].startswith("已关闭") else status_rank.get(alert["status"], 3)
        return (rank, LEVEL_RANK.get(alert["level"], 9), -alert["metric"]["n"])

    alerts.sort(key=sort_key)
    return alerts


def update_alert(alert_no: str, action: str, reason: str = "", owner: str = "质量工程师") -> dict:
    mapping = {"confirm": "已确认", "dismiss": "已关闭（误报）", "rectify": "整改中"}
    status = mapping.get(action)
    if not status:
        return {"ok": False, "message": "不支持的操作"}
    target = next((alert for alert in _compute_alerts() if alert["alert_no"] == alert_no), None)
    if not target:
        return {"ok": False, "message": "预警已变化，请刷新后重试"}
    state = load_state()
    entry = state.setdefault("alerts", {}).setdefault(target["alert_key"], {})
    entry.update(
        {
            "status": status,
            "reason": reason,
            "owner": owner,
            "closed_at": TODAY.isoformat() if action == "dismiss" else None,
        }
    )
    save_state(state)
    return {"ok": True, "status": status, "alert_key": target["alert_key"]}


def _find_computed_alert(alert_no: str) -> dict | None:
    return next((alert for alert in _compute_alerts() if alert["alert_no"] == alert_no), None)


def save_alert_note(alert_no: str, note: str) -> dict:
    target = _find_computed_alert(alert_no)
    if not target:
        return {"ok": False, "message": "预警已变化，请刷新后重试"}
    state = load_state()
    entry = state.setdefault("alerts", {}).setdefault(target["alert_key"], {})
    entry["note"] = (note or "").strip()[:500]
    save_state(state)
    return {"ok": True, "note": entry["note"]}


ALERT_SUGGEST_SYSTEM = """你是起重机质量工程师。根据预警规则和证据问题，给出 3～4 条具体、可执行的改进建议。
要求：只依据给定事实，不编造数字；每条一句话；用中文；不要 Markdown 标题；总字数不超过 250 字。"""


def generate_alert_suggestion(alert_no: str) -> dict:
    target = _find_computed_alert(alert_no)
    if not target:
        return {"ok": False, "message": "预警已变化，请刷新后重试"}

    evidence = [
        issue_summary(ISSUE_BY_ID[i]) for i in target["evidence"] if i in ISSUE_BY_ID
    ]
    fallback = target["suggested_action"]
    info = llm.status()
    if not info["configured"]:
        return {
            "ok": True,
            "suggestion": fallback,
            "mode": "rule",
            "model": "",
            "error": "未配置 DEEPSEEK_API_KEY，当前为规则建议",
        }

    facts = {
        "规则": target["rule_name"],
        "条件": target["condition_text"],
        "窗口天数": target["window_days"],
        "阈值": target["threshold"],
        "实际命中": target["metric"]["n"],
        "涉及整机": target["machines"],
        "涉及客户": target["customers"],
        "证据": [
            {
                "报修单号": item["repair_no"],
                "日期": item["date"],
                "部件": item["component"],
                "现象": item["phenomenon"],
                "原因归属": item["attribution_raw"] or item["cause"],
                "根因": item["cause_detail"],
                "处置": item["handling"],
                "责任对象": " / ".join(
                    x for x in (item["team"], item["designer"], item["supplier"]) if x
                ),
            }
            for item in evidence
        ],
    }
    try:
        result = llm.chat(
            [
                {"role": "system", "content": ALERT_SUGGEST_SYSTEM},
                {
                    "role": "user",
                    "content": "事实："
                    + json.dumps(facts, ensure_ascii=False)
                    + "\n请给改进建议。",
                },
            ],
            temperature=0.3,
            max_tokens=700,
        )
        text = result["content"].strip()
        if not text:
            raise llm.LLMError("模型返回为空")
        state = load_state()
        entry = state.setdefault("alerts", {}).setdefault(target["alert_key"], {})
        entry["ai_suggestion"] = text
        entry["ai_generated_at"] = TODAY.isoformat()
        entry["ai_model"] = result["model"]
        save_state(state)
        return {
            "ok": True,
            "suggestion": text,
            "mode": "llm",
            "model": result["model"],
            "elapsed_ms": result["elapsed_ms"],
            "error": "",
        }
    except llm.LLMError as exc:
        return {
            "ok": True,
            "suggestion": fallback,
            "mode": "rule",
            "model": info["model"],
            "error": str(exc),
        }


def add_review(machine_no: str, question: str, action: str, comment: str = "") -> dict:
    state = load_state()
    status = "已确认" if action == "confirm" else "有异议"
    state.setdefault("reviews", []).append(
        {
            "machine_id": machine_no,
            "question": question,
            "action": action,
            "status": status,
            "comment": comment,
            "reviewer": "质量工程师",
            "created_at": "2026-11-10",
        }
    )
    save_state(state)
    return {"ok": True, "status": status}


# ---------------------------------------------------------------------------
# 问题库问答（DeepSeek 整理全部问题）
# ---------------------------------------------------------------------------

ISSUE_ASK_SYSTEM = """你是起重机售后质量分析师。用户会问关于质量问题库的问题。
你只能依据给定「问题清单」回答，禁止编造清单之外的问题、数字或结论。
输出必须是 JSON，格式：{"answer": "中文回答，最多 6 条分点，引用具体问题编号", "related": ["QI-...", "..."]}
related 只能从清单中的问题编号里选，最多 6 个。"""


def _rule_issue_summary(scope: list[dict]) -> str:
    causes = Counter(i["cause"] for i in scope)
    components = Counter(i["component"] for i in scope)
    open_items = [i for i in scope if i["status"] != "已关闭"]
    lines = [f"当前问题库共 {len(scope)} 条问题。"]
    if causes:
        lines.append("按原因：" + "、".join(f"{name} {count} 条" for name, count in causes.most_common(4)) + "。")
    if components:
        lines.append(
            "按部件：" + "、".join(f"{name} {count} 条" for name, count in components.most_common(4)) + "。"
        )
    if open_items:
        latest = sorted(open_items, key=lambda i: i["date"], reverse=True)
        lines.append(
            "未闭环：" + "；".join(f"{i['issue_no']}（{i['machine_id']} {i['phenomenon']}）" for i in latest[:4]) + "。"
        )
    else:
        lines.append("当前没有未闭环问题。")
    return "\n".join(lines)


def answer_issue_question(question: str, machine_id: str = "") -> dict:
    scope = [i for i in ISSUES if not machine_id or i["machine_id"] == machine_id]
    if not scope:
        return {
            "ok": True,
            "question": question,
            "answer": "该范围内没有问题记录。",
            "related": [],
            "mode": "rule",
            "issue_count": 0,
        }

    payload = [
        {
            "编号": i["issue_no"],
            "日期": i["date"],
            "客户": i["customer"],
            "整机": i["machine_id"],
            "部件": i["component"],
            "现象": i["phenomenon"],
            "原因类型": i["cause"],
            "根因": i["cause_detail"],
            "处置": i["handling"],
            "状态": i["status"],
            "责任对象": " / ".join(x for x in (i["team"], i["designer"], i["supplier"]) if x),
        }
        for i in sorted(scope, key=lambda i: i["date"], reverse=True)
    ]

    fallback_related = [
        i["issue_no"]
        for i in sorted(
            [x for x in scope if x["status"] != "已关闭"] or scope,
            key=lambda x: x["date"],
            reverse=True,
        )[:4]
    ]
    fallback = _rule_issue_summary(scope)

    info = llm.status()
    if not info["configured"]:
        return {
            "ok": True,
            "question": question,
            "answer": fallback,
            "related": [issue_summary(ISSUE_BY_NO[no]) for no in fallback_related if no in ISSUE_BY_NO],
            "mode": "rule",
            "model": "",
            "elapsed_ms": 0,
            "issue_count": len(scope),
            "error": "未配置 DEEPSEEK_API_KEY，当前为规则摘要",
        }

    try:
        result = llm.chat(
            [
                {"role": "system", "content": ISSUE_ASK_SYSTEM},
                {
                    "role": "user",
                    "content": f"今天是 {TODAY.isoformat()}。问题清单：\n"
                    + json.dumps(payload, ensure_ascii=False)
                    + f"\n\n用户问题：{question}",
                },
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        parsed = llm.parse_json_answer(result["content"])
        if parsed and isinstance(parsed.get("answer"), str):
            answer = parsed["answer"].strip()
            raw_related = parsed.get("related") or []
        else:
            answer = result["content"].strip()
            raw_related = []
        valid_nos = {i["issue_no"] for i in scope}
        related = [no for no in raw_related if isinstance(no, str) and no in valid_nos][:6]
        return {
            "ok": True,
            "question": question,
            "answer": answer,
            "related": [issue_summary(ISSUE_BY_NO[no]) for no in related],
            "mode": "llm",
            "model": result["model"],
            "elapsed_ms": result["elapsed_ms"],
            "usage": result.get("usage", {}),
            "issue_count": len(scope),
            "error": "",
        }
    except llm.LLMError as exc:
        return {
            "ok": True,
            "question": question,
            "answer": fallback,
            "related": [issue_summary(ISSUE_BY_NO[no]) for no in fallback_related if no in ISSUE_BY_NO],
            "mode": "rule",
            "model": info["model"],
            "elapsed_ms": 0,
            "issue_count": len(scope),
            "error": str(exc),
        }





def dashboard() -> dict:
    open_issues = [i for i in ISSUES if i["status"] != "已关闭"]
    closed = [i for i in ISSUES if i.get("closed_at")]
    avg_days = round(sum((parse_date(i["closed_at"]) - parse_date(i["date"])).days for i in closed) / max(len(closed), 1), 1)
    alerts = list_alerts()
    pending_alerts = [a for a in alerts if a["status"] == "待确认"]

    months = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    trend = []
    for m in months:
        trend.append({"month": m, "count": len([i for i in ISSUES if i["date"][:7] == m])})

    causes = {}
    for i in ISSUES:
        causes[i["cause"]] = causes.get(i["cause"], 0) + 1
    by_cause = [{"name": k, "count": v} for k, v in sorted(causes.items(), key=lambda x: -x[1])]

    comps = {}
    for i in ISSUES:
        comps[i["component"]] = comps.get(i["component"], 0) + 1
    top_components = [{"name": k, "count": v} for k, v in sorted(comps.items(), key=lambda x: -x[1])[:5]]

    completeness = []
    for issue in ISSUES[:6]:
        chain = quality_chain(issue)
        completeness.append(chain["completeness"] / chain["total"])
    avg_completeness = round(sum(completeness) / max(len(completeness), 1) * 100)

    clause_total = sum(len(d["clauses"]) for d in DOCUMENTS)
    return {
        "kpis": {
            "issue_total": len(ISSUES),
            "issue_open": len(open_issues),
            "alert_pending": len(pending_alerts),
            "avg_close_days": avg_days,
            "chain_completeness": avg_completeness,
            "clause_total": clause_total,
            "machine_total": len(MACHINES),
        },
        "trend": trend,
        "by_cause": by_cause,
        "top_components": top_components,
        "recent_issues": [issue_summary(i) for i in sorted(ISSUES, key=lambda x: x["date"], reverse=True)[:5]],
        "alerts": alerts[:3],
        "today": TODAY.isoformat(),
    }


def reset_demo() -> dict:
    save_state({"alerts": {}, "reviews": []})
    return {"ok": True, "message": "演示状态已重置"}


def machine_detail(machine_no: str) -> dict | None:
    machine = MACHINE_BY_NO.get(machine_no)
    if not machine:
        return None
    return {
        "machine": machine,
        "documents": machine_documents(machine_no),
        "issues": list_issues(machine_id=machine_no),
        "inspections": [x for x in INSPECTIONS if x["machine_id"] == machine_no],
        "traces": [t for t in TRACES if t["machine_id"] == machine_no],
    }
