"""
Evidence Analysis Tool — 证据分析引擎。
对标 AlphaGPT 的证据清单/质证意见/证据矩阵功能。
"""
from __future__ import annotations
from typing import Any
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.services.knowledge_service import list_kb_files, read_file_content
from app.core.llm.base import LLMMessage
from app.core.llm.registry import get_llm_from_config


EVIDENCE_SYSTEM_PROMPT = """你是一位经验丰富的出庭律师，专精于证据分析。请对提供的案件材料进行专业的证据分析。

## 第一部分：证据清单
按「原告证据/被告证据/第三人证据」分组，每组包含：
- 编号、证据名称、证据类型（书证/物证/电子数据/证人证言/鉴定意见/勘验笔录）
- 证明事项（对方主张用该证据证明什么）
- 来源文件/页码
- 是否涉及保密/隐私

## 第二部分：三性分析
对每一份证据从三个维度分析：
1. **真实性**：形式真实（是否原件/复印件）、内容真实（是否与事实一致）
2. **合法性**：证据来源是否合法、取证程序是否合规
3. **关联性**：与待证事实的关联程度（直接/间接/无关）

## 第三部分：质证意见
对每份证据出具专业质证意见：
- 认可/异议/部分异议
- 异议理由（具体到证据的三性问题）
- 反驳证据建议
- 庭审询问建议

## 第四部分：证据链评估
- 原告证据链完整性（强/中/弱）
- 被告证据链完整性（强/中/弱）
- 关键证据缺失提示
- 建议补充的证据目录

## 输出格式
使用表格展示证据清单，每份证据附三性分析标签。"""


class EvidenceListTool(BaseTool):
    """生成标准化证据清单。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="evidence_list",
            description="从案件材料中提取并生成标准化证据清单，按当事人分组，包含证据名称、类型、证明事项、来源文件。",
            parameters={
                "type": "object",
                "properties": {
                    "case_name": {
                        "type": "string",
                        "description": "案件名称",
                    },
                    "file_ids": {
                        "type": "string",
                        "description": "要分析的文件ID列表，逗号分隔，如 '1,2,3'。留空则搜索全知识库",
                    },
                },
                "required": ["case_name"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        case_name = kwargs.get("case_name", "")
        file_ids_str = kwargs.get("file_ids", "")

        try:
            materials = await self._load_materials(file_ids_str, case_name)
            if not materials:
                return ToolResult(success=True, data={
                    "case_name": case_name,
                    "evidence_list": [],
                    "message": "知识库中无相关材料，请先上传案件文件",
                })

            llm = get_llm_from_config()
            if not llm:
                return ToolResult(success=False, error="未配置 API Key")

            prompt = f"""请从以下案件材料中提取并生成标准化证据清单。

案件名称：{case_name}

案件材料：
{materials[:6000]}

请输出：
1. 证据清单（表格形式，含编号/名称/类型/证明事项/来源）
2. 每份证据标记"原件/复印件/电子件"
3. 如有缺失关键证据，在末尾标注「待补充」"""

            messages = [
                LLMMessage(role="system", content=EVIDENCE_SYSTEM_PROMPT),
                LLMMessage(role="user", content=prompt),
            ]
            result = await llm.chat(messages, max_tokens=4096, temperature=0.3)

            return ToolResult(success=True, data={
                "case_name": case_name,
                "content": result.content,
                "model": result.model,
            })

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _load_materials(self, file_ids_str: str, case_name: str) -> str:
        fragments = []
        file_ids = [int(x.strip()) for x in file_ids_str.split(",") if x.strip().isdigit()] if file_ids_str else []

        for fid in file_ids:
            try:
                fc = read_file_content(fid)
                content = fc.get("content", "")[:3000]
                fragments.append(f"## {fc.get('name', fid)}\n{content}")
            except Exception:
                pass

        # 如果没有指定文件，搜索关联内容
        if not fragments:
            try:
                from app.services.vector_service import search_hybrid
                results = search_hybrid(case_name, top_k=5)
                for r in results[:3]:
                    content = r.get("document", "")[:2000]
                    fname = r.get("metadata", {}).get("file_name", "")
                    fragments.append(f"## {fname}\n{content}")
            except Exception:
                pass

        return "\n\n".join(fragments) if fragments else ""


class EvidenceCrossExamineTool(BaseTool):
    """生成质证意见。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="evidence_cross_examine",
            description="对指定证据出具专业质证意见，从真实性、合法性、关联性三个维度分析，并给出庭审询问建议。",
            parameters={
                "type": "object",
                "properties": {
                    "case_name": {
                        "type": "string",
                        "description": "案件名称",
                    },
                    "evidence_description": {
                        "type": "string",
                        "description": "对方证据描述或已提取的证据清单内容",
                    },
                    "party": {
                        "type": "string",
                        "description": "我方当事人身份：原告/被告/第三人",
                    },
                },
                "required": ["case_name", "evidence_description"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        case_name = kwargs.get("case_name", "")
        evidence_desc = kwargs.get("evidence_description", "")
        party = kwargs.get("party", "被告")

        try:
            llm = get_llm_from_config()
            if not llm:
                return ToolResult(success=False, error="未配置 API Key")

            prompt = f"""案件名称：{case_name}
我方当事人：{party}
对方证据描述：
{evidence_desc[:4000]}

请对上述证据逐一出具质证意见，包括：
1. 对每份证据的三性分析（真实性/合法性/关联性）
2. 认可或异议，并说明理由
3. 庭审交叉询问建议
4. 反驳证据建议"""

            messages = [
                LLMMessage(role="system", content=EVIDENCE_SYSTEM_PROMPT),
                LLMMessage(role="user", content=prompt),
            ]
            result = await llm.chat(messages, max_tokens=4096, temperature=0.3)

            return ToolResult(success=True, data={
                "case_name": case_name,
                "party": party,
                "content": result.content,
                "model": result.model,
            })

        except Exception as e:
            return ToolResult(success=False, error=str(e))
