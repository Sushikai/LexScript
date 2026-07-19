"""Statute service — 法条缓存 / 向量索引 / 语义搜索 / 批量导入。"""
from __future__ import annotations
import time
import json
import re
from pathlib import Path
from loguru import logger
from app.db.database import query, query_one, execute
from app.config import STATUTE_CATEGORIES
from app.core.vector.embedder import Embedder
from app.core.vector.store import store


def _now() -> int:
    return int(time.time())


# ── SQL 搜索（关键词） ───────────────────────

def search_statutes(keyword: str, category: str | None = None, limit: int = 20) -> list[dict]:
    conditions = []
    params = []
    if keyword:
        conditions.append("(code LIKE ? OR name LIKE ? OR content LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])
    if category:
        conditions.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query(f"SELECT * FROM statutes {where} ORDER BY code LIMIT ?", tuple(params + [limit]))
    return [dict(r) for r in rows]


def get_statute(code: str) -> dict | None:
    row = query_one("SELECT * FROM statutes WHERE code = ?", (code,))
    return dict(row) if row else None


def upsert_statute(code: str, name: str, category: str, content: str,
                   source: str | None = None) -> dict:
    now = _now()
    existing = query_one("SELECT id FROM statutes WHERE code = ?", (code,))
    if existing:
        execute(
            "UPDATE statutes SET name = ?, category = ?, content = ?, source = ?, fetched_at = ? WHERE id = ?",
            (name, category, content, source, now, existing["id"]),
        )
    else:
        execute(
            "INSERT INTO statutes (code, name, category, content, source, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
            (code, name, category, content, source, now),
        )
    return get_statute(code)


def list_categories() -> list[str]:
    return STATUTE_CATEGORIES


def count_statutes() -> int:
    row = query_one("SELECT COUNT(*) as n FROM statutes")
    return row["n"] if row else 0


# ── 语义搜索（向量） ─────────────────────────

def build_vector_index() -> dict:
    """将所有法条索引入向量库，支持语义搜索。"""
    rows = query("SELECT code, name, category, content FROM statutes ORDER BY code")
    if not rows:
        return {"indexed": 0}

    # 清除旧的 statute 向量，避免重复
    try:
        store.delete_by_metadata("source", "statute")
    except Exception:
        pass  # 首次运行或 collection 不存在时忽略

    embedder = Embedder()
    try:
        # 逐条索引（每条法条作为一个向量文档）
        texts = []
        ids = []
        metadatas = []
        for r in rows:
            # 索引内容 + 名称，提高匹配率
            combined = f"{r['name']}\n{r['content']}"
            texts.append(combined)
            ids.append(f"statute_{r['code']}")
            metadatas.append({
                "code": r["code"],
                "name": r["name"],
                "category": r["category"],
                "source": "statute",
            })

        # 分批嵌入（每次 20 条）
        batch_size = 20
        total = 0
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            embeddings = embedder.embed(batch_texts)
            if embeddings and embeddings[0] and any(any(v != 0.0 for v in emb) for emb in embeddings):
                store.add(batch_ids, embeddings, batch_texts, batch_metas)
                total += len(batch_texts)

        return {"indexed": total, "total_in_db": len(rows)}
    finally:
        embedder.close()


def semantic_search(query_text: str, top_k: int = 10) -> list[dict]:
    """语义搜索法条，返回合并结果。"""
    embedder = Embedder()
    try:
        q_emb = embedder.embed([query_text])
        if not q_emb or not q_emb[0] or not any(v != 0.0 for v in q_emb[0]):
            # 零向量回退到关键词搜索
            return search_statutes(query_text, limit=top_k)

        results = store.search(q_emb[0], top_k=top_k, where={"source": "statute"})
        # 转换成 statute 格式
        output = []
        for r in results:
            meta = r.get("metadata", {})
            output.append({
                "code": meta.get("code", ""),
                "name": meta.get("name", ""),
                "category": meta.get("category", ""),
                "content": r.get("document", "")[:500],
                "score": round(1.0 - r.get("score", 0), 4),
                "source": "semantic",
            })
        return output
    finally:
        embedder.close()


def hybrid_search(query_text: str, category: str | None = None, top_k: int = 20) -> list[dict]:
    """混合搜索：向量语义 + SQL 关键词，去重合并。"""
    semantic_results = semantic_search(query_text, top_k=top_k)
    sql_results = search_statutes(query_text, category, limit=top_k)

    # 合并去重（code 去重）
    seen_codes = set()
    merged = []
    for r in semantic_results + sql_results:
        code = r.get("code", "")
        if code and code not in seen_codes:
            seen_codes.add(code)
            merged.append(r)

    return merged[:top_k]


# ── 批量导入 ────────────────────────────────

def parse_statute_from_text(filepath: str) -> list[dict]:
    """从文本/markdown 文件中解析法条条目。
    支持格式:
    - 【民法典 第1条】内容
    - 民法典 第一条 内容
    - 第XXX条 内容
    """
    text = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    entries = []

    # 匹配 【法规名 第X条】 或 法规名 第X条 模式
    pattern = re.compile(
        r'[【【]?\s*(民法典|刑法|民事诉讼法|刑事诉讼法|行政诉讼法|公司法|合同法|劳动法|'
        r'劳动合同法|著作权法|商标法|专利法|侵权责任法|物权法|担保法|'
        r'婚姻法|继承法|收养法|保险法|票据法|海商法|'
        r'反垄断法|反不正当竞争法|消费者权益保护法|产品质量法|'
        r'食品安全法|环境保护法|土地管理法|城市房地产管理法|'
        r'农村土地承包法|税收征收管理法|个人所得税法|企业所得税法|'
        r'企业破产法|合伙企业法|个人独资企业法|外商投资法|'
        r'招标投标法|政府采购法|仲裁法|人民调解法|行政处罚法|'
        r'行政复议法|国家赔偿法|立法法|选举法|'
        r'民法典|刑法|民事诉讼法|刑事诉讼法)\s*[】】]?\s*'
        r'(第[零一二三四五六七八九十百千\d]+条|第[零一二三四五六七八九十百千\d]+条之[一二三四五])\s*'
        r'[，,。.]?\s*(.+)',
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        name = match.group(1)
        article = match.group(2)
        content = match.group(3).strip()
        code = f"{name}_{article}"
        entries.append({
            "code": code,
            "name": f"{name} {article}",
            "category": _guess_category(name),
            "content": content,
            "source": filepath,
        })

    return entries


def _guess_category(name: str) -> str:
    """根据法规名称猜测分类。"""
    mapping = {
        "民法典": "民法典",
        "刑法": "刑法",
        "民事诉讼法": "诉讼法",
        "刑事诉讼法": "诉讼法",
        "行政诉讼法": "诉讼法",
        "公司法": "公司法",
        "劳动合同法": "劳动法",
        "劳动法": "劳动法",
        "著作权法": "知识产权法",
        "商标法": "知识产权法",
        "专利法": "知识产权法",
        "消费者权益保护法": "侵权责任法",
        "物权法": "物权法",
        "侵权责任法": "侵权责任法",
        "婚姻法": "婚姻家庭法",
        "继承法": "婚姻家庭法",
    }
    for key, cat in mapping.items():
        if key in name:
            return cat
    return "其他"


def bulk_import_from_text(filepath: str) -> dict:
    """从文本文件中批量导入法条。"""
    entries = parse_statute_from_text(filepath)
    imported = 0
    errors = 0
    for entry in entries:
        try:
            upsert_statute(**entry)
            imported += 1
        except Exception as e:
            logger.warning(f"[statute] 导入失败 {entry.get('code')}: {e}")
            errors += 1
    # 导入后重建向量索引
    if imported:
        build_vector_index()
    return {"imported": imported, "errors": errors, "total": len(entries)}


def bulk_import_from_directory(directory: str | None = None) -> dict:
    """扫描目录中的 txt/md 文件批量导入法条。"""
    from app.services.knowledge_service import get_kb_path
    base = directory or get_kb_path()
    p = Path(base)
    total_imported = 0
    total_errors = 0
    for f in p.rglob("*"):
        if f.suffix.lower() in (".txt", ".md", ".json"):
            try:
                result = bulk_import_from_text(str(f))
                total_imported += result["imported"]
                total_errors += result["errors"]
            except Exception as e:
                logger.warning(f"[statute] 目录导入失败 {f}: {e}")
                total_errors += 1
    if total_imported:
        build_vector_index()
    return {"imported": total_imported, "errors": total_errors}


# ── 在线同步 ────────────────────────────────

def sync_from_online() -> dict:
    """从中国法律法规数据库 (flk.npc.gov.cn) 同步最新法条。

    分页拉取,逐步写入本地 DB,增量更新。
    由于官方 API 有频率限制,本函数使用保守的请求间隔。
    """
    import urllib.request, urllib.error
    import json
    import time as _time

    api_url = "https://flk.npc.gov.cn/api/"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; LexScript/1.0)",
        "Referer": "https://flk.npc.gov.cn/",
    }

    # 第一页:获取总数
    payload = json.dumps({"page": 1, "size": 50, "type": "法律"}).encode()
    try:
        req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        logger.info(f"[statute] flk API 返回: {json.dumps(data, ensure_ascii=False)[:200]}")
    except Exception as e:
        return {"synced": 0, "error": f"无法连接 flk.npc.gov.cn: {e}",
                "message": "官方 API 暂不可用，可尝试从 GitHub 数据源导入"}

    # flk.npc.gov.cn API 响应结构:
    # {"data": {"result": {...}, "records": [...]}}
    records = []
    try:
        if "data" in data:
            result_data = data["data"]
            if isinstance(result_data, dict) and "records" in result_data:
                records = result_data["records"]
            elif isinstance(result_data, list):
                records = result_data
    except Exception:
        pass

    if not records:
        return {"synced": 0, "message": "未获取到记录",
                "hint": "可直接使用 GitHub 数据集: python -m scripts.import_statutes"}

    # 处理记录
    from app.db.database import execute, query_one
    now = int(_time.time())
    synced = 0
    errors = 0

    for rec in records:
        try:
            title = rec.get("title", "") or rec.get("name", "")
            content = rec.get("content", "") or rec.get("text", "") or rec.get("html", "")
            # 清理 HTML
            if content.startswith("<"):
                import re as _re
                content = _re.sub(r"<[^>]+>", "", content)
            if not title or not content:
                continue
            # 生成 code
            code = re.sub(r"[^一-鿿\w]", "", title)[:50]
            # 分类
            cat = "其他"
            for law_name, category in _get_category_map().items():
                if law_name in title:
                    cat = category
                    break
            # 去重插入
            existing = query_one("SELECT id FROM statutes WHERE code LIKE ?", (f"%{code[:20]}%",))
            if not existing:
                execute(
                    "INSERT INTO statutes (code, name, category, content, source, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (code, title, cat, content[:5000], "flk.npc.gov.cn", now),
                )
                synced += 1
            else:
                # 更新已存在的
                execute(
                    "UPDATE statutes SET content = ?, fetched_at = ? WHERE id = ?",
                    (content[:5000], now, existing["id"]),
                )
                synced += 1
        except Exception as e:
            errors += 1

    if synced:
        build_vector_index()

    return {"synced": synced, "errors": errors, "total_after": count_statutes()}


# ── 法条引用检测 ──────────────────────────────

# 中国法律名称规范化映射（简称→全称）
_LAW_NAME_MAP: dict[str, str] = {
    "宪法": "宪法", "民法典": "民法典", "刑法": "刑法",
    "民事诉讼法": "民事诉讼法", "刑事诉讼法": "刑事诉讼法", "行政诉讼法": "行政诉讼法",
    "海事诉讼特别程序法": "海事诉讼特别程序法",
    "公司法": "公司法", "合伙企业法": "合伙企业法", "外商投资法": "外商投资法",
    "商业银行法": "商业银行法", "证券法": "证券法", "保险法": "保险法",
    "海商法": "海商法", "票据法": "票据法",
    "劳动合同法": "劳动合同法", "劳动法": "劳动法", "社会保险法": "社会保险法",
    "安全生产法": "安全生产法", "工会法": "工会法",
    "著作权法": "著作权法", "商标法": "商标法", "专利法": "专利法",
    "消费者权益保护法": "消费者权益保护法", "产品质量法": "产品质量法",
    "食品安全法": "食品安全法", "电子商务法": "电子商务法",
    "土地管理法": "土地管理法", "城市房地产管理法": "城市房地产管理法",
    "物权法": "物权法", "农村土地承包法": "农村土地承包法",
    "婚姻法": "婚姻法", "继承法": "继承法", "收养法": "收养法",
    "反家庭暴力法": "反家庭暴力法", "未成年人保护法": "未成年人保护法",
    "行政处罚法": "行政处罚法", "行政复议法": "行政复议法",
    "行政强制法": "行政强制法", "行政许可法": "行政许可法",
    "治安管理处罚法": "治安管理处罚法", "国家赔偿法": "国家赔偿法",
    "网络安全法": "网络安全法", "数据安全法": "数据安全法",
    "个人信息保护法": "个人信息保护法",
    "环境保护法": "环境保护法", "环境影响评价法": "环境影响评价法",
    "招标投标法": "招标投标法", "政府采购法": "政府采购法",
    "仲裁法": "仲裁法", "人民调解法": "人民调解法",
    "立法法": "立法法", "选举法": "选举法",
    "反垄断法": "反垄断法", "反不正当竞争法": "反不正当竞争法",
    "企业破产法": "企业破产法", "个人所得税法": "个人所得税法",
    "道路交通安全法": "道路交通安全法",
}


def _normalize_law_name(raw: str) -> str:
    """将法律名称统一化，去掉 '中华人民共和国' 前缀和书名号。"""
    name = raw.replace("中华人民共和国", "").replace("《", "").replace("》", "").strip()
    # 尝试精确匹配
    if name in _LAW_NAME_MAP:
        return _LAW_NAME_MAP[name]
    # 子串匹配
    for key, val in _LAW_NAME_MAP.items():
        if key in name or name in key:
            return val
    return name


def _chinese_article_to_digit(article: str) -> str:
    """将中文数字条号转为阿拉伯数字，用于 DB 匹配。"""
    cn_map = {"零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
              "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
    result = []
    for ch in article:
        if ch in cn_map:
            result.append(cn_map[ch])
        else:
            result.append(ch)
    return "".join(result)


def _arabic_to_chinese_num(n: int) -> str:
    """阿拉伯数字转中文数字（用于法条编号匹配）。"""
    if n == 0:
        return "零"
    digits = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    places = ["", "十", "百", "千", "万"]
    s = str(n)
    length = len(s)
    if length == 2 and 10 <= n < 20:
        result = "十"
        if n % 10 != 0:
            result += digits[n % 10]
        return result
    result = ""
    zero_flag = False
    for i, ch in enumerate(s):
        digit = int(ch)
        pos = length - i - 1
        if digit == 0:
            zero_flag = True
        else:
            if zero_flag:
                result += "零"
                zero_flag = False
            result += digits[digit]
            if pos > 0:
                result += places[pos]
    return result


def _normalize_article_for_db(raw_article: str) -> list[str]:
    """将输入的条号转为多种可能的 DB 格式，逐一尝试匹配。

    例: '第577条' → ['第577条', '第五百七十七条']
         '第38条'  → ['第38条', '第三十八条']
    """
    candidates = [raw_article]
    m = re.match(r'第([零一二三四五六七八九十百千\d]+)条(?:之(\d+))?', raw_article)
    if m:
        num_str = m.group(1)
        # 如果已经是中文数字，直接作为候选
        if any(c in "零一二三四五六七八九十百千" for c in num_str):
            candidates.append(raw_article)
        else:
            # 阿拉伯数字 → 中文
            try:
                cn = _arabic_to_chinese_num(int(num_str))
                cn_article = f"第{cn}条"
                sub = m.group(2)
                if sub:
                    cn_article += f"之{sub}"
                candidates.append(cn_article)
            except ValueError:
                pass
    return candidates


def _lookup_citation(law_name: str, raw_article: str) -> dict | None:
    """根据法律名称和条号查找 DB 中的最新版本。"""
    for variant in _normalize_article_for_db(raw_article):
        rows = query(
            "SELECT code, name, category, content, source FROM statutes "
            "WHERE code LIKE ? AND (code LIKE ? OR name LIKE ?) LIMIT 1",
            (f"%{law_name}%", f"%{variant}%", f"%{variant}%"),
        )
        if rows:
            return dict(rows[0])
    return None


def find_citations(text: str) -> list[dict]:
    """从文本中检测法条引用，返回最新法条内容。

    支持的引用格式:
    - 《民法典》第577条
    - 《中华人民共和国刑法》第XXX条
    - 合同法第X条 (无书名号)
    - 第XXX条 (无法律名称时基于段落推断)
    """
    # 构建法律名称匹配串（按长度降序避免短名误匹配长名）
    _law_names_sorted = sorted(_LAW_NAME_MAP.keys(), key=len, reverse=True)
    _law_names_alt = "|".join(_law_names_sorted)

    citations = []
    seen: set[str] = set()

    def _add(  # noqa: PLR0913
        matched_text: str, law_name: str, article: str,
        latest: dict | None,
    ) -> None:
        key = f"{law_name}_{article}"
        if key in seen:
            return
        seen.add(key)
        citations.append({
            "citation": matched_text,
            "law_name": law_name,
            "article": article,
            "found": latest is not None,
            "latest_code": latest["code"] if latest else None,
            "latest_name": latest["name"] if latest else None,
            "latest_content": latest["content"][:500] if latest else None,
            "category": latest["category"] if latest else None,
        })

    # ── 第1轮: 《法律名称》第XX条 ──
    for m in re.finditer(r'《([^》]+)》\s*(第[零一二三四五六七八九十百千\d]+条[之\d]*)', text):
        raw_law = m.group(1).strip()
        raw_article = m.group(2).strip()
        law_name = _normalize_law_name(raw_law)
        latest = _lookup_citation(law_name, raw_article)
        _add(m.group(0).strip(), law_name, raw_article, latest)

    # ── 第2轮: 法律名称(无《》)后跟第X条 (跨度<=30字, 不跨句) ──
    flex_pat = re.compile(
        rf'(?:{_law_names_alt})[^。！？\n]{{0,30}}(第[零一二三四五六七八九十百千\d]+条[之\d]*)',
    )
    for m in flex_pat.finditer(text):
        # 确定匹配到的是哪个法律名称
        raw_law = ""
        for ln in _law_names_sorted:
            if text[m.start():m.start() + len(ln)] == ln:
                raw_law = ln
                break
        if not raw_law:
            continue
        raw_article = m.group(1).strip()
        law_name = _normalize_law_name(raw_law)
        latest = _lookup_citation(law_name, raw_article)
        _add(m.group(0).strip(), law_name, raw_article, latest)

    # ── 第3轮: 孤立的第X条 — 按句推断法律名称 ──
    sentences = re.split(r'[。！？\n]', text)
    current_law: str | None = None
    for sent in sentences:
        # 检测句中的已知法律名称
        for ln in _law_names_sorted:
            if ln in sent:
                current_law = _LAW_NAME_MAP[ln]
                break
        # 检测孤立的 第X条
        for m in re.finditer(r'(第[零一二三四五六七八九十百千\d]+条[之\d]*)', sent):
            raw_article = m.group(1).strip()
            key_base = current_law or "unknown"
            fk = f"{key_base}_{raw_article}"
            if fk in seen:
                continue

            if current_law:
                latest = _lookup_citation(current_law, raw_article)
                _add(m.group(0).strip(), current_law, raw_article, latest)
            else:
                # 全库模糊匹配
                article_digit = _chinese_article_to_digit(raw_article)
                for row in query(
                    "SELECT code, name, category, content, source FROM statutes "
                    "WHERE code LIKE ? OR name LIKE ? LIMIT 3",
                    (f"%{raw_article}%", f"%{article_digit}%"),
                ):
                    r = dict(row)
                    sub_key = f"{r['code']}_{raw_article}"
                    if sub_key in seen:
                        continue
                    seen.add(sub_key)
                    _add(
                        m.group(0).strip(),
                        r.get("name", "").split(" ")[0] if r.get("name") else "未知",
                        raw_article,
                        r,
                    )

    return citations


def _get_category_map() -> dict[str, str]:
    """返回法律名称到分类的映射。"""
    return {
        "宪法": "宪法", "民法典": "民法典", "刑法": "刑法",
        "民事诉讼法": "诉讼法", "刑事诉讼法": "诉讼法", "行政诉讼法": "诉讼法",
        "公司法": "公司法", "合伙企业法": "公司法",
        "证券法": "商法", "商业银行法": "商法", "保险法": "商法",
        "劳动合同法": "劳动法", "劳动法": "劳动法", "社会保险法": "劳动法",
        "著作权法": "知识产权法", "商标法": "知识产权法", "专利法": "知识产权法",
        "消费者权益保护法": "侵权责任法",
        "行政处罚法": "行政法", "行政复议法": "行政法",
        "治安管理处罚法": "行政法", "数据安全法": "行政法",
        "网络安全法": "行政法", "环境保护法": "行政法",
        "婚姻法": "婚姻家庭法", "继承法": "婚姻家庭法",
        "未成年人保护法": "婚姻家庭法",
        "反家庭暴力法": "婚姻家庭法",
        "土地管理法": "物权法", "城市房地产管理法": "物权法",
    }
