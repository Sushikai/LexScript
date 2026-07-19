"""Chat service — 会话 CRUD + 消息管理 + SSE 流式编排 + Agent 系统提示词注入。"""
from __future__ import annotations
import time
import uuid
import json
from typing import AsyncIterator
from app.db.database import query, query_one, execute
from app.core.security import encrypt as _encrypt, decrypt as _decrypt
from app.core.agent.prompts import get_system_prompt, get_scene_prompt
from app.core.llm.registry import get_llm_from_config, get_llm
from app.core.llm.base import LLMMessage
from app.core.llm.minimax import MiniMaxLLM


def _now() -> int:
    return int(time.time())


# ── 会话 CRUD ───────────────────────────────
def create_session(title: str, role: str = "legal_expert",
                   session_type: str = "normal", model: str = "",
                   owner_user_id: int = 1) -> dict:
    now = _now()
    sess_uuid = uuid.uuid4().hex
    sys_prompt = get_system_prompt(role)
    execute(
        """INSERT INTO chat_sessions (uuid, title, type, role, system_prompt, model, owner_user_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sess_uuid, title, session_type, role, sys_prompt, model or "", owner_user_id, now, now),
    )
    return get_session_by_uuid(sess_uuid)


def get_session_by_uuid(uuid: str) -> dict | None:
    row = query_one("SELECT * FROM chat_sessions WHERE uuid = ?", (uuid,))
    return dict(row) if row else None


def list_sessions(limit: int = 50, offset: int = 0,
                  user_id: int = 0) -> list[dict]:
    """列出会话。user_id=0 看全部,否则只看自己的。"""
    if user_id:
        rows = query(
            "SELECT id, uuid, title, type, role, model, created_at, updated_at FROM chat_sessions WHERE owner_user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
    else:
        rows = query(
            "SELECT id, uuid, title, type, role, model, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    return [dict(r) for r in rows]


def update_session(uuid: str, **kwargs) -> dict | None:
    fields = {k: v for k, v in kwargs.items() if v is not None}
    if not fields:
        return get_session_by_uuid(uuid)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [uuid]
    execute(f"UPDATE chat_sessions SET {set_clause} WHERE uuid = ?", tuple(vals))
    return get_session_by_uuid(uuid)


def delete_session(uuid: str):
    sess = get_session_by_uuid(uuid)
    if sess:
        execute("DELETE FROM chat_sessions WHERE uuid = ?", (uuid,))


# ── 消息 CRUD ───────────────────────────────
def add_message(session_id: int, role: str, content: str,
                tokens_in: int = 0, tokens_out: int = 0,
                model: str | None = None, owner_user_id: int = 1) -> dict:
    now = _now()
    encrypted = _encrypt(content) if content else ""
    execute(
        """INSERT INTO chat_messages (session_id, role, content, tokens_in, tokens_out, model, owner_user_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, role, encrypted, tokens_in, tokens_out, model, owner_user_id, now),
    )
    # 更新会话时间
    execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    row = query_one("SELECT * FROM chat_messages WHERE id = last_insert_rowid()")
    return dict(row) if row else {}


def _decrypt_msg(row: dict) -> dict:
    """解密消息 content 字段。"""
    d = dict(row)
    if d.get("content"):
        d["content"] = _decrypt(d["content"]) or d["content"]
    return d


def list_messages(session_id: int, limit: int = 100) -> list[dict]:
    rows = query(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at LIMIT ?",
        (session_id, limit),
    )
    return [_decrypt_msg(r) for r in rows]


def get_session_messages(session_uuid: str, limit: int = 100) -> list[dict]:
    """按 session_uuid 取消息列表(用于 agent_chat)。"""
    sess = get_session_by_uuid(session_uuid)
    if not sess:
        return []
    return list_messages(sess["id"], limit=limit)


def save_message(session_uuid: str, role: str, content: str, owner_user_id: int = 1) -> dict:
    """按 session_uuid 保存消息(用于 agent_chat)。"""
    sess = get_session_by_uuid(session_uuid)
    if not sess:
        return {}
    return add_message(sess["id"], role, content, owner_user_id=owner_user_id)


def get_recent_corrections(limit: int = 50) -> list[dict]:
    """拉历史纠错记录(供 Zero-重复错误 规则)。"""
    rows = query(
        "SELECT * FROM document_corrections ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


# ── SSE 流式发送 ────────────────────────────
async def stream_chat(session_uuid: str, user_message: str,
                      scene: str | None = None) -> AsyncIterator[str]:
    """SSE 流式对话。"""
    sess = get_session_by_uuid(session_uuid)
    if not sess:
        yield f"data: {json.dumps({'error': '会话不存在'})}\n\n"
        return

    owner_id = sess.get("owner_user_id", 0)

    # 1. 保存用户消息
    add_message(sess["id"], "user", user_message, owner_user_id=owner_id)

    # 2. 构建消息列表
    msgs = list_messages(sess["id"], limit=50)
    llm_messages = []

    # 系统提示词
    system_prompt = get_system_prompt(sess["role"])
    # 若指定场景,追加场景子提示词
    if scene:
        scene_prompt = get_scene_prompt(scene)
        if scene_prompt:
            system_prompt += f"\n\n## 本次任务\n{scene_prompt}"
    # 追加纠错记忆
    corrections = get_recent_corrections(20)
    if corrections:
        system_prompt += "\n\n## 历史纠错记录(规避以下错误)\n"
        for c in corrections:
            system_prompt += f"- [{c['issue_type']}] {c['original']} → {c['corrected']}\n"

    llm_messages.append(LLMMessage(role="system", content=system_prompt))

    for m in msgs[-30:]:  # 只取最近 30 条
        llm_messages.append(LLMMessage(role=m["role"], content=m["content"]))

    # 3. 获取 LLM (优先使用会话里保存的 model)
    llm = None
    if sess.get("model"):
        from app.services.config_service import get_config as _gcfg
        from app.core.llm.registry import PROVIDER_CONFIGS
        pk = _gcfg("llm_api_key") or _gcfg("minimax_api_key")
        pv = _gcfg("llm_provider") or "minimax"
        if pk:
            pi = PROVIDER_CONFIGS.get(pv, {})
            llm = get_llm(api_key=pk, base_url=pi.get("base_url", ""), model=sess["model"])
    if not llm:
        llm = get_llm_from_config()
    if not llm:
        yield f"data: {json.dumps({'error': '请先配置 API Key'})}\n\n"
        return

    # 4. 双模型路由检测:若配置了 Alpha GPT 且用户消息含法律关键词
    from app.services.config_service import get_config
    alpha_key = get_config("alpha_gpt_api_key")
    legal_keywords = ["法条", "起诉", "诉讼", "合同", "风险", "合规", "证据", "侵权", "债权", "赔偿"]
    use_dual = bool(alpha_key) and any(kw in user_message for kw in legal_keywords)

    if use_dual:
        # 双模型模式:第一轮事实提取,第二轮法律分析
        alpha_model = get_config("alpha_gpt_model") or "MiniMax-M3"
        alpha_llm = MiniMaxLLM(
            api_key=alpha_key,
            base_url="https://api.MiniMax.io/v1",
            model=alpha_model,
        )

        # 第一轮:事实提取(用主 LLM)
        fact_prompt = f"""你是一位法律助理。请从以下对话中提取关键法律事实和问题焦点。

对话上下文:
{system_prompt[:2000]}

用户问题:
{user_message}

请输出结构化摘要:
1. 涉及的法律领域
2. 关键事实
3. 需要分析的法律问题"""
        fact_msgs = [LLMMessage(role="system", content="你是一位严谨的法律助理。"), LLMMessage(role="user", content=fact_prompt)]
        fact_summary = ""
        try:
            async for chunk in llm.stream(fact_msgs):
                fact_summary += chunk
        except Exception:
            fact_summary = user_message  # fallback

        # 第二轮:法律分析(用 Alpha GPT)
        legal_prompt = f"""你是一位资深法律专家(Alpha GPT)。请基于以下材料进行专业法律分析。

## 事实摘要
{fact_summary[:3000]}

## 用户问题
{user_message}

请提供:
1. 法律依据(引用具体法条)
2. 风险分析
3. 专业建议"""
        legal_msgs = [
            LLMMessage(role="system", content=get_system_prompt(sess["role"])),
            LLMMessage(role="user", content=legal_prompt),
        ]
        full_content = ""
        tokens_out = 0
        try:
            async for chunk in alpha_llm.stream(legal_msgs):
                full_content += chunk
                tokens_out += 1
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
            add_message(sess["id"], "assistant", full_content,
                        tokens_out=tokens_out, model=alpha_llm.model, owner_user_id=owner_id)
            yield f"data: {json.dumps({'content': '', 'done': True, 'model': alpha_llm.model, 'tokens_out': tokens_out})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
        return

    # 5. 单模型 SSE 流式输出(原有行为)
    full_content = ""
    tokens_out = 0
    try:
        async for chunk in llm.stream(llm_messages):
            full_content += chunk
            tokens_out += 1
            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

        # 6. 保存助手消息
        add_message(sess["id"], "assistant", full_content,
                    tokens_out=tokens_out, model=llm.model, owner_user_id=owner_id)
        yield f"data: {json.dumps({'content': '', 'done': True, 'model': llm.model, 'tokens_out': tokens_out})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"