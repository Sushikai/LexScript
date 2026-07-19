"""Template service — 模板 CRUD + Jinja2 渲染。"""
from __future__ import annotations
import time
import json
from jinja2 import Template
from app.db.database import query, query_one, execute


def _now() -> int:
    return int(time.time())


def list_templates(category: str | None = None) -> list[dict]:
    if category:
        rows = query("SELECT * FROM templates WHERE category = ? ORDER BY updated_at DESC", (category,))
    else:
        rows = query("SELECT * FROM templates ORDER BY category, updated_at DESC")
    return [dict(r) for r in rows]


def get_template(tid: int) -> dict | None:
    row = query_one("SELECT * FROM templates WHERE id = ?", (tid,))
    return dict(row) if row else None


def create_template(name: str, category: str, content: str,
                    variables: str = "[]", description: str = "") -> dict:
    now = _now()
    execute(
        "INSERT INTO templates (name, category, content, variables, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, category, content, variables, description, now, now),
    )
    return get_template(query_one("SELECT last_insert_rowid() as id")["id"])


def update_template(tid: int, **kwargs) -> dict | None:
    t = get_template(tid)
    if not t:
        return None
    fields = {k: v for k, v in kwargs.items() if v is not None}
    if not fields:
        return t
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [tid]
    execute(f"UPDATE templates SET {set_clause} WHERE id = ?", tuple(vals))
    return get_template(tid)


def delete_template(tid: int):
    execute("DELETE FROM templates WHERE id = ?", (tid,))


def render_template(tid: int, variables: dict) -> str:
    """用 Jinja2 渲染模板。"""
    t = get_template(tid)
    if not t:
        raise ValueError(f"模板不存在: {tid}")
    jinja_tpl = Template(t["content"])
    return jinja_tpl.render(**variables)


def get_builtin_templates() -> list[dict]:
    """返回内置模板(参见 config.py DOC_TYPE_STRUCTURES)。"""
    from app.config import DOC_TYPE_STRUCTURES
    templates = []
    for doc_type, sections in DOC_TYPE_STRUCTURES.items():
        sections_html = "\n".join(f"<h2>{s}</h2>\n<p>{{{s}}}</p>" for s in sections)
        content = f"""# {{title}}
**文书类型**:{doc_type}
**当事人**:{{party_name}}
---
{sections_html}
---
生成日期:{{date}}
"""
        templates.append({
            "name": doc_type + "模板",
            "category": doc_type,
            "content": content,
            "variables": json.dumps([
                {"name": "title", "type": "text", "required": True, "label": "文书标题"},
                {"name": "party_name", "type": "text", "required": True, "label": "当事人"},
                {"name": "date", "type": "text", "required": True, "label": "日期"},
            ] + [{"name": s, "type": "textarea", "required": False, "label": s} for s in sections]),
            "description": f"{doc_type}标准模板",
        })
    return templates