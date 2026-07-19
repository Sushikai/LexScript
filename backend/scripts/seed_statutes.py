"""
种子脚本：将核心通用法律条文写入 statutes 表。
按 15 个分类组织，每个分类包含该领域最常引用的核心条文。
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["LEXSCRIPT_ENV"] = "cli"

from app.db.database import query_one, execute
from app.core.legal_statutes import STATUTE_SEED_DATA


def seed():
    """写入所有种子法律条文。"""
    total = 0
    for code, data in STATUTE_SEED_DATA.items():
        existing = query_one("SELECT id FROM statutes WHERE code = ?", (code,))
        now = int(__import__("time").time())
        if existing:
            execute(
                "UPDATE statutes SET name=?, category=?, content=?, source=?, fetched_at=? WHERE code=?",
                (data["name"], data["category"], data["content"], "seed_builtin", now, code),
            )
        else:
            execute(
                "INSERT INTO statutes (code, name, category, content, source, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (code, data["name"], data["category"], data["content"], "seed_builtin", now),
            )
        total += 1
    categories = len(set(d["category"] for d in STATUTE_SEED_DATA.values()))
    print(f"[seed] ✓ 已导入 {total} 条法律条文, 覆盖 {categories} 个分类")


if __name__ == "__main__":
    seed()
