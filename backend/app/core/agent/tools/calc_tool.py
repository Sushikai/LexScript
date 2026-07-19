"""
Legal Calculator Tool — 法律计算器。
覆盖：诉讼时效、诉讼费、违约金、利息、赔偿金、劳动补偿计算。
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Any
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult


# 常见诉讼时效期间（年）
SOL_PERIODS = {
    "一般诉讼时效": 3,
    "劳动争议仲裁时效": 1,
    "国际货物买卖合同": 4,
    "环境损害赔偿": 3,
    "国家赔偿": 2,
    "税务行政处罚": 5,
    "知识产权侵权": 3,
    "人身损害赔偿": 3,
    "产品质量责任": 2,
    "海商法海上货物运输": 1,
}

# 财产案件诉讼费速算表（争议金额 → 费率）
COURT_FEE_BRACKETS = [
    (10000,        0.50,  50),       # 1万以下：50元
    (100000,       0.025, 300),       # 1万-10万：2.5% + 300
    (200000,       0.020, 800),       # 10万-20万：2% + 800
    (500000,       0.015, 1800),      # 20万-50万：1.5% + 1800
    (1000000,      0.010, 4300),      # 50万-100万：1% + 4300
    (2000000,      0.009, 8300),      # 100万-200万：0.9% + 8300
    (5000000,      0.008, 17300),     # 200万-500万：0.8% + 17300
    (10000000,     0.007, 41300),     # 500万-1000万：0.7% + 41300
    (20000000,     0.006, 91300),     # 1000万-2000万：0.6% + 91300
    (float('inf'), 0.005, 151300),    # 2000万以上：0.5% + 151300
]


def calc_court_fee(amount: float) -> float:
    """计算财产案件诉讼费。"""
    prev_limit = 0
    prev_fee = 0
    for limit, rate, base_fee in COURT_FEE_BRACKETS:
        if amount <= limit:
            return prev_fee + (amount - prev_limit) * rate
        prev_limit = limit
        prev_fee = base_fee
    return prev_fee  # fallback


def calc_sol(incident_date: str, period_type: str = "一般诉讼时效") -> dict:
    """计算诉讼时效截止日期。"""
    try:
        d = datetime.strptime(incident_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {"error": "日期格式错误，请使用 YYYY-MM-DD"}
    years = SOL_PERIODS.get(period_type, 3)
    deadline = d.replace(year=d.year + years)
    remaining = (deadline - datetime.now()).days if datetime.now() < deadline else 0
    return {
        "起算日": incident_date,
        "时效类型": period_type,
        "时效期间": f"{years}年",
        "截止日": deadline.strftime("%Y-%m-%d"),
        "剩余天数": max(remaining, 0),
        "是否已届满": remaining <= 0,
    }


def calc_interest(principal: float, rate: float, start_date: str, end_date: str) -> dict:
    """计算利息（简单利率）。"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {"error": "日期格式错误，请使用 YYYY-MM-DD"}
    days = (end - start).days
    if days <= 0:
        return {"error": "截止日必须晚于起算日"}
    annual_interest = principal * rate
    actual_interest = annual_interest * days / 365
    return {
        "本金": principal,
        "年利率": f"{rate*100:.2f}%",
        "计息天数": days,
        "年利息": round(annual_interest, 2),
        "应付利息": round(actual_interest, 2),
        "本息合计": round(principal + actual_interest, 2),
    }


def calc_late_payment_penalty(amount: float, days: int, rate: float = 0.0005) -> dict:
    """计算逾期付款违约金（默认日万分之五）。"""
    penalty = amount * rate * days
    return {
        "本金": amount,
        "日费率": f"{rate*100:.4f}%",
        "逾期天数": days,
        "违约金": round(penalty, 2),
        "合计": round(amount + penalty, 2),
    }


# ── Tools ─────────────────────────────────────────

class SolCheckTool(BaseTool):
    """诉讼时效计算器。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="sol_calc",
            description="计算诉讼时效截止日期及是否已届满。支持一般诉讼时效(3年)、劳动争议(1年)、国际货物买卖(4年)、国家赔偿(2年)等。",
            parameters={
                "type": "object",
                "properties": {
                    "incident_date": {
                        "type": "string",
                        "description": "起算日，格式 YYYY-MM-DD，如 2023-06-15",
                    },
                    "period_type": {
                        "type": "string",
                        "description": "时效类型，默认'一般诉讼时效'。可选：一般诉讼时效/劳动争议仲裁时效/国际货物买卖合同/国家赔偿/人身损害赔偿/知识产权侵权",
                    },
                },
                "required": ["incident_date"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        incident_date = kwargs.get("incident_date", "")
        period_type = kwargs.get("period_type", "一般诉讼时效")
        result = calc_sol(incident_date, period_type)
        return ToolResult(success="error" not in result, data=result)


class CourtFeeCalcTool(BaseTool):
    """诉讼费计算器。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="court_fee_calc",
            description="计算财产案件诉讼费（受理费），按争议金额自动套用费率。也支持计算保全费、执行费。",
            parameters={
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "争议金额（元）",
                    },
                    "fee_type": {
                        "type": "string",
                        "description": "费用类型：受理费/保全费/执行费，默认受理费",
                    },
                },
                "required": ["amount"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        amount = float(kwargs.get("amount", 0))
        fee_type = kwargs.get("fee_type", "受理费")
        if amount < 0:
            return ToolResult(success=False, error="金额不能为负")
        court_fee = calc_court_fee(amount)
        # 保全费：最高5000，最低30，0.5% + 30
        preservation_fee = min(max(amount * 0.005 + 30, 30), 5000) if amount > 0 else 0

        data = {
            "争议金额": amount,
            "受理费": round(court_fee, 2),
            "保全费": round(preservation_fee, 2) if fee_type == "保全费" else None,
        }
        if fee_type == "受理费":
            data["说明"] = "受理费=案件受理费，不含保全费、执行费"
        return ToolResult(success=True, data=data)


class DamageCalcTool(BaseTool):
    """赔偿金/利息/违约金计算器。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="damage_calc",
            description="计算各类赔偿金额：逾期付款违约金（日万分之五）、利息（指定利率/期间）、LPR利率利息、劳动补偿金等。",
            parameters={
                "type": "object",
                "properties": {
                    "calc_type": {
                        "type": "string",
                        "description": "计算类型：违约金/利息/劳动补偿",
                        "enum": ["违约金", "利息", "劳动补偿"],
                    },
                    "principal": {
                        "type": "number",
                        "description": "本金金额（元）",
                    },
                    "rate": {
                        "type": "number",
                        "description": "年利率（如输入5表示5%），默认违约金日万分之五",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "起算日 YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "截止日 YYYY-MM-DD，默认今天",
                    },
                },
                "required": ["calc_type", "principal"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        calc_type = kwargs.get("calc_type", "违约金")
        principal = float(kwargs.get("principal", 0))
        rate = kwargs.get("rate")
        start_date = kwargs.get("start_date", "")
        end_date = kwargs.get("end_date", datetime.now().strftime("%Y-%m-%d"))

        if principal < 0:
            return ToolResult(success=False, error="金额不能为负")

        if calc_type == "违约金":
            # 默认日万分之五
            daily_rate = 0.0005
            if start_date:
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                    end = datetime.strptime(end_date, "%Y-%m-%d")
                    days = (end - start).days
                except (ValueError, TypeError):
                    days = 365
            else:
                days = 365
            data = calc_late_payment_penalty(principal, max(days, 1), daily_rate)

        elif calc_type == "利息":
            if not start_date:
                return ToolResult(success=False, error="利息计算需要提供起算日")
            annual_rate = (rate or 3.45) / 100  # 默认 LPR 一年期 3.45%
            data = calc_interest(principal, annual_rate, start_date, end_date)

        else:
            data = {"message": "劳动补偿计算器（开发中），请使用其他计算类型"}

        return ToolResult(success=True, data=data)
