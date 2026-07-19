"""初始化并注册所有 Agent Tools。"""
from __future__ import annotations
from app.core.agent.registry import registry
from app.core.agent.tools.file_tool import FileListTool, FileImportTool, FileParseTool
from app.core.agent.tools.search_tool import HybridSearchTool, SemanticSearchTool
from app.core.agent.tools.document_tool import DocumentGenerateTool, DocumentListTool
from app.core.agent.tools.statute_tool import StatuteSearchTool, StatuteCategoriesTool
from app.core.agent.tools.template_tool import TemplateListTool, TemplatePreviewTool
from app.core.agent.tools.knowledge_tool import (
    KbListTool, KbReadTool, KbWriteTool, KbCreateFileTool,
    KbRegTool, KbRegAllTool, KbSearchTool, KbImportTool,
)


def register_all_tools():
    """注册所有 Tool 到全局注册表。"""
    # 文件工具
    registry.register(FileListTool())
    registry.register(FileImportTool())
    registry.register(FileParseTool())

    # 检索工具
    registry.register(HybridSearchTool())
    registry.register(SemanticSearchTool())

    # 文书工具
    registry.register(DocumentGenerateTool())
    registry.register(DocumentListTool())

    # 法条工具
    registry.register(StatuteSearchTool())
    registry.register(StatuteCategoriesTool())

    # 模板工具
    registry.register(TemplateListTool())
    registry.register(TemplatePreviewTool())

    # 知识库工具
    registry.register(KbListTool())
    registry.register(KbReadTool())
    registry.register(KbWriteTool())
    registry.register(KbCreateFileTool())
    registry.register(KbRegTool())
    registry.register(KbRegAllTool())
    registry.register(KbSearchTool())
    registry.register(KbImportTool())

    # ── AlphaGPT 级高级工具 ─────────────────
    from app.core.agent.tools.legal_analysis_tool import LegalAnalysisTool, LegalOpinionTool
    registry.register(LegalAnalysisTool())
    registry.register(LegalOpinionTool())

    from app.core.agent.tools.evidence_tool import EvidenceListTool, EvidenceCrossExamineTool
    registry.register(EvidenceListTool())
    registry.register(EvidenceCrossExamineTool())

    from app.core.agent.tools.risk_tool import RiskScanTool, ProcedureCheckTool
    registry.register(RiskScanTool())
    registry.register(ProcedureCheckTool())

    from app.core.agent.tools.calc_tool import SolCheckTool, CourtFeeCalcTool, DamageCalcTool
    registry.register(SolCheckTool())
    registry.register(CourtFeeCalcTool())
    registry.register(DamageCalcTool())

    # ── 技能管理工具 ──────────────────────────
    from app.core.agent.tools.skill_tool import CreateSkillTool, DeleteSkillTool
    registry.register(CreateSkillTool())
    registry.register(DeleteSkillTool())

    return registry
