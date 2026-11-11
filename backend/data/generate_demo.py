"""生成售后问题质量库演示数据。

- 保留现有 26 条有完整质量字段的记录（用于 AI 研判、档案关联、预警）
- 追加 74 条日常报修记录，补齐截图里的报修单字段
- 固定随机种子，重复运行结果一致
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).parent
rng = random.Random(20261110)

MACHINES = json.loads((DATA / "machines.json").read_text(encoding="utf-8"))
_loaded_issues = json.loads((DATA / "issues.json").read_text(encoding="utf-8"))
# 只保留最初 26 条手工维护的记录，保证脚本可重复运行不重复追加
ISSUES = [issue for issue in _loaded_issues if issue["id"] <= 26]

NEW_MACHINES = [
    {
        "product_no": "QD-2024-0912",
        "model_code": "QD",
        "model_name": "电动双梁桥式起重机",
        "spec": "QD10t-22.5m A5",
        "customer": "新乡恒达新能源装备有限公司",
        "contract_no": "HT-2024-0912",
        "manufacture_date": "2024-09-12",
        "delivery_date": "2024-09-28",
        "warranty_months": 12,
        "warranty_end": "2025-09-12",
        "serial_no": "240912-01",
        "designer": "王工",
        "team": "装配一班",
        "workshop": "总装车间",
        "usage_env": "新能源车间，粉尘",
    },
    {
        "product_no": "MH-2022-0318",
        "model_code": "MH",
        "model_name": "门式起重机",
        "spec": "MH16t-24m A3",
        "customer": "山西晟远能源科技有限公司",
        "contract_no": "HT-2022-0318",
        "manufacture_date": "2022-03-18",
        "delivery_date": "2022-04-02",
        "warranty_months": 12,
        "warranty_end": "2023-03-18",
        "serial_no": "220318-02",
        "designer": "李工",
        "team": "焊接一班",
        "workshop": "结构件车间",
        "usage_env": "室外料场，温差大",
    },
    {
        "product_no": "CD1-2025-0106",
        "model_code": "CD1",
        "model_name": "电动葫芦",
        "spec": "CD1-3t-12m",
        "customer": "中原磨料磨具有限公司",
        "contract_no": "HT-2025-0106",
        "manufacture_date": "2025-01-06",
        "delivery_date": "2025-01-18",
        "warranty_months": 12,
        "warranty_end": "2026-01-06",
        "serial_no": "250106-03",
        "designer": "赵工",
        "team": "装配二班",
        "workshop": "总装车间",
        "usage_env": "机加工车间",
    },
    {
        "product_no": "QD-2024-1120",
        "model_code": "QD",
        "model_name": "电动双梁桥式起重机",
        "spec": "QD32/5t-19.5m A5",
        "customer": "大连恒舟船舶工程有限公司",
        "contract_no": "HT-2024-1120",
        "manufacture_date": "2024-11-20",
        "delivery_date": "2024-12-08",
        "warranty_months": 12,
        "warranty_end": "2025-11-20",
        "serial_no": "241120-01",
        "designer": "王工",
        "team": "装配一班",
        "workshop": "总装车间",
        "usage_env": "船体车间，盐雾",
    },
    {
        "product_no": "BZ-2023-0825",
        "model_code": "BZ",
        "model_name": "悬臂起重机",
        "spec": "BZ5t-5m",
        "customer": "河北冀镁新材料有限公司",
        "contract_no": "HT-2023-0825",
        "manufacture_date": "2023-08-25",
        "delivery_date": "2023-09-06",
        "warranty_months": 12,
        "warranty_end": "2024-08-25",
        "serial_no": "230825-04",
        "designer": "赵工",
        "team": "装配二班",
        "workshop": "总装车间",
        "usage_env": "镁合金车间，高温",
    },
    {
        "product_no": "LD5-2025-0603",
        "model_code": "LD5",
        "model_name": "电动单梁起重机",
        "spec": "LD5-16.5 A4",
        "customer": "山东鲁腾机械装备有限公司",
        "contract_no": "HT-2025-0603",
        "manufacture_date": "2025-06-03",
        "delivery_date": "2025-06-18",
        "warranty_months": 12,
        "warranty_end": "2026-06-03",
        "serial_no": "250603-02",
        "designer": "王工",
        "team": "装配一班",
        "workshop": "总装车间",
        "usage_env": "重型机加工车间",
    },
]

existing_machine_nos = {m["product_no"] for m in MACHINES}
for machine in NEW_MACHINES:
    if machine["product_no"] in existing_machine_nos:
        target = next(m for m in MACHINES if m["product_no"] == machine["product_no"])
        target.update(machine)
    else:
        MACHINES.append(machine)

CONTACTS = {
    "河南华丰食品有限公司": ("张明远", "13800000001"),
    "浙江华远起重设备有限公司": ("李国强", "13800000002"),
    "郑州中原机械制造有限公司": ("王海燕", "13800000003"),
    "洛阳建材科技有限公司": ("刘志远", "13800000004"),
    "新乡恒达新能源装备有限公司": ("陈晓东", "13800000005"),
    "山西晟远能源科技有限公司": ("杨丽娟", "13800000006"),
    "中原磨料磨具有限公司": ("赵鹏", "13800000007"),
    "大连恒舟船舶工程有限公司": ("黄敏", "13800000008"),
    "河北冀镁新材料有限公司": ("周涛", "13800000009"),
    "山东鲁腾机械装备有限公司": ("吴静", "13800000010"),
}

DEPARTMENTS = ["售后部", "质量部", "客服部", "销售部"]
CHANNELS = [("云上卫4", 60), ("oa", 25), ("电话", 10), ("微信", 5)]
SALES_STATUS = [
    ("待派工", 8),
    ("已派工-待完工", 35),
    ("已完工-待评价", 25),
    ("已完工-已评价", 30),
    ("已取消", 2),
]


def weighted(items):
    total = sum(weight for _, weight in items)
    pick = rng.uniform(0, total)
    upto = 0
    for value, weight in items:
        upto += weight
        if pick <= upto:
            return value
    return items[-1][0]


def responsibility_for(cause: str) -> str:
    if cause in ("使用",):
        return "无责"
    if cause == "待归因":
        return "未开始"
    if cause in ("制作", "设计", "外协", "发货", "安装"):
        return "有责"
    if cause in ("技术支持",):
        return "无责"
    return "待定"


def channel_for(source: str) -> str:
    if source == "售后服务平台":
        return "云上卫4"
    return "oa"


def phone() -> str:
    return "13" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def repair_no(day: str, used: set[str]) -> str:
    compact = day.replace("-", "")
    while True:
        number = f"FN{compact}{rng.randint(100, 999)}"
        if number not in used:
            used.add(number)
            return number


def enrich(issue: dict, used_repairs: set[str], used_issues: set[str]) -> dict:
    day = issue["date"]
    issue["repair_no"] = repair_no(day, used_repairs)
    issue["after_sales_status"] = (
        "已派工-待完工" if issue["status"] in ("研判中", "整改中") else "已完工-已评价"
    )
    issue["responsibility_status"] = responsibility_for(issue["cause"])
    issue["source_channel"] = channel_for(issue["source"])
    issue["entry_method"] = "订单"
    issue["after_sales_order"] = (
        f"29000386{issue['id']:02d}-10" if issue["id"] in (7, 17, 19) else ""
    )
    contact, mobile = CONTACTS.get(issue["customer"], ("张伟", phone()))
    issue["contact_name"] = contact
    issue["contact_phone"] = mobile
    issue["department"] = "售后部" if issue["source"] == "售后服务平台" else "质量部"
    issue["quality_status"] = issue["status"]
    issue["report_time"] = f"{8 + issue['id'] % 10:02d}:{(issue['id'] * 7) % 60:02d}"
    return issue


used_repairs: set[str] = set()
for issue in ISSUES:
    enrich(issue, used_repairs, set())

used_repairs = {issue["repair_no"] for issue in ISSUES}
used_issues = {issue["issue_no"] for issue in ISSUES}

FILLER_TEMPLATES = {
    "钢丝绳": ("钢丝绳断丝超标", "机械类", "检查发现钢丝绳一个捻距内断丝数超过报废标准。"),
    "制动器": ("制动器异响", "机械类", "制动器松闸时有异响，制动力矩正常。"),
    "限位开关": ("上升限位失效", "电气类", "上升限位开关动作不灵敏，需更换。"),
    "电控柜": ("接触器故障", "电气类", "电控柜接触器吸合不稳定，偶发不动作。"),
    "缓冲器": ("缓冲器老化", "机械类", "大车缓冲器聚氨酯老化开裂。"),
    "遥控器": ("遥控器失灵", "电气类", "遥控器按键偶发失灵，电池正常。"),
    "吊钩组": ("吊钩闭锁卡滞", "机械类", "吊钩闭锁装置弹簧卡滞，开闭不灵活。"),
    "主梁": ("油漆局部锈点", "其他类", "主梁走台下方出现局部锈点。"),
    "起升减速机": ("减速机渗油", "机械类", "减速机输入轴端轻微渗油。"),
    "小车运行机构": ("小车运行抖动", "机械类", "小车启动和制动时抖动明显。"),
    "司机室": ("司机室玻璃松动", "其他类", "司机室前窗玻璃密封条老化松动。"),
}

ATTRIBUTION_PLAN = [
    ("客户（质保内）", 18),
    ("客户（质保外）", 14),
    ("技术支持", 16),
    ("其他", 14),
    ("发货问题", 10),
    ("制作问题", 10),
    ("设计问题", 5),
    ("外协问题", 5),
    ("公司自营", 4),
]

# 填充数据刻意避开 5 条预警规则的条件组合，保证演示数字稳定
COMPONENTS_BY_ATTRIBUTION = {
    "客户（质保内）": ["钢丝绳", "限位开关", "遥控器", "缓冲器"],
    "客户（质保外）": ["钢丝绳", "制动器", "吊钩组", "缓冲器"],
    "技术支持": ["电控柜", "遥控器", "限位开关"],
    "其他": ["司机室", "缓冲器", "电控柜"],
    "发货问题": ["钢丝绳", "电控柜", "缓冲器"],
    "制作问题": ["制动器", "钢丝绳", "限位开关", "电控柜"],
    "设计问题": ["小车运行机构", "电控柜", "司机室"],
    "外协问题": ["主梁", "起升减速机", "吊钩组"],
    "公司自营": ["制动器", "缓冲器", "限位开关"],
}

SUPPLIERS = {"外协问题": ["洛阳XX钢铁", "江苏XX减速机"], "制作问题": ["自制"], "发货问题": ["自制"], "公司自营": ["自制"]}
DESIGNERS = ["王工", "李工", "赵工"]
TEAMS = ["装配一班", "装配二班", "涂装一班", "焊接一班", "电气班"]

start = date(2025, 11, 1)
end = date(2026, 11, 9)
span = (end - start).days

next_id = max(issue["id"] for issue in ISSUES) + 1
month_seq: dict[str, int] = {}
for issue in ISSUES:
    month = issue["date"][:7]
    month_seq[month] = max(month_seq.get(month, 0), int(issue["issue_no"].split("-")[-1]))

for index in range(74):
    day = start + timedelta(days=rng.randint(0, span))
    day_text = day.isoformat()
    attribution = weighted(ATTRIBUTION_PLAN)
    component = rng.choice(COMPONENTS_BY_ATTRIBUTION[attribution])
    phenomenon, fault_type, description = FILLER_TEMPLATES[component]
    cause = {
        "客户（质保内）": "使用",
        "客户（质保外）": "使用",
        "技术支持": "技术支持",
        "其他": "其他",
        "发货问题": "发货",
        "制作问题": "制作",
        "设计问题": "设计",
        "外协问题": "外协",
        "公司自营": "安装",
    }[attribution]
    machine = rng.choice(MACHINES)
    month = day_text[:7]
    seq = month_seq.get(month, 0) + 1
    month_seq[month] = seq
    issue_no = f"QI-{month.replace('-', '')}-{seq:04d}"
    while issue_no in used_issues:
        seq += 1
        month_seq[month] = seq
        issue_no = f"QI-{month.replace('-', '')}-{seq:04d}"
    used_issues.add(issue_no)

    closed = day + timedelta(days=rng.randint(2, 12))
    status = "已关闭"
    filler = {
        "id": next_id,
        "issue_no": issue_no,
        "date": day_text,
        "source": "售后服务平台" if rng.random() < 0.7 else "手工",
        "source_no": f"WX{day.strftime('%Y%m%d')}{rng.randint(100, 999)}",
        "machine_id": machine["product_no"],
        "customer": machine["customer"],
        "component": component,
        "component_code": "",
        "phenomenon": phenomenon,
        "description": description,
        "fault_type": fault_type,
        "cause": cause,
        "attribution_raw": attribution,
        "cause_detail": description,
        "team": rng.choice(TEAMS) if cause == "制作" else "",
        "designer": rng.choice(DESIGNERS) if cause == "设计" else "",
        "supplier": rng.choice(SUPPLIERS.get(attribution, [""])),
        "stage": "使用",
        "severity": rng.choice(["一般", "一般", "一般", "较重"]),
        "status": status,
        "handling": "已更换/调整并复检",
        "handling_method": rng.choice(["上门处理", "远程指导", "寄件维修"]),
        "resolved": True,
        "recurrence_of": None,
        "closed_at": closed.isoformat(),
        "cost": rng.choice([0, 0, 200, 500, 800, 1200, 2600, 3800]),
        "batch": "",
        "after_sales_status": weighted(SALES_STATUS),
        "responsibility_status": responsibility_for(cause),
        "source_channel": weighted(CHANNELS),
        "entry_method": "订单",
        "after_sales_order": f"29000386{rng.randint(10, 99)}-10" if rng.random() < 0.12 else "",
        "contact_name": CONTACTS.get(machine["customer"], ("张伟", ""))[0],
        "contact_phone": CONTACTS.get(machine["customer"], ("", phone()))[1],
        "department": weighted([("售后部", 60), ("质量部", 25), ("客服部", 10), ("销售部", 5)]),
        "quality_status": status,
        "report_time": f"{rng.randint(8, 17):02d}:{rng.randint(0, 59):02d}",
    }
    filler["repair_no"] = repair_no(day_text, used_repairs)
    ISSUES.append(filler)
    next_id += 1

ISSUES.sort(key=lambda item: item["date"], reverse=True)
(DATA / "issues.json").write_text(json.dumps(ISSUES, ensure_ascii=False, indent=2), encoding="utf-8")
(DATA / "machines.json").write_text(json.dumps(MACHINES, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"issues={len(ISSUES)} machines={len(MACHINES)}")
print("sample:", ISSUES[0]["repair_no"], ISSUES[0]["after_sales_status"], ISSUES[0]["customer"])
