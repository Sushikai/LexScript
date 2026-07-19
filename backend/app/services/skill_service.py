"""User skill service — CRUD for user-created skills."""
from __future__ import annotations
import time
from app.db.database import query, query_one, execute

_SKILL_TABLE = "skills"


def _now() -> int:
    return int(time.time())


def list_user_skills(owner_user_id: int = 0) -> list[dict]:
    """List all skills, optionally filtered by owner."""
    if owner_user_id:
        rows = query(
            f"SELECT name, category, description, prompt, created_at FROM {_SKILL_TABLE} WHERE owner_user_id = ? ORDER BY category, name",
            (owner_user_id,),
        )
    else:
        rows = query(
            f"SELECT name, category, description, prompt, created_at FROM {_SKILL_TABLE} ORDER BY category, name",
        )
    return [dict(r) for r in rows]


def get_skill(name: str) -> dict | None:
    """Get a single skill by name."""
    row = query_one(f"SELECT * FROM {_SKILL_TABLE} WHERE name = ?", (name,))
    return dict(row) if row else None


def create_skill(name: str, category: str, description: str, prompt: str, owner_user_id: int = 1) -> dict:
    """Create a new user skill. Raises ValueError if name exists."""
    existing = get_skill(name)
    if existing:
        raise ValueError(f"技能 '{name}' 已存在")
    now = _now()
    execute(
        f"INSERT INTO {_SKILL_TABLE} (name, category, description, prompt, owner_user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, category, description, prompt, owner_user_id, now, now),
    )
    return get_skill(name)


def delete_skill(name: str) -> bool:
    """Delete a skill by name. Returns True if deleted."""
    existing = get_skill(name)
    if existing:
        execute(f"DELETE FROM {_SKILL_TABLE} WHERE name = ?", (name,))
        return True
    return False


def update_skill(name: str, **kwargs) -> dict | None:
    """Update skill fields by name."""
    fields = {k: v for k, v in kwargs.items() if v is not None}
    if not fields:
        return get_skill(name)
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [name]
    execute(f"UPDATE {_SKILL_TABLE} SET {set_clause} WHERE name = ?", tuple(vals))
    return get_skill(name)
