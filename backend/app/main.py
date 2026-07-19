"""
Legal SaaS · FastAPI 入口
绑定 0.0.0.0:7800,支持局域网 + 公网隧道访问。
"""
from __future__ import annotations
import socket
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import HOST, PORT, DEBUG
from app.core.logger import get_logger
from app.core.exceptions import BusinessError, business_error_handler
from app.core.tunnel import get_public_url
from app.core.agent.init_tools import register_all_tools
from app.db.database import init_schema
import threading

log = get_logger()

BACKEND_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BACKEND_DIR / "app" / "web" / "static"
MIGRATIONS_DIR = BACKEND_DIR / "app" / "db" / "migrations"

app = FastAPI(
    title="牍知库 · 本地私有化案件智能分析与文书生成平台",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    """为所有响应添加安全头。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # CSP: 允许 self + inline style(前端框架需要) + data: URI(图片)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self' *; "
        "font-src 'self' data:; "
    )
    return response


app.add_exception_handler(BusinessError, business_error_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """全局未捕获异常处理 — 统一 JSON 错误响应。"""
    log.error(f"[unhandled] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"ok": False, "code": "INTERNAL_ERROR", "message": str(exc)},
    )


# ── 模块级注册路由(必须在 SPA fallback 之前) ──
def _register_routes_module():
    import importlib
    from app.api.v1 import router as v1_router

    # 模块列表: (module_path, sub_prefix)
    _modules = [
        "app.api.v1.config",
        "app.api.v1.auth",
        "app.api.v1.chat",
        "app.api.v1.files",
        "app.api.v1.search",
        "app.api.v1.documents",
        "app.api.v1.templates",
        "app.api.v1.statutes",
        "app.api.v1.tasks",
        "app.api.v1.logs",
        "app.api.v1.agent_chat",
        "app.api.v1.knowledge",
        "app.api.v1.legal_skills",
    ]
    for mod_path in _modules:
        mod = importlib.import_module(mod_path)
        if hasattr(mod, "router"):
            v1_router.include_router(mod.router)

    app.include_router(v1_router)
    log.info("[module] ✓ 全部路由注册: /api/v1/* (config/auth/chat/files/search/documents/templates/statutes/tasks/logs)")


_register_routes_module()


@app.on_event("startup")
def _startup():
    log.info(f"[startup] init schema: {MIGRATIONS_DIR}")
    init_schema(MIGRATIONS_DIR)
    log.info(f"[startup] ✓ 15 表就绪(12 + users + auth_tokens + login_attempts)")
    # 预埋:首次启动自动建 root/123456 + root2/123456
    from app.services.user_service import ensure_default_admin
    users = ensure_default_admin()
    if users:
        for u in users:
            log.warning(f"[startup] ✓ 默认用户已创建 · username={u['username']} password=123456")
        log.warning(f"[startup]   ⚠️  两个用户数据完全隔离,请登录后立即修改默认密码!")
    # 注册 Agent Tools
    register_all_tools()
    log.info(f"[startup] ✓ Agent Tools 已注册")

    # 启动知识库:导入已有文件 + 后台自动 REG 工程化 + 开启文件监控
    from app.services.knowledge_service import import_all_kb_files, reg_all_pending, start_watcher, recover_stale_indexing, seed_watcher_seen

    # 恢复卡住的文件（系统崩溃后重新索引）
    recover_stale_indexing()
    log.info(f"[startup] ✓ 卡住状态文件已恢复")

    imported = import_all_kb_files()
    log.info(f"[startup] ✓ 知识库扫描完成, 导入 {len(imported)} 个文件")

    # 预填充 watcher seen 字典（避免启动时重复 REG）
    seed_watcher_seen()

    # 后台线程对所有 pending 文件执行 REG(解析→分片→向量索引)
    def _background_reg():
        log.info("[startup]   ↳ 后台 REG 工程化开始...")
        results = reg_all_pending()
        ok = sum(1 for r in results if r.get("status") == "indexed")
        fail = sum(1 for r in results if r.get("status") == "failed")
        log.info(f"[startup]   ↳ 后台 REG 工程化完成: {ok} 成功, {fail} 失败")
        if fail:
            for r in results:
                if r.get("status") == "failed":
                    log.warning(f"[startup]   ↳ REG 失败 file_id={r.get('file_id')}: {r.get('error')}")

    threading.Thread(target=_background_reg, daemon=True).start()

    start_watcher()
    log.info(f"[startup] ✓ 知识库文件监控已启动 (间隔 5s)")

    # 自动填充通用法律条文（首次启动时 statutes 表为空则自动导入）
    from app.db.database import query_one as _q1
    count_row = _q1("SELECT count(*) as cnt FROM statutes")
    if count_row and count_row["cnt"] == 0:
        log.info("[startup]   ↳ statutes 表为空, 自动导入通用法律种子数据...")
        from app.core.legal_statutes import STATUTE_SEED_DATA
        from app.db.database import execute as _ex
        now = int(__import__("time").time())
        for _code, _data in STATUTE_SEED_DATA.items():
            _ex(
                "INSERT INTO statutes (code, name, category, content, source, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (_code, _data["name"], _data["category"], _data["content"], "seed_builtin", now),
            )
        log.info(f"[startup]   ↳ ✓ 已导入 {len(STATUTE_SEED_DATA)} 条通用法律条文")

    # 后台自动向量索引 statutes（启动时始终执行一次）
    def _auto_index_statutes():
        from app.services.statute_service import build_vector_index as _bvi
        result = _bvi()
        log.info(f"[startup]   ↳ 法条向量索引: {result.get('indexed', 0)} 条")

    threading.Thread(target=_auto_index_statutes, daemon=True).start()


# ═══════════════════════════════════════════════════
# 核心 API
# ═══════════════════════════════════════════════════
@app.get("/api/v1/health")
def health():
    """健康检查 + DB 状态。"""
    from app.db.database import query_one
    db_ok = False
    try:
        row = query_one("SELECT count(*) as cnt FROM system_config")
        db_ok = row is not None
    except Exception:
        pass
    return {
        "ok": True,
        "service": "LexScript",
        "version": "0.1.0",
        "db": "ok" if db_ok else "error",
    }


@app.get("/api/v1/info")
def info():
    """返回 server 自身信息(含 LAN IP + 公网隧道,前端展示用)。"""
    lan_ip = _get_lan_ip()
    tunnel = get_public_url()
    return {
        "ok": True,
        "service": "LexScript",
        "version": "0.1.0",
        "host": HOST,
        "port": PORT,
        "lan_ip": lan_ip,
        "lan_url": f"http://{lan_ip}:{PORT}" if lan_ip else None,
        "local_url": f"http://127.0.0.1:{PORT}",
        "tunnel_url": tunnel,
    }


def _get_lan_ip() -> str | None:
    """探测本机局域网 IP(非 127.0.0.1)。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("223.5.5.5", 80))  # 阿里 DNS,不发包只取路由
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# 静态前端 + SPA fallback
# ═══════════════════════════════════════════════════
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return HTMLResponse("<h1>Legal SaaS</h1><p>前端未构建</p>")
else:
    @app.get("/", response_class=HTMLResponse)
    def root_inline():
        return HTMLResponse(INLINE_INDEX_HTML)


# 简易 SPA fallback
@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    if path.startswith("api/") or path.startswith("static/"):
        return JSONResponse({"ok": False, "code": "NOT_FOUND", "message": path}, status_code=404)
    if STATIC_DIR.exists():
        candidate = STATIC_DIR / path
        if candidate.is_file():
            return FileResponse(str(candidate))
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return HTMLResponse(INLINE_INDEX_HTML)


INLINE_INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Legal SaaS · 本地法律 AI 文书生成平台</title>
<style>
:root {
  --bg: #0f1419;
  --bg-elev: #1a2028;
  --bg-card: #232b35;
  --border: #2d3748;
  --text: #e5e7eb;
  --text-muted: #9ca3af;
  --primary: #1e3a8a;
  --primary-glow: #3b82f6;
  --accent: #b91c1c;
  --success: #10b981;
  --radius: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
.app { max-width: 1200px; margin: 0 auto; padding: 24px; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; background: var(--bg-elev);
  border-bottom: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 24px;
}
.brand {
  display: flex; align-items: center; gap: 12px;
  font-size: 20px; font-weight: 700; letter-spacing: 0.5px;
}
.brand-icon {
  width: 36px; height: 36px; border-radius: 8px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: white;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 8px var(--success); }
.status { display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 13px; }
.hero {
  text-align: center; padding: 48px 24px;
  background: linear-gradient(180deg, var(--bg-elev) 0%, var(--bg) 100%);
  border-radius: var(--radius); border: 1px solid var(--border);
  margin-bottom: 24px;
}
.hero h1 { font-size: 36px; margin-bottom: 12px; background: linear-gradient(90deg, var(--primary-glow), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hero p { color: var(--text-muted); font-size: 16px; max-width: 600px; margin: 0 auto; line-height: 1.7; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px;
  transition: all 0.2s;
}
.card:hover { border-color: var(--primary-glow); transform: translateY(-2px); }
.card-icon { font-size: 24px; margin-bottom: 12px; }
.card-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.card-desc { color: var(--text-muted); font-size: 13px; line-height: 1.6; }
.access {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px; margin-bottom: 24px;
}
.access h3 { font-size: 16px; margin-bottom: 12px; color: var(--primary-glow); }
.url-list { display: flex; flex-direction: column; gap: 8px; }
.url-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: var(--bg);
  border-radius: 6px; font-family: ui-monospace, "SF Mono", monospace;
  font-size: 13px;
}
.url-row a { color: var(--primary-glow); text-decoration: none; }
.url-row a:hover { text-decoration: underline; }
.copy-btn {
  padding: 4px 10px; background: var(--primary); color: white;
  border: none; border-radius: 4px; font-size: 12px; cursor: pointer;
}
.copy-btn:hover { background: var(--primary-glow); }
.footer { text-align: center; padding: 24px; color: var(--text-muted); font-size: 12px; border-top: 1px solid var(--border); margin-top: 24px; }
.tag { display: inline-block; padding: 2px 8px; background: var(--primary); color: white; border-radius: 4px; font-size: 11px; margin-left: 8px; }
.progress-section { margin-top: 16px; }
.progress-bar { height: 6px; background: var(--bg); border-radius: 3px; overflow: hidden; margin-top: 8px; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--primary-glow), var(--accent)); transition: width 0.3s; }
@media (max-width: 640px) {
  .app { padding: 12px; }
  .hero h1 { font-size: 24px; }
  .hero { padding: 24px 16px; }
}
</style>
</head>
<body>
<div class="app">
  <div class="topbar">
    <div class="brand">
      <div class="brand-icon">⚖</div>
      <span>Legal SaaS</span>
      <span class="tag">v0.1.0</span>
    </div>
    <div class="status">
      <span class="status-dot"></span>
      <span>运行中</span>
    </div>
  </div>

  <div class="hero">
    <h1>本地私有化法律 AI 智能文书生成平台</h1>
    <p>MiniMax 驱动 · 百 MB 卷宗检索 · 一键案稿生成 · 法条联动 · 全离线运行</p>
  </div>

  <div class="access" id="access">
    <h3>🌐 访问入口</h3>
    <div class="url-list" id="url-list">
      <div class="url-row">
        <span>加载中...</span>
      </div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-icon">📁</div>
      <div class="card-title">本地卷宗管理</div>
      <div class="card-desc">PDF / Word / Excel / 图片 OCR 全格式解析,百 MB 不阻塞分片索引</div>
    </div>
    <div class="card">
      <div class="card-icon">💬</div>
      <div class="card-title">AI 多角色对话</div>
      <div class="card-desc">法律专家 / 诉讼律师 / 企业法务 / 合同专员 四角色,SSE 流式输出</div>
    </div>
    <div class="card">
      <div class="card-icon">📝</div>
      <div class="card-title">一键案件稿生成</div>
      <div class="card-desc">读卷宗 → 向量检索 → 法条匹配 → AI 历史避错 → 生成</div>
    </div>
    <div class="card">
      <div class="card-icon">⚖️</div>
      <div class="card-title">法条联动</div>
      <div class="card-desc">文书自动标注法条来源,司法解释、指导案例联动匹配</div>
    </div>
    <div class="card">
      <div class="card-icon">📋</div>
      <div class="card-title">模板库</div>
      <div class="card-desc">起诉状 / 答辩状 / 代理词 / 合同 / 律师函 · 内置变量动态渲染</div>
    </div>
    <div class="card">
      <div class="card-icon">🔒</div>
      <div class="card-title">本地加密存储</div>
      <div class="card-desc">API Key Fernet 加密,数据不出本机,SQLite WAL 高并发</div>
    </div>
  </div>

  <div class="card" style="margin-bottom: 24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;">
      <div>
        <div class="card-title">🚧 建设进度</div>
        <div class="card-desc">Phase 1 骨架已就位,核心模块与正式 UI 持续推进中</div>
      </div>
      <div style="color: var(--primary-glow); font-weight: 600;" id="progress-text">25%</div>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill" style="width: 25%;"></div></div>
  </div>

  <div class="footer">
    Powered by MiniMax · FastAPI · SQLite WAL · ChromaDB · Vue3 · Local-first
  </div>
</div>

<script>
async function loadInfo() {
  try {
    const r = await fetch('/api/v1/info');
    const data = await r.json();
    const list = document.getElementById('url-list');
    list.innerHTML = '';
    const urls = [
      { label: '本机访问', url: data.local_url, primary: false },
      { label: '局域网 (电脑/手机同 WiFi)', url: data.lan_url, primary: true },
    ];
    if (data.tunnel_url) {
      urls.push({ label: '公网隧道 (任意网络)', url: data.tunnel_url, primary: true });
    }
    for (const u of urls) {
      const row = document.createElement('div');
      row.className = 'url-row';
      row.innerHTML = `
        <span><b style="color:${u.primary ? 'var(--primary-glow)' : 'var(--text-muted)'}">${u.label}</b> · <a href="${u.url}" target="_blank">${u.url}</a></span>
        <button class="copy-btn" onclick="navigator.clipboard.writeText('${u.url}');this.textContent='已复制 ✓';setTimeout(()=>this.textContent='复制',1500)">复制</button>
      `;
      list.appendChild(row);
    }
  } catch (e) {
    document.getElementById('url-list').innerHTML = '<div class="url-row"><span style="color:var(--accent)">⚠ 无法连接后端</span></div>';
  }
}
loadInfo();
setInterval(loadInfo, 30000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    log.info(f"[main] 启动 牍知库 · http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG, log_level="info")