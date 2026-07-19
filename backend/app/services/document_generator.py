"""
Document Generator — ★ 核心模板:一键案稿生成工作流。

5 步工作流:
1. 读取卷宗 → 拼接上下文
2. 向量检索匹配 → 同案件历史文书 + 同类模板
3. 法条匹配 → 命中法条列表
4. 历史避错 → document_corrections 高频错误入 system prompt
5. AI 生成 → SSE 流式输出 → 落库

支持双模型路由:法律分析走"Alpha GPT"(可配置第二模型),事实提取用主 LLM。
"""
from __future__ import annotations
import time
import uuid
import json
from typing import AsyncIterator
from app.db.database import query, query_one, execute
from app.core.security import encrypt as _encrypt, decrypt as _decrypt
from app.services.file_service import get_file
from app.core.llm.registry import get_llm_from_config
from app.core.llm.base import LLMMessage
from app.core.agent.prompts import get_system_prompt, SCENE_PROMPTS
from app.services.vector_service import search_hybrid
from app.core.vector.chunker import chunk_text


def _now() -> int:
    return int(time.time())


def get_corrections(limit: int = 50) -> list[dict]:
    rows = query(
        "SELECT issue_type, original, corrected, severity FROM document_corrections ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def _get_alpha_gpt_llm():
    """读取 alpha_gpt_api_key 配置,返回第二 LLM 实例(如未配返回 None)。"""
    from app.services.config_service import get_config
    api_key = get_config("alpha_gpt_api_key")
    if not api_key:
        return None
    model = get_config("alpha_gpt_model") or ""
    # Alpha GPT 默认走 MiniMax 的 M3
    base_url = "https://api.MiniMax.io/v1"
    from app.core.llm.minimax import MiniMaxLLM
    return MiniMaxLLM(api_key=api_key, base_url=base_url, model=model or "MiniMax-M3")


async def dual_model_generate(
    user_prompt: str,
    case_context: str,
    rag_context: str,
    statutes_context: str,
    corrections_context: str,
    doc_type: str,
) -> str:
    """双模型生成:
    第一轮:用主 LLM 提取事实与关键信息,构造法律检索 query。
    第二轮:用 Alpha GPT(或主 LLM fallback)进行法律分析,结合第一轮结果生成最终文书。
    """
    main_llm = get_llm_from_config()
    if not main_llm:
        raise RuntimeError("请先配置 API Key")

    alpha_llm = _get_alpha_gpt_llm() or main_llm

    # 第一轮:事实提取
    fact_extract_prompt = f"""你是一位法律助理。请从以下案件材料中提取关键事实和法律争议焦点，输出为结构化摘要。

案件材料:
{case_context[:6000]}

用户需求:
{user_prompt}

请输出:
1. 关键事实(时间、人物、事件)
2. 法律争议焦点
3. 可能适用的法律领域
4. 建议检索的法律条文关键词
"""
    fact_messages = [
        LLMMessage(role="system", content="你是一位严谨的法律助理,擅长从事实中提取关键信息。"),
        LLMMessage(role="user", content=fact_extract_prompt),
    ]
    fact_summary = ""
    try:
        async for chunk in main_llm.stream(fact_messages):
            fact_summary += chunk
    except Exception as e:
        raise RuntimeError(f"事实提取失败: {e}")

    # 第二轮:法律分析 + 文书生成
    legal_analysis_prompt = f"""你是一位资深诉讼律师(Alpha GPT)。基于以下材料和法律分析,生成{user_prompt}案的{doc_type}。

## 事实摘要(由法律助理整理)
{fact_summary[:3000]}

## 相关文书参考(RAG)
{rag_context}

## 匹配法条
{statutes_context or "无匹配法条"}

## 历史纠错
{corrections_context}
"""
    system_prompt = get_system_prompt("litigator")
    legal_messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=legal_analysis_prompt),
    ]
    final_content = ""
    try:
        async for chunk in alpha_llm.stream(legal_messages):
            final_content += chunk
    except Exception as e:
        raise RuntimeError(f"法律分析生成失败: {e}")

    return final_content


async def generate_document(
    case_name: str,
    file_ids: list[int],
    doc_type: str,
    template_id: int | None = None,
    session_id: str | None = None,
    extra_requirements: str = "",
    owner_user_id: int = 0,
) -> dict:
    """5 步一键案稿生成,返回 document 记录。"""
    doc_uuid = uuid.uuid4().hex
    now = _now()

    # 1. 读取卷宗
    case_context = ""
    for fid in file_ids:
        f = get_file(fid)
        if not f:
            continue
        chunks = query("SELECT content, metadata FROM file_chunks WHERE file_id = ?", (fid,))
        case_context += f"\n## 文件:{f['name']}\n"
        for c in chunks[:100]:  # 最多 100 分片/文件
            case_context += c["content"][:2000] + "\n"
            if c["metadata"]:
                case_context += f"(来源:{c['metadata']})\n"

    # 2. 向量检索匹配
    vector_results = search_hybrid(case_name, top_k=10)
    rag_context = ""
    for r in vector_results:
        rag_context += f"\n- [{r.get('metadata', {}).get('file_name', 'unknown')}](score:{r.get('score', 0):.3f}): {r['document'][:500]}"

    # 3. 法条匹配
    statute_results = query(
        "SELECT code, name, content FROM statutes WHERE content LIKE ? LIMIT 10",
        (f"%{case_name[:10]}%",),
    )
    statutes_context = ""
    for s in statute_results:
        statutes_context += f"- {s['code']} {s['name']}: {s['content'][:300]}\n"

    # 4. 历史避错
    corrections = get_corrections(50)
    corrections_context = ""
    if corrections:
        corrections_context = "\n## 历史纠错记录(必须规避)\n"
        for c in corrections:
            corrections_context += f"- [{c['severity']}][{c['issue_type']}] {c['original']} → {c['corrected']}\n"

    # 5. AI 生成(支持双模型:Alpha GPT 模式)
    from app.services.config_service import get_config
    alpha_key = get_config("alpha_gpt_api_key")

    if alpha_key:
        # 双模型路由:事实提取 + 法律分析
        full_content = await dual_model_generate(
            user_prompt=f"{case_name} {doc_type}",
            case_context=case_context,
            rag_context=rag_context,
            statutes_context=statutes_context,
            corrections_context=corrections_context,
            doc_type=doc_type,
        )
    else:
        # 单模型模式(原有行为)
        llm = get_llm_from_config()
        if not llm:
            raise RuntimeError("请先配置 API Key")

        system_prompt = get_system_prompt("litigator")
        system_prompt += f"""

## 本次任务:生成【{doc_type}】
{document_generation_prompt(doc_type)}

## 案件材料上下文
{case_context[:8000]}

## 相关文书参考(RAG 检索结果)
{rag_context}

## 匹配法条
{statutes_context or "无匹配法条"}

## 用户额外要求
{extra_requirements or "无"}
{corrections_context}
"""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"请基于上述材料,生成一份{case_name}案的{doc_type}。"),
        ]

        full_content = ""
        try:
            async for chunk in llm.stream(messages):
                full_content += chunk
        except Exception as e:
            raise RuntimeError(f"AI 生成失败: {e}")

    # 落库(内容加密存储)
    encrypted_content = _encrypt(full_content) if full_content else ""
    execute(
        """INSERT INTO documents (uuid, title, case_name, doc_type, content, source_files, statutes, owner_user_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_uuid, f"{case_name}_{doc_type}", case_name, doc_type, encrypted_content,
         json.dumps(file_ids), json.dumps([dict(s) for s in statute_results]), owner_user_id, now, now),
    )

    # 自动索引到向量库供 AI 搜索(用明文)
    try:
        from app.services.knowledge_service import index_document_to_vector
        index_document_to_vector(doc_uuid, f"{case_name}_{doc_type}", full_content)
    except Exception:
        pass

    return dict(query_one("SELECT * FROM documents WHERE uuid = ?", (doc_uuid,)))


async def generate_document_stream(
    case_name: str,
    file_ids: list[int],
    doc_type: str,
    template_id: int | None = None,
    session_id: str | None = None,
    extra_requirements: str = "",
    owner_user_id: int = 0,
) -> AsyncIterator[dict]:
    """流式版一键案稿生成,逐步 yield SSE 事件,最后落库。"""
    doc_uuid = uuid.uuid4().hex
    now = _now()

    # 1. 读取卷宗
    yield {"event": "status", "data": json.dumps({"status": "reading_files", "message": "正在读取卷宗文件..."})}
    case_context = ""
    for fid in file_ids:
        f = get_file(fid)
        if not f:
            continue
        chunks = query("SELECT content, metadata FROM file_chunks WHERE file_id = ?", (fid,))
        case_context += f"\n## 文件:{f['name']}\n"
        for c in chunks[:100]:
            case_context += c["content"][:2000] + "\n"
            if c["metadata"]:
                case_context += f"(来源:{c['metadata']})\n"

    # 2. 向量检索匹配
    yield {"event": "status", "data": json.dumps({"status": "searching", "message": "正在检索相关文书与法条..."})}
    vector_results = search_hybrid(case_name, top_k=10)
    rag_context = ""
    for r in vector_results:
        rag_context += f"\n- [{r.get('metadata', {}).get('file_name', 'unknown')}](score:{r.get('score', 0):.3f}): {r['document'][:500]}"

    statute_results = query(
        "SELECT code, name, content FROM statutes WHERE content LIKE ? LIMIT 10",
        (f"%{case_name[:10]}%",),
    )
    statutes_context = ""
    for s in statute_results:
        statutes_context += f"- {s['code']} {s['name']}: {s['content'][:300]}\n"

    # 3. 历史避错
    corrections = get_corrections(50)
    corrections_context = ""
    if corrections:
        corrections_context = "\n## 历史纠错记录(必须规避)\n"
        for c in corrections:
            corrections_context += f"- [{c['severity']}][{c['issue_type']}] {c['original']} → {c['corrected']}\n"

    # 4. AI 生成
    yield {"event": "status", "data": json.dumps({"status": "generating", "message": "AI 正在生成文书..."})}
    from app.services.config_service import get_config
    alpha_key = get_config("alpha_gpt_api_key")

    full_content = ""
    used_model = ""

    if alpha_key:
        # 双模型路由:事实提取 + 法律分析
        yield {"event": "status", "data": json.dumps({"status": "extracting", "message": "法律助理正在提取关键事实..."})}

        main_llm = get_llm_from_config()
        if not main_llm:
            yield {"event": "error", "data": json.dumps({"message": "请先配置 API Key"})}
            return

        alpha_llm_raw = _get_alpha_gpt_llm() or main_llm

        # 第一轮:事实提取(主 LLM 流式)
        fact_extract_prompt = f"""你是一位法律助理。请从以下案件材料中提取关键事实和法律争议焦点，输出为结构化摘要。

案件材料:
{case_context[:6000]}

用户需求:
{case_name} {doc_type}

请输出:
1. 关键事实(时间、人物、事件)
2. 法律争议焦点
3. 可能适用的法律领域
4. 建议检索的法律条文关键词
"""
        fact_messages = [
            LLMMessage(role="system", content="你是一位严谨的法律助理,擅长从事实中提取关键信息。"),
            LLMMessage(role="user", content=fact_extract_prompt),
        ]
        fact_summary = ""
        try:
            async for chunk in main_llm.stream(fact_messages):
                fact_summary += chunk
                yield {"event": "chunk", "data": json.dumps({"text": chunk, "phase": "extract"})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"事实提取失败: {e}"})}
            return

        yield {"event": "status", "data": json.dumps({"status": "analyzing", "message": "Alpha GPT 正在进行法律分析..."})}

        # 第二轮:法律分析 + 文书生成(Alpha GPT 流式)
        legal_analysis_prompt = f"""你是一位资深诉讼律师(Alpha GPT)。基于以下材料和法律分析,生成{case_name}案的{doc_type}。

## 事实摘要(由法律助理整理)
{fact_summary[:3000]}

## 相关文书参考(RAG)
{rag_context}

## 匹配法条
{statutes_context or "无匹配法条"}

## 历史纠错
{corrections_context}
"""
        system_prompt = get_system_prompt("litigator")
        legal_messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=legal_analysis_prompt),
        ]
        try:
            async for chunk in alpha_llm_raw.stream(legal_messages):
                full_content += chunk
                yield {"event": "chunk", "data": json.dumps({"text": chunk, "phase": "generate"})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"法律分析生成失败: {e}"})}
            return
        used_model = alpha_llm_raw.model
    else:
        # 单模型模式
        llm = get_llm_from_config()
        if not llm:
            yield {"event": "error", "data": json.dumps({"message": "请先配置 API Key"})}
            return

        system_prompt = get_system_prompt("litigator")
        system_prompt += f"""

## 本次任务:生成【{doc_type}】
{document_generation_prompt(doc_type)}

## 案件材料上下文
{case_context[:8000]}

## 相关文书参考(RAG 检索结果)
{rag_context}

## 匹配法条
{statutes_context or "无匹配法条"}

## 用户额外要求
{extra_requirements or "无"}
{corrections_context}
"""
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"请基于上述材料,生成一份{case_name}案的{doc_type}。"),
        ]

        try:
            async for chunk in llm.stream(messages):
                full_content += chunk
                yield {"event": "chunk", "data": json.dumps({"text": chunk})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"message": f"AI 生成失败: {e}"})}
            return
        used_model = llm.model

    # 落库(内容加密存储)
    encrypted_content = _encrypt(full_content) if full_content else ""
    execute(
        """INSERT INTO documents (uuid, title, case_name, doc_type, content, source_files, statutes, owner_user_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_uuid, f"{case_name}_{doc_type}", case_name, doc_type, encrypted_content,
         json.dumps(file_ids), json.dumps([dict(s) for s in statute_results]), owner_user_id, now, now),
    )

    doc = dict(query_one("SELECT * FROM documents WHERE uuid = ?", (doc_uuid,)))
    yield {"event": "done", "data": json.dumps({"document": doc, "model": used_model})}

    # 异步索引到向量库（fire-and-forget，不阻塞 SSE 流）
    try:
        from app.services.knowledge_service import index_document_to_vector
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(asyncio.to_thread(
            index_document_to_vector, doc_uuid, doc.get("title", ""), full_content
        ))
    except Exception:
        pass


def document_generation_prompt(doc_type: str) -> str:
    """返回对应文书类型的生成指引。"""
    from app.config import DOC_TYPE_STRUCTURES
    sections = DOC_TYPE_STRUCTURES.get(doc_type, [])
    return f"""生成要求:
1. 严格遵循法院文书格式:首部→诉讼请求→事实与理由→证据清单→尾部
2. 先确定本案请求权基础、对应法条、诉讼请求的合规性
3. 事实与理由逻辑清晰,法言法语规范,不添加材料外主观臆断
4. 文末附法律依据对照表,列明引用的全部法条全称、条款号、原文内容
5. 所有事实标注对应材料来源,支持溯源核验
6. 推荐结构:{" → ".join(sections)}"""