"""
批量导入最新法条数据 —— 从 Chinese-Laws-folk 数据集导入。
支持多种格式: clause-by-clause / structured articles / mixed
"""
from __future__ import annotations
import os, sys, re, json, time, urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("LEGAL_DATA_DIR", str(BACKEND_DIR / "data"))

# ── 法律分类映射 ──
LAW_CATEGORY: dict[str, str] = {
    "宪法": "宪法", "民法典": "民法典", "刑法": "刑法",
    "民事诉讼法": "诉讼法", "刑事诉讼法": "诉讼法", "行政诉讼法": "诉讼法",
    "海事诉讼特别程序法": "诉讼法", "引渡法": "诉讼法",
    "公司法": "公司法", "合伙企业法": "公司法", "外商投资法": "公司法",
    "商业银行法": "商法", "证券法": "商法", "证券投资基金法": "商法",
    "票据法": "商法", "保险法": "商法", "海商法": "商法",
    "期货和衍生品法": "商法", "招标投标法": "商法", "拍卖法": "商法",
    "劳动合同法": "劳动法", "劳动法": "劳动法", "就业促进法": "劳动法",
    "社会保险法": "劳动法", "安全生产法": "劳动法", "职业病防治法": "劳动法",
    "工会法": "劳动法", "劳动争议调解仲裁法": "劳动法",
    "著作权法": "知识产权法", "商标法": "知识产权法", "专利法": "知识产权法",
    "消费者权益保护法": "侵权责任法", "产品质量法": "侵权责任法",
    "食品安全法": "侵权责任法", "药品管理法": "侵权责任法",
    "广告法": "侵权责任法", "电子商务法": "侵权责任法",
    "土地管理法": "物权法", "城市房地产管理法": "物权法",
    "农村土地承包法": "物权法", "物权法": "物权法",
    "婚姻法": "婚姻家庭法", "继承法": "婚姻家庭法", "收养法": "婚姻家庭法",
    "反家庭暴力法": "婚姻家庭法", "未成年人保护法": "婚姻家庭法",
    "预防未成年人犯罪法": "婚姻家庭法", "老年人权益保障法": "婚姻家庭法",
    "妇女权益保障法": "婚姻家庭法", "家庭教育促进法": "婚姻家庭法",
    "残疾人保障法": "婚姻家庭法",
    "行政处罚法": "行政法", "行政复议法": "行政法", "行政强制法": "行政法",
    "行政许可法": "行政法", "治安管理处罚法": "行政法", "国家赔偿法": "行政法",
    "道路交通安全法": "行政法", "律师法": "行政法", "公证法": "行政法",
    "法律援助法": "行政法", "监察法": "行政法", "公务员法": "行政法",
    "环境保护法": "行政法", "环境影响评价法": "行政法",
    "海洋环境保护法": "行政法", "大气污染防治法": "行政法",
    "水污染防治法": "行政法", "噪声污染防治法": "行政法",
    "固体废物污染环境防治法": "行政法", "土壤污染防治法": "行政法",
    "放射性污染防治法": "行政法", "湿地保护法": "行政法",
    "长江保护法": "行政法", "黄河保护法": "行政法", "青藏高原生态保护法": "行政法",
    "黑土地保护法": "行政法", "防沙治沙法": "行政法",
    "环境保护税法": "行政法", "数据安全法": "行政法", "网络安全法": "行政法",
    "个人信息保护法": "行政法", "密码法": "行政法", "消防法": "行政法",
    "禁毒法": "行政法", "社区矫正法": "行政法",
    "反电信网络诈骗法": "行政法", "反有组织犯罪法": "行政法",
    "反间谍法": "行政法", "反恐怖主义法": "行政法", "反洗钱法": "行政法",
    "突发事件应对法": "行政法", "预备役人员法": "行政法",
    "国防教育法": "行政法", "国防动员法": "行政法", "国防交通法": "行政法",
    "现役军官法": "行政法", "海警法": "行政法", "监狱法": "行政法",
    "枪支管理法": "行政法", "境外非政府组织境内活动管理法": "行政法",
    "国家情报法": "行政法", "国际刑事司法协助法": "行政法", "海关法": "行政法",
    "国境卫生检疫法": "行政法", "进出境动植物检疫法": "行政法",
    "进出口商品检验法": "行政法", "税收征收管理法": "行政法",
    "个人所得税法": "行政法", "企业所得税法": "行政法", "增值税法": "行政法",
    "契税法": "行政法", "资源税法": "行政法", "车船税法": "行政法",
    "车辆购置税法": "行政法", "船舶吨税法": "行政法", "耕地占用税法": "行政法",
    "烟叶税法": "行政法", "城市维护建设税法": "行政法",
    "审计法": "行政法", "统计法": "行政法", "反食品浪费法": "行政法",
    "教育法": "其他", "高等教育法": "其他", "职业教育法": "其他",
    "教师法": "其他", "民办教育促进法": "其他", "学位法": "其他",
    "科学技术进步法": "其他", "科学技术普及法": "其他", "文物保护法": "其他",
    "非物质文化遗产法": "其他", "国家通用语言文字法": "其他",
    "旅游法": "其他", "基本医疗卫生与健康促进法": "其他",
    "精神卫生法": "其他", "献血法": "其他", "母婴保健法": "其他",
    "疫苗管理法": "其他",  "中医药法": "其他",
    "粮食安全保障法": "其他", "畜牧法": "其他", "渔业法": "其他",
    "草原法": "其他", "森林法": "其他", "野生动物保护法": "其他",
    "种子法": "其他", "水法": "其他", "水土保持法": "其他",
    "防洪法": "其他", "防震减灾法": "其他",
    "电力法": "其他", "煤炭法": "其他", "矿产资源法": "其他",
    "矿山安全法": "其他", "节约能源法": "其他", "可再生能源法": "其他",
    "核安全法": "其他", "石油天然气管道保护法": "其他",
    "特种设备安全法": "其他", "标准化法": "其他", "计量法": "其他",
    "测绘法": "其他", "建筑法": "其他", "城乡规划法": "其他",
    "清洁生产促进法": "其他", "循环经济促进法": "其他",
    "慈善法": "其他", "红十字会法": "其他",
    "退役军人保障法": "其他", "居民身份证法": "其他",
    "护照法": "其他", "驻外外交人员法": "其他",
    "深海海底区域资源勘探开发法": "其他", "海南自由贸易港法": "其他",
    "无障碍环境建设法": "其他",
    "消防救援衔条例": "其他", "公安机关组织管理条例": "其他",
    "海上交通安全法": "其他", "港口法": "其他", "航道法": "其他",
    "铁路法": "其他", "民用航空法": "其他", "邮政法": "其他",
    "烟草专卖法": "其他", "银行业监督管理法": "其他", "资产评估法": "其他",
    "注册会计师法": "其他", "海域使用管理法": "其他", "海岛保护法": "其他",
    "对外贸易法": "其他", "生物安全法": "其他",
    "电子签名法": "其他", "电影产业促进法": "其他", "气象法": "其他",
    "人民调解法": "其他", "法律援助法": "其他",
}

# 正则回退规则
FALLBACK_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"税|税务|税收"), "行政法"),
    (re.compile(r"安全|矿山|生产|质量|标准|计量|测绘"), "行政法"),
    (re.compile(r"教育|教师|学位|文化|体育|科技|文物"), "其他"),
    (re.compile(r"环境|污染|生态|湿地|水土|草原|森林|野生动|矿产|煤炭|电力|能源|核安全"), "行政法"),
    (re.compile(r"食品|药品|医疗|卫生|献血|母婴|精神|疫苗|中医药|健康|保健"), "侵权责任法"),
    (re.compile(r"交通|道路|铁路|航空|港口|航道|邮政"), "行政法"),
    (re.compile(r"网络|数据|信息|密码"), "行政法"),
    (re.compile(r"劳动|就业|社保"), "劳动法"),
    (re.compile(r"婚姻|家庭|妇女|未成年|老年|残疾|收养"), "婚姻家庭法"),
    (re.compile(r"合同|拍卖|招投标"), "商法"),
    (re.compile(r"证券|银行|保险|信托|票据|期货"), "商法"),
    (re.compile(r"商标|专利|著作"), "知识产权法"),
    (re.compile(r"消费者|产品|广告|电子商务"), "侵权责任法"),
]


def guess_category(law_name: str) -> str:
    """根据法律名称猜测分类。"""
    name = law_name.replace("中华人民共和国", "")
    for key, cat in LAW_CATEGORY.items():
        if key in name:
            return cat
    for pattern, cat in FALLBACK_RULES:
        if pattern.search(name):
            return cat
    return "其他"


def parse_clause_format(text: str, law_name: str) -> list[dict]:
    """解析 clause-by-clause 格式: 《法律名称》第XX条规定，..."""
    clauses = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"《(.+?)》(第[零一二三四五六七八九十百千\d]+条[之\d]*)(?:规定)?[，,。\.\s]*(.*)", line)
        if m:
            full_name = m.group(1)
            article = m.group(2)
            rest = m.group(3).strip()
            short = full_name.replace("中华人民共和国", "")
            code = f"{short}-{article}"
            clauses.append({
                "code": code,
                "name": f"{full_name} {article}",
                "category": guess_category(full_name),
                "content": f"{article} {rest}" if rest else article,
            })
    return clauses


def parse_structured_articles(text: str, law_name: str) -> list[dict]:
    """解析结构化公文格式: 第XX条 ..."""
    articles = []
    # 尝试匹配 "第XX条" 在行首
    pattern = re.compile(r"^\s*(第[零一二三四五六七八九十百千\d]+条[之\d]*)\s+(.+?)$", re.MULTILINE)
    for m in pattern.finditer(text):
        article = m.group(1)
        content = m.group(2).strip()
        short = law_name.replace("中华人民共和国", "").replace(".txt", "")
        code = f"{short}-{article}"
        articles.append({
            "code": code,
            "name": f"{law_name.replace('.txt', '')} {article}",
            "category": guess_category(law_name),
            "content": f"{article} {content}",
        })
    return articles


def parse_law_file(text: str, fname: str) -> list[dict]:
    """智能解析法律文件，自动尝试多种格式。"""
    # 去掉 extension
    law_name = fname.replace(".txt", "")

    # 尝试 clause-by-clause 格式
    clauses = parse_clause_format(text, law_name)
    if len(clauses) > 5:
        return clauses

    # 尝试结构化文章格式
    articles = parse_structured_articles(text, law_name)
    if len(articles) > 5:
        return articles

    # 回退：将整个文件作为一个条目
    return [{
        "code": law_name.replace("中华人民共和国", ""),
        "name": law_name,
        "category": guess_category(law_name),
        "content": text.strip()[:2000],
    }]


def main():
    data_dir = Path(BACKEND_DIR / "data" / "law_files")
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取文件列表
    print("=== 获取文件列表 ===")
    resp = urllib.request.urlopen("https://api.github.com/repos/taburise/Chinese-Laws-folk/contents/")
    files = json.loads(resp.read())
    txt_files = sorted([f["name"] for f in files if f["name"].endswith(".txt")])
    print(f"共 {len(txt_files)} 个法律文件")

    # 2. 下载文件
    print("\n=== 下载文件 ===")
    base_url = "https://media.githubusercontent.com/media/taburise/Chinese-Laws-folk/main"
    downloaded = []
    for i, fname in enumerate(txt_files):
        fpath = data_dir / fname
        if fpath.exists() and fpath.stat().st_size > 100:
            downloaded.append(fpath)
            continue
        url = f"{base_url}/{urllib.request.quote(fname)}"
        try:
            urllib.request.urlretrieve(url, fpath)
            downloaded.append(fpath)
            print(f"  [{i+1}/{len(txt_files)}] ✓ {fname}")
        except Exception as e:
            print(f"  [{i+1}/{len(txt_files)}] ✗ {fname}: {e}")
        if (i + 1) % 30 == 0:
            time.sleep(1)
    print(f"下载完成: {len(downloaded)}/{len(txt_files)}")

    # 3. 解析所有文件
    print("\n=== 解析文件 ===")
    all_clauses = []
    for fpath in downloaded:
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            clauses = parse_law_file(text, fpath.name)
            if clauses:
                all_clauses.extend(clauses)
                print(f"  ✓ {fpath.name}: {len(clauses)} 条")
            else:
                print(f"  ? {fpath.name}: 0 条 (格式无法识别)")
        except Exception as e:
            print(f"  ✗ {fpath.name}: {e}")

    print(f"\n共解析 {len(all_clauses)} 条法律条文")

    # 4. 导入数据库
    print("\n=== 导入数据库 ===")
    from app.db.database import execute

    # 清除旧数据
    execute("DELETE FROM statutes")
    print("  ✓ 清除旧数据")

    from app.core.vector.store import store
    try:
        store.delete_by_metadata("source", "statute")
        store.delete_by_metadata("source", "seed_builtin")
    except Exception:
        pass
    print("  ✓ 清除旧向量")

    now = int(time.time())
    imported = 0
    errors = 0
    for clause in all_clauses:
        try:
            execute(
                "INSERT INTO statutes (code, name, category, content, source, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (clause["code"], clause["name"], clause["category"], clause["content"],
                 "chinese-laws-folk", now),
            )
            imported += 1
        except Exception as e:
            errors += 1

    print(f"  导入完成: {imported} 成功, {errors} 失败")

    # 5. 向量索引
    print("\n=== 向量索引 ===")
    from app.services.statute_service import build_vector_index
    result = build_vector_index()
    print(f"  向量索引: {result.get('indexed', 0)} 条 (共 {result.get('total_in_db', 0)} 条在库)")

    # 6. 统计
    from app.db.database import query_one
    count = query_one("SELECT COUNT(*) as n, COUNT(DISTINCT category) as c FROM statutes")
    print(f"\n=== 完成 ===")
    print(f"  总条文数: {count['n'] if count else 0}")
    print(f"  分类数: {count['c'] if count else 0}")

    categories = execute("SELECT category, COUNT(*) as n FROM statutes GROUP BY category ORDER BY n DESC")
    for row in categories:
        print(f"    {row['category']}: {row['n']} 条")

    return 0


if __name__ == "__main__":
    sys.exit(main())
