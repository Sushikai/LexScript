"""
Legal Skills API — 专业法律技能指令库的查询与应用。
技能注入当前会话的 system_prompt，让 AI 按选定角色的专业规范作答。
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.api.v1 import router as v1_router
from app.services.chat_service import get_session_by_uuid, update_session
from app.core.agent.prompts import get_system_prompt
from app.core.legal_skills import LEGAL_SKILLS, get_all_skills as _get_all_skills

router = APIRouter(prefix="/legal-skills", tags=["legal_skills"])
v1_router.include_router(router)

SKILL_MARKER_START = "\n\n<!-- SKILL:"
SKILL_MARKER_END = "<!-- /SKILL -->"


@router.get("")
def list_skills():
    """列出所有法律技能（内置 + 用户自定义），按分类分组。"""
    return {"ok": True, "data": _get_all_skills()}


class ApplySkillReq(BaseModel):
    skill_name: str


def _get_skill_prompt(name: str) -> str | None:
    """Get skill prompt from LEGAL_SKILLS (builtin) or DB (user-created)."""
    skill = LEGAL_SKILLS.get(name)
    if skill:
        return skill["prompt"]
    from app.services.skill_service import get_skill
    s = get_skill(name)
    return s["prompt"] if s else None


def _get_skill_category(name: str) -> str:
    """Get skill category."""
    skill = LEGAL_SKILLS.get(name)
    if skill:
        return skill["category"]
    from app.services.skill_service import get_skill
    s = get_skill(name)
    return s["category"] if s else ""


@router.post("/sessions/{uuid}/apply")
def apply_skill(uuid: str, req: ApplySkillReq):
    """应用技能到指定会话（注入 system_prompt）。"""
    session = get_session_by_uuid(uuid)
    if not session:
        return {"ok": False, "code": "NOT_FOUND", "message": "会话不存在"}

    prompt = _get_skill_prompt(req.skill_name)
    if not prompt:
        return {"ok": False, "code": "NOT_FOUND", "message": f"技能不存在: {req.skill_name}"}

    category = _get_skill_category(req.skill_name)

    # 移除已有技能标记
    current_prompt = session["system_prompt"] or ""
    if SKILL_MARKER_START in current_prompt:
        base = current_prompt.split(SKILL_MARKER_START)[0].rstrip()
    else:
        base = get_system_prompt(session["role"])

    # 注入新技能
    skill_block = (
        f"{SKILL_MARKER_START}{req.skill_name}{SKILL_MARKER_END}\n"
        f"你当前启用了专业技能「{category} · {req.skill_name}」。\n"
        f"请严格遵循以下专业指令执行本次任务：\n\n"
        f"{prompt}"
    )
    new_prompt = f"{base}\n\n{skill_block}"

    update_session(uuid, system_prompt=new_prompt)
    return {"ok": True, "data": {"skill_name": req.skill_name, "category": category}}


@router.delete("/sessions/{uuid}/skill")
def remove_skill(uuid: str):
    """移除会话中已应用的技能。"""
    session = get_session_by_uuid(uuid)
    if not session:
        return {"ok": False, "code": "NOT_FOUND", "message": "会话不存在"}

    current_prompt = session["system_prompt"] or ""
    if SKILL_MARKER_START not in current_prompt:
        return {"ok": True, "data": {"skill_name": None, "message": "当前未应用技能"}}

    base = current_prompt.split(SKILL_MARKER_START)[0].rstrip()
    update_session(uuid, system_prompt=base)
    return {"ok": True, "data": {"skill_name": None}}


@router.get("/sessions/{uuid}/active")
def active_skill(uuid: str):
    """查询会话当前激活的技能。"""
    session = get_session_by_uuid(uuid)
    if not session:
        return {"ok": False, "code": "NOT_FOUND", "message": "会话不存在"}

    prompt = session["system_prompt"] or ""
    if SKILL_MARKER_START in prompt:
        name = prompt.split(SKILL_MARKER_START)[1].split(SKILL_MARKER_END)[0]
        category = _get_skill_category(name)
        return {"ok": True, "data": {"skill_name": name, "category": category}}
    return {"ok": True, "data": {"skill_name": None}}


@router.get("/list-custom")
def list_custom_skills():
    """列出用户自定义技能。"""
    from app.services.skill_service import list_user_skills
    skills = list_user_skills()
    return {"ok": True, "data": [{"name": s["name"], "category": s["category"], "description": s["description"]} for s in skills]}


class CreateSkillReq(BaseModel):
    name: str
    category: str
    description: str
    prompt: str


@router.post("/create")
def create_user_skill(req: CreateSkillReq):
    """（直接 API 创建）创建一个用户自定义技能。"""
    from app.services.skill_service import create_skill
    try:
        skill = create_skill(name=req.name, category=req.category, description=req.description, prompt=req.prompt)
        return {"ok": True, "data": {"name": skill["name"], "category": skill["category"]}}
    except ValueError as e:
        return {"ok": False, "code": "CONFLICT", "message": str(e)}


class DeleteSkillReq(BaseModel):
    name: str


@router.post("/delete")
def delete_user_skill(req: DeleteSkillReq):
    """删除一个用户自定义技能。"""
    if req.name in LEGAL_SKILLS:
        return {"ok": False, "code": "FORBIDDEN", "message": "内置技能不能删除"}
    from app.services.skill_service import delete_skill
    ok = delete_skill(req.name)
    if ok:
        return {"ok": True, "data": {"name": req.name, "deleted": True}}
    return {"ok": False, "code": "NOT_FOUND", "message": f"技能不存在: {req.name}"}
