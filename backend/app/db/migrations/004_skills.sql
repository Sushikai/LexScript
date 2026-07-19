-- 004: 用户自定义技能表
-- 用户通过对话创建的技能存入此表，与 LEGAL_SKILLS 内置技能合并展示

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    prompt TEXT NOT NULL,
    owner_user_id INTEGER REFERENCES users(id),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_owner ON skills(owner_user_id);
