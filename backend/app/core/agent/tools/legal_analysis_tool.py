"""
Legal Analysis Tool — 多步案件智能分析引擎。
对标 AlphaGPT 的案件分析能力：
1. 事实提取 → 2. 法律关系定性 → 3. 争议焦点归纳 → 4. 法条匹配 → 5. 风险评估 → 6. 策略建议
"""
from __future__ import annotations
import json
import time
from typing import Any
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult
from app.core.llm.base import LLMMessage
from app.core.llm.registry import get_llm_from_config


ANALYSIS_SYSTEM_PROMPT = """你是一位资深诉讼律师兼法律分析专家。请对以下案件材料进行全方位结构化分析。

你必须严格按照以下 6 步框架输出分析结果：

## 第一步：基本事实提取
- 当事人信息：原告/被告/第三人全称、身份信息
- 案件事实：按时间线整理关键事实
- 诉讼请求/争议标的：金额、物、行为等
- 关键日期：合同签订日、违约日、起诉日等

## 第二步：法律关系定性
- 案由：精确到《民事案件案由规定》三级案由
- 法律关系类型：合同纠纷/侵权/物权/婚姻家庭/公司/知识产权等
- 法律关系要素：主体、客体、内容
- 请求权基础：具体法律规范条款

## 第三步：争议焦点归纳
- 事实争议点：当事人对哪些事实存在争议
- 法律争议点：法律适用、解释分歧
- 程序争议点：管辖、时效、主体资格
- 争议焦点排序：按对案件结果影响程度排列

## 第四步：适用法条匹配
对每个争议焦点，匹配：
- 法律名称及具体条款
- 条款原文摘要
- 是否可能存在多个解释路径
- 相关司法解释

## 第五步：风险评估
- 实体风险：败诉风险点及程度（高/中/低）
- 程序风险：管辖、时效、证据
- 执行风险：对方偿付能力、财产保全
- 综合评估：整体胜诉概率区间

## 第六步：诉讼策略建议
- 核心策略：最有利的诉讼路径
- 备选方案：多套策略对比
- 证据准备：需要补充的证据材料
- 风险防控：需要特别注意的环节

## 输出要求
- 每个步骤标题使用 ### 三级标题
- 关键信息加粗
- 争议焦点使用编号列表
- 风险等级标注：🟢低 🟡中 🔴高
- 所有法条标注具体条款号和出处
- 若有材料不足，在每一步末尾标注「待补充」"""


class LegalAnalysisTool(BaseTool):
    """多步案件智能分析。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="legal_analyze",
            description="对案件材料进行全方位结构化法律分析，包括事实提取、法律关系定性、争议焦点归纳、法条匹配、风险评估和策略建议。需要先通过 knowledge_search 搜索相关材料。",
            parameters={
                "type": "object",
                "properties": {
                    "case_name": {
                        "type": "string",
                        "description": "案件名称或案号",
                    },
                    "query": {
                        "type": "string",
                        "description": "具体的分析需求描述，如'分析张三诉李四合同纠纷案的关键争议焦点'",
                    },
                },
                "required": ["case_name", "query"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        case_name = kwargs.get("case_name", "")
        query = kwargs.get("query", "")

        try:
            # Step 1: 搜索知识库相关材料
            material_text = await self._gather_materials(case_name, query)

            # Step 2: 调用 LLM 进行结构化分析
            llm = get_llm_from_config()
            if not llm:
                return ToolResult(success=False, error="未配置 API Key")

            prompt = f"""请对以下案件材料进行全面结构化分析。

案件名称/案号：{case_name}
分析需求：{query}

可供分析的材料：
{material_text[:8000]}  # 截断到 8K 避免超长

请严格按照 6 步框架输出：事实提取 → 法律关系定性 → 争议焦点归纳 → 法条匹配 → 风险评估 → 策略建议。"""

            messages = [
                LLMMessage(role="system", content=ANALYSIS_SYSTEM_PROMPT),
                LLMMessage(role="user", content=prompt),
            ]
            result = await llm.chat(messages, max_tokens=8192, temperature=0.3)

            return ToolResult(success=True, data={
                "case_name": case_name,
                "analysis": result.content,
                "model": result.model,
                "tokens": {"in": result.tokens_in, "out": result.tokens_out},
            })

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _gather_materials(self, case_name: str, query: str) -> str:
        """从知识库收集相关材料。"""
        fragments = []

        # 搜索知识库
        try:
            from app.services.vector_service import search_hybrid
            search_results = search_hybrid(query, top_k=10)
            if search_results:
                fragments.append("【知识库搜索结果】")
                for r in search_results[:5]:
                    content = r.get("document", "")[:2000]
                    fragments.append(f"- {r.get('metadata', {}).get('file_name', '')}:\n{content}")
        except Exception:
            pass

        # 列出已索引文件
        try:
            from app.services.knowledge_service import list_kb_files, read_file_content
            files = list_kb_files(status="indexed")
            if files:
                fragments.append(f"\n【已索引文件 ({len(files)} 个)】")
                for f in files[:3]:
                    try:
                        fc = read_file_content(f["id"])
                        content = fc.get("content", "")[:3000]
                        fragments.append(f"\n## {f['name']}\n{content}")
                    except Exception:
                        pass
        except Exception:
            pass

        combined = "\n\n".join(fragments)
        return combined or "（知识库暂无相关材料，分析基于通用法律知识进行）"


class LegalOpinionTool(BaseTool):
    """生成法律意见书。"""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="legal_opinion",
            description="基于案件分析结果，生成格式规范的法律意见书，涵盖案件背景、法律分析、结论意见。",
            parameters={
                "type": "object",
                "properties": {
                    "case_name": {
                        "type": "string",
                        "description": "案件名称",
                    },
                    "analysis_data": {
                        "type": "string",
                        "description": "案件分析结果或案件事实描述",
                    },
                    "opinion_type": {
                        "type": "string",
                        "description": "意见书类型：诉讼策略意见书/法律风险意见书/合规审查意见书",
                        "enum": ["诉讼策略意见书", "法律风险意见书", "合规审查意见书"],
                    },
                },
                "required": ["case_name", "analysis_data", "opinion_type"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        case_name = kwargs.get("case_name", "")
        analysis_data = kwargs.get("analysis_data", "")
        opinion_type = kwargs.get("opinion_type", "诉讼策略意见书")

        try:
            llm = get_llm_from_config()
            if not llm:
                return ToolResult(success=False, error="未配置 API Key")

            prompt = f"""请根据以下案件信息和分析，生成一份专业的《{opinion_type}》。

案件名称：{case_name}
分析材料：
{analysis_data[:6000]}

要求：
1. 格式规范、结构完整，符合法律意见书的行业标准
2. 结论明确，分点列出意见
3. 标注不确定性或风险点
4. 引用法律法规时注明具体条款
5. 语言严谨、法言法语"""

            messages = [
                LLMMessage(role="system", content=f"你是一位资深律师，正在为客户出具{opinion_type}。要求：逻辑严谨、结论明确、风险提示充分。"),
                LLMMessage(role="user", content=prompt),
            ]
            result = await llm.chat(messages, max_tokens=8192, temperature=0.3)

            return ToolResult(success=True, data={
                "case_name": case_name,
                "opinion_type": opinion_type,
                "content": result.content,
                "model": result.model,
            })

        except Exception as e:
            return ToolResult(success=False, error=str(e))
