"""
Agent Chat API — 带多轮 Function Calling / Tool Use 的智能对话端点。
用户发消息 → LLM 判断是否调用工具 → 执行工具 → 可多轮 → 流式回复。
"""
from __future__ import annotations
import json
from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.api.v1 import router as v1_router
from app.core.agent.registry import registry
from app.core.agent.prompts import get_system_prompt
from app.services.chat_service import (
    create_session,
    get_session_by_uuid,
    get_session_messages,
    save_message,
    get_recent_corrections,
)
from app.core.llm.registry import get_llm_from_config, get_llm, PROVIDER_CONFIGS
from app.core.llm.base import LLMMessage
from app.services.config_service import get_config
from app.services.vector_service import search_hybrid

router = APIRouter(prefix="/agent", tags=["agent"])
v1_router.include_router(router)

MAX_TOOL_ROUNDS = 3


class AgentChatRequest(BaseModel):
    session_uuid: str | None = None
    message: str
    role: str = "litigator"
    model: str | None = None  # 可选模型覆盖
    file_ids: list[int] | None = None  # 关联文件 ID 列表


def _msg_to_dict(m: LLMMessage) -> dict:
    d = {"role": m.role, "content": m.content}
    if m.tool_call_id:
        d["tool_call_id"] = m.tool_call_id
    if m.tool_calls:
        d["tool_calls"] = m.tool_calls
    return d


def _parse_sse_chunk(line: str) -> str | None:
    """解析 SSE 行,返回 content chunk 或 None。"""
    line = line.strip()
    if not line or line == "[DONE]":
        return None
    try:
        d = json.loads(line)
        return d["choices"][0].get("delta", {}).get("content", "")
    except Exception:
        return None


@router.post("/chat")
async def agent_chat(req: AgentChatRequest):
    """Agent 对话端点 — 自动调用工具 + 多轮 + 流式回复。"""
    # LLM 初始化
    llm = None
    if req.model:
        api_key = get_config("llm_api_key") or get_config("minimax_api_key") or ""
        provider = get_config("llm_provider") or "minimax"
        pcfg = PROVIDER_CONFIGS.get(provider, {})
        if api_key:
            llm = get_llm(api_key=api_key, base_url=pcfg.get("base_url", ""), model=req.model)
    if not llm:
        llm = get_llm_from_config()
    if not llm:
        return {"ok": False, "code": "NOT_CONFIGURED", "message": "请先在设置中配置 API Key"}

    # 创建或获取会话
    session_uuid = req.session_uuid
    if not session_uuid:
        sess = create_session(title="新对话", role=req.role, model=llm.model)
        session_uuid = sess["uuid"]

    # 构建消息列表
    messages = get_session_messages(session_uuid)

    # 使用会话存储的 system_prompt（含已应用的技能）
    session = get_session_by_uuid(session_uuid)
    system_prompt = session.get("system_prompt", "") if session else get_system_prompt(req.role)
    if not system_prompt:
        system_prompt = get_system_prompt(req.role)

    # 注入历史纠错记忆
    corrections = get_recent_corrections(limit=20)
    if corrections:
        corr_text = "\n".join(
            f"- 错误: {c['original']} → 修正: {c['corrected']} (严重度: {c.get('severity','')})"
            for c in corrections
        )
        system_prompt += f"\n\n## 历史纠错记录(避免重复错误)\n{corr_text}"

    # 知识库检索: 自动搜索相关材料
    llm_api_key = get_config("llm_api_key") or get_config("minimax_api_key") or ""
    kb_results = search_hybrid(req.message, api_key=llm_api_key, top_k=5)
    if kb_results:
        kb_text = "\n\n".join(
            f"[来源: {r.get('metadata', {}).get('file_name', '知识库')}]\n{r.get('document', '')[:500]}"
            for r in kb_results
        )
        system_prompt += f"\n\n## 知识库相关材料\n{kb_text}"

    # 法条自动检索：根据用户问题自动搜索相关法律条文
    from app.db.database import query as _statute_query
    _keywords = [w for w in req.message.replace("，"," ").replace("、"," ").replace("？"," ").split() if len(w) >= 2]
    if _keywords:
        _clauses = []
        for _kw in _keywords[:5]:
            _rows = _statute_query(
                "SELECT code, name, content, category FROM statutes WHERE content LIKE ? OR name LIKE ? LIMIT 3",
                (f"%{_kw}%", f"%{_kw}%"),
            )
            _clauses.extend(dict(r) for r in _rows)
        # 去重（按 code）
        _seen_codes = set()
        _unique_clauses = []
        for _r in _clauses:
            if _r["code"] not in _seen_codes:
                _seen_codes.add(_r["code"])
                _unique_clauses.append(_r)
        if _unique_clauses:
            statutes_text = "\n\n".join(
                f"[{r['category']}] {r['name']}\n{r['content']}" for r in _unique_clauses[:5]
            )
            system_prompt += f"\n\n## 相关法律条文（自动检索）\n{statutes_text}"

    # 关联文件上下文
    if req.file_ids:
        from app.services.file_service import get_file, parse_file
        file_contexts = []
        for fid in req.file_ids:
            f = get_file(fid)
            if f:
                chunks = parse_file(fid)
                text = "\n".join(c.content for c in chunks[:20])
                file_contexts.append(f"[文件: {f.get('name', f'ID:{fid}')}]\n{text[:2000]}")
        if file_contexts:
            system_prompt += "\n\n## 用户指定的参考文件\n" + "\n\n".join(file_contexts)

    tool_defs = registry.openai_tools()

    async def event_generator():
        llm_messages = [LLMMessage(role="system", content=system_prompt)]
        for m in messages[-20:]:
            llm_messages.append(LLMMessage(role=m["role"], content=m["content"]))
        llm_messages.append(LLMMessage(role="user", content=req.message))

        save_message(session_uuid, "user", req.message)

        try:
            client = await llm._get_client()
            full_content = ""

            # 多轮工具调用循环
            for _round in range(MAX_TOOL_ROUNDS + 1):
                payload = {
                    "model": llm.model,
                    "messages": [_msg_to_dict(m) for m in llm_messages],
                    "max_tokens": 4096,
                    "temperature": 0.7,
                }

                is_final = (_round == MAX_TOOL_ROUNDS)

                if not is_final:
                    # 前 N-1 轮: 非流式, 带工具定义, 检测是否命中工具
                    payload["tools"] = tool_defs
                    payload["tool_choice"] = "auto"

                    r = await client.post(
                        "/chat/completions", json=payload,
                        headers={"Authorization": f"Bearer {llm.api_key}"},
                    )
                    if r.status_code != 200:
                        body = await r.aread()
                        yield {"event": "error", "data": json.dumps({"message": f"API {r.status_code}: {body[:500].decode()}"})}
                        return

                    data = r.json()
                    choice = data["choices"][0]
                    msg = choice.get("message", {})
                    tool_calls = msg.get("tool_calls")

                    if not tool_calls:
                        # LLM 选择不调用工具, 普通回复
                        reply = msg.get("content", "")
                        if reply:
                            yield {"event": "chunk", "data": json.dumps({"text": reply})}
                            full_content += reply
                        break

                    # 有工具调用
                    logger.info(f"[agent] 第{_round+1}轮 LLM 请求调用 {len(tool_calls)} 个工具")
                    yield {"event": "tools", "data": json.dumps({
                        "tool_calls": [
                            {"name": tc["function"]["name"], "args": tc["function"]["arguments"]}
                            for tc in tool_calls
                        ],
                        "round": _round + 1,
                    })}

                    tool_results = await registry.call_tools_from_llm(tool_calls)
                    yield {"event": "tool_results", "data": json.dumps(tool_results)}

                    # 追加 assistant + tool 消息到上下文
                    llm_messages.append(LLMMessage(
                        role="assistant",
                        content=msg.get("content") or "",
                        tool_calls=[{
                            "id": tc["id"],
                            "type": "function",
                            "function": tc["function"],
                        } for tc in tool_calls],
                    ))
                    for tr in tool_results:
                        llm_messages.append(LLMMessage(
                            role="tool",
                            tool_call_id=tr.get("tool_call_id", ""),
                            content=json.dumps(tr["result"], ensure_ascii=False),
                        ))

                    # 继续下一轮,LLM 可以继续调用工具或回复文本
                else:
                    # 最后一轮: 流式输出, 不带工具定义
                    payload["stream"] = True

                    async with client.stream(
                        "POST", "/chat/completions", json=payload,
                        headers={"Authorization": f"Bearer {llm.api_key}"},
                    ) as stream_r:
                        if stream_r.status_code != 200:
                            body = await stream_r.aread()
                            yield {"event": "error", "data": json.dumps({"message": f"Stream {stream_r.status_code}: {body[:300].decode()}"})}
                            return
                        async for line in stream_r.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            chunk = line[6:].strip()
                            if chunk == "[DONE]":
                                break
                            content = _parse_sse_chunk(chunk)
                            if content:
                                full_content += content
                                yield {"event": "chunk", "data": json.dumps({"text": content})}

                    break  # 流式输出完成,退出循环

            save_message(session_uuid, "assistant", full_content)
            yield {"event": "done", "data": json.dumps({"session_uuid": session_uuid, "rounds": _round + 1})}

        except Exception as e:
            logger.error(f"[agent] chat error: {e}")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())


@router.get("/tools")
async def list_agent_tools():
    """列出所有已注册的 Agent Tool。"""
    return {
        "ok": True,
        "data": {
            "tools": [t.spec.name for t in registry.all_tools],
            "total": len(registry.all_tools),
            "stats": registry.get_stats(),
        },
    }
