"""Skill management tools for agent — create/delete skills via conversation."""
from __future__ import annotations
from app.core.agent.tool import BaseTool, ToolSpec, ToolResult


class CreateSkillTool(BaseTool):
    """Create a new legal skill via conversation. The user describes what they want,
    the LLM proposes a skill definition, and on user confirmation, calls this tool to persist it."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="create_skill",
            description="创建一个新法律技能。当用户通过对话描述想要的技能功能后，AI 先生成完整的技能定义（名称、分类、描述、指令prompt），用户确认后调用此工具保存。技能创建后立即可在技能页面看到并使用。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称，格式：分类_技能名，例如「侵权责任_交通事故责任认定分析」"},
                    "category": {"type": "string", "description": "技能分类，例如：侵权责任、合同审查、刑事诉讼、行政诉讼、婚姻家庭、知识产权等"},
                    "description": {"type": "string", "description": "技能简短描述（20-50字），说明该技能的用途"},
                    "prompt": {"type": "string", "description": "技能完整指令，AI 执行此技能时需要遵循的详细步骤和要求，用 Markdown 格式"},
                },
                "required": ["name", "category", "description", "prompt"],
            },
        )

    async def execute(self, name: str, category: str, description: str, prompt: str, **kwargs) -> ToolResult:
        from app.services.skill_service import create_skill as _create

        try:
            skill = _create(name=name, category=category, description=description, prompt=prompt)
            return ToolResult(success=True, data={
                "name": skill["name"],
                "category": skill["category"],
                "description": skill["description"],
            })
        except ValueError as e:
            return ToolResult(success=False, error=str(e))


class DeleteSkillTool(BaseTool):
    """Delete a user-created skill."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="delete_skill",
            description="删除一个用户创建的法律技能。只能删除用户自定义技能，不能删除内置技能。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "要删除的技能名称"},
                },
                "required": ["name"],
            },
        )

    async def execute(self, name: str, **kwargs) -> ToolResult:
        from app.services.skill_service import delete_skill as _delete
        from app.core.legal_skills import LEGAL_SKILLS

        if name in LEGAL_SKILLS:
            return ToolResult(success=False, error=f"'{name}' 是内置技能，不能删除")

        ok = _delete(name)
        if ok:
            return ToolResult(success=True, data={"name": name, "deleted": True})
        return ToolResult(success=False, error=f"技能 '{name}' 不存在")
