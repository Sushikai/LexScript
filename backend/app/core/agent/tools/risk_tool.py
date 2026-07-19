"""
Risk Scanner Tool — 法律风险扫描引擎。
覆盖：法条有效性校验 / 程序风险 / 文书合规 / 引用核验。
"""
from __future__ import annotations
import re
from typing import Any
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.core.llm.base import LLMMessage
from app.core.llm.registry import get_llm_from_config
from app.db.database import query


RISK_SCAN_SYSTEM_PROMPT = """你是一位法律风控专家。请对以下法律文书进行全方位风险扫描。

## 扫描维度

### 1. 法条适用风险
- 引用的法条是否现行有效（已被废止/修改的标注"⚠已废止"）
- 法条是否与本案法律关系匹配
- 是否存在应当引用却未引用的法条
- 条款号引用是否准确

### 2. 程序风险
- 诉讼时效是否已过
- 管辖法院是否正确
- 当事人主体资格是否适格
- 是否存在重复起诉风险
- 举证期限是否合理

### 3. 事实与逻辑风险
- 事实陈述是否前后矛盾
- 诉讼请求是否有充分事实支撑
- 是否存在关键事实遗漏
- 推理链条是否完整

### 4. 格式与表述风险
- 文书格式是否符合司法规范
- 术语使用是否准确
- 层级结构是否清晰
- 是否存在歧义表述

### 5. 执行风险
- 对方偿付能力评估
- 是否需要财产保全
- 胜诉后执行可行性

## 输出格式
每条风险标注：
- 🔴 高风险 / 🟡 中风险 / 🟢 低风险
- 具体位置（文中引用）
- 风险描述
- 修改建议
- 依据法条"""


class RiskScanTool(BaseTool):
    """法律文书风险扫描。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="risk_scan",
            description="对法律文书进行全方位风险扫描，包括法条有效性校验、程序风险、逻辑矛盾、格式规范和执行风险评估。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "文书标题",
                    },
                    "content": {
                        "type": "string",
                        "description": "文书全文内容",
                    },
                    "scan_type": {
                        "type": "string",
                        "description": "扫描类型：full/statute/procedure/format",
                        "enum": ["full", "statute", "procedure", "format"],
                    },
                },
                "required": ["title", "content"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        title = kwargs.get("title", "")
        content = kwargs.get("content", "")
        scan_type = kwargs.get("scan_type", "full")

        try:
            llm = get_llm_from_config()
            if not llm:
                return ToolResult(success=False, error="未配置 API Key")

            # Step 1: 提取文中引用的法条
            cited_statutes = self._extract_statutes(content)

            # Step 2: 本地法条库交叉校验
            statute_checks = []
            for code, name in cited_statutes:
                local = query(
                    "SELECT content FROM statutes WHERE code LIKE ? OR name LIKE ?",
                    (f"%{code}%", f"%{name}%"),
                )
                if local:
                    statute_checks.append(f"✓ {code} {name} — 已在本地法条库")
                else:
                    statute_checks.append(f"⚠ {code} {name} — 本地法条库未收录，建议核实有效性")

            # Step 3: LLM 深度分析
            statute_context = "\n".join(statute_checks) if statute_checks else "（未检测到明确法条引用）"

            type_desc = {
                "full": "全方位扫描（法条/程序/事实/格式/执行）",
                "statute": "仅法条适用扫描",
                "procedure": "仅程序风险扫描",
                "format": "仅格式规范扫描",
            }

            prompt = f"""请对以下法律文书进行{type_desc.get(scan_type, '风险扫描')}。

文书标题：{title}

文书全文：
{content[:8000]}

引用法条校验结果：
{statute_context}"""

            messages = [
                LLMMessage(role="system", content=RISK_SCAN_SYSTEM_PROMPT),
                LLMMessage(role="user", content=prompt),
            ]
            result = await llm.chat(messages, max_tokens=4096, temperature=0.3)

            return ToolResult(success=True, data={
                "title": title,
                "risk_report": result.content,
                "cited_statutes": [{"code": c, "name": n} for c, n in cited_statutes],
                "statute_checks": statute_checks,
                "scan_type": scan_type,
                "model": result.model,
            })

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _extract_statutes(self, text: str) -> list[tuple[str, str]]:
        """从文本中提取法条引用。"""
        patterns = [
            # 《民法典》第xxx条
            r'[《]([^》]+)[》]\s*第([一二三四五六七八九十百千万\d]+)条',
            # 第xxx条
            r'第([一二三四五六七八九十百千万\d]+)条',
            # XXX法第xxx条
            r'([一-鿿]{2,6}(?:法|条例|规定|解释))\s*第([一二三四五六七八九十百千万\d]+)条',
            # 依据XX法
            r'(?:依据|根据|按照|依照)\s*[《]?([一-鿿]{2,10}(?:法|条例|规定|解释))[》]?',
        ]

        results = []
        seen = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for m in matches:
                key = str(m)
                if key not in seen:
                    seen.add(key)
                    if isinstance(m, tuple) and len(m) >= 2:
                        results.append((m[0], m[1] if len(m) > 1 else ""))
                    elif isinstance(m, str):
                        results.append((m, ""))
        return results


class ProcedureCheckTool(BaseTool):
    """程序性事项检查（诉讼时效/管辖/主体资格）。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="procedure_check",
            description="检查案件的程序性事项，包括诉讼时效是否届满、管辖法院是否正确、当事人主体资格、是否重复起诉等。",
            parameters={
                "type": "object",
                "properties": {
                    "case_facts": {
                        "type": "string",
                        "description": "案件事实描述，包括关键日期、当事人、合同/事件性质等",
                    },
                    "court": {
                        "type": "string",
                        "description": "拟起诉/已立案的法院",
                    },
                },
                "required": ["case_facts"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        case_facts = kwargs.get("case_facts", "")
        court = kwargs.get("court", "")

        try:
            llm = get_llm_from_config()
            if not llm:
                return ToolResult(success=False, error="未配置 API Key")

            prompt = f"""请对以下案件进行程序性事项核查。

案件事实：
{case_facts[:3000]}

{"拟诉法院：" + court if court else ""}

请核查：
1. 诉讼时效：争议类型对应的时效期间、起算点、是否已届满
2. 管辖法院：地域管辖、级别管辖、专属管辖、协议管辖
3. 当事人主体资格：原告是否适格、被告是否明确
4. 是否存在重复起诉或一事不再理
5. 其他程序风险（举证期限、保全、公告等）"""

            messages = [
                LLMMessage(role="system", content="你是一位精通民事诉讼程序的专业律师。请严谨、准确地分析程序法问题，引用《民事诉讼法》及相关司法解释的具体条款。"),
                LLMMessage(role="user", content=prompt),
            ]
            result = await llm.chat(messages, max_tokens=4096, temperature=0.3)

            return ToolResult(success=True, data={
                "content": result.content,
                "model": result.model,
            })

        except Exception as e:
            return ToolResult(success=False, error=str(e))
