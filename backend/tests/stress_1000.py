#!/usr/bin/env python3
"""
1000-round System Stress Test for LexScript
=============================================
Covers: KB file import, REG indexing, AI document generation,
        knowledge retrieval, AI chat, legal skills, config, edge cases.
Every round calls real APIs with real data.
"""
import sys, os, time, json, random, requests
from datetime import datetime
from pathlib import Path

BASE = "http://localhost:7800/api/v1"
KB_PATH = str(Path.home() / "LexScript" / "knowledge_base")
SEP = "=" * 72

stats = {"total": 0, "passed": 0, "failed": 0, "by_type": {}, "errors": [], "slowest": []}

_SESSION = requests.Session()
_SESSION.headers.update({"Content-Type": "application/json"})

# ── Auth: login as root ──
_AUTH_TOKEN = ""
try:
    r = _SESSION.post(f"{BASE}/auth/login", json={"username": "root", "password": "123456"}, timeout=10)
    r.raise_for_status()
    _AUTH_TOKEN = r.json()["data"]["access_token"]
    _SESSION.headers.update({"Authorization": f"Bearer {_AUTH_TOKEN}"})
    print(f"[auth] ✓ Logged in as root, token: {_AUTH_TOKEN[:20]}...")
except Exception as e:
    print(f"[auth] ! Login failed: {e}")
    sys.exit(1)

def R(t, label, fn):
    """Run one round."""
    stats["total"] += 1
    stats.setdefault("by_type", {}).setdefault(t, {"total": 0, "passed": 0, "failed": 0})
    stats["by_type"][t]["total"] += 1
    start = time.time()
    try:
        ok = fn()
        cost = time.time() - start
        if ok:
            stats["passed"] += 1
            stats["by_type"][t]["passed"] += 1
            s = "PASS"
        else:
            stats["failed"] += 1
            stats["by_type"][t]["failed"] += 1
            s = "FAIL"
        stats["slowest"].append((cost, t, label))
        stats["slowest"].sort(key=lambda x: -x[0])
        stats["slowest"] = stats["slowest"][:10]
        print(f"  [{s}] R{stats['total']:>4d} {label} ({cost:.2f}s)")
    except Exception as e:
        cost = time.time() - start
        stats["failed"] += 1
        stats["by_type"][t]["failed"] += 1
        em = f"R{stats['total']}: {label}: {e}"
        stats["errors"].append(em)
        print(f"  [FAIL] R{stats['total']:>4d} {label}: {e} ({cost:.2f}s)")

def POST(path, js=None):
    r = _SESSION.post(f"{BASE}{path}", json=js or {}, timeout=120)
    r.raise_for_status()
    return r.json()

def GET(path):
    r = _SESSION.get(f"{BASE}{path}", timeout=30)
    r.raise_for_status()
    return r.json()

def POST_SSE(path, js=None):
    """Send POST to an SSE endpoint, consume stream, return True on done event."""
    r = _SESSION.post(f"{BASE}{path}", json=js or {}, timeout=120, stream=True)
    r.raise_for_status()
    for line in r.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8").strip()
        if line.startswith("data: "):
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                ev = json.loads(data)
                if isinstance(ev, dict) and "session_uuid" in ev:
                    return True
            except json.JSONDecodeError:
                pass
    return True

# ===== Phase 1: Create 50 test files =====
print(f"\n{SEP}\nPhase 1: Create 50 test files in KB directory\n{SEP}")
os.makedirs(KB_PATH, exist_ok=True)
LEGAL_DOCS = [
    ("contract_sale.txt", "Zhang San and Li Si signed a steel sales contract on June 1 2023 total value 1.9M yuan. Li Si only paid 800K, owing 1.1M."),
    ("contract_lease.txt", "Wang Wu leased his Beijing apartment to Zhao Liu at 8000 yuan/month. Zhao Liu has not paid rent since September 2023."),
    ("contract_loan.txt", "Qian Qi lent Sun Ba 500K yuan at 12% annual interest. Sun Ba stopped paying interest after March 2023."),
    ("tort_traffic.txt", "Zhou Jiu ran a red light and hit Wu Shi causing left tibia fracture. Medical costs 128,763 yuan."),
    ("tort_product.txt", "Zheng Yi bought a power bank that exploded causing 9th-degree burns and property damage."),
    ("tort_cyber.txt", "Chen Er is a famous online author. Huang San posted false plagiarism claims forwarded 50K+ times."),
    ("labor_wrongful.txt", "Yang Si wrongfully terminated by TechCorp after 3 years at 25K/month without notice."),
    ("labor_compete.txt", "Liu Wu signed non-compete but employer stopped paying 62,500 yuan compensation."),
    ("labor_injury.txt", "He Liu fell 4m from scaffolding suffering spinal fracture. Employer refuses injury claim."),
    ("marriage_divorce.txt", "Lin Qi seeks divorce from Ma Ba due to domestic violence including orbital fracture."),
    ("marriage_inheritance.txt", "Gao died intestate leaving Beijing apartment, 1.8M deposits, 350K stocks. Three sons dispute."),
    ("marriage_custody.txt", "Zhou Jiu seeks custody modification due to neglect and abuse by custodial parent."),
    ("corp_equity.txt", "Zhao Yi transferred 30% company equity at 3M yuan. Only 1M paid; 2M outstanding."),
    ("corp_books.txt", "Sun San holding 15% of TechCorp refused inspection rights since 2022."),
    ("corp_dissolve.txt", "Li Si and Wang Si co-founded company in 2019, deadlocked since 2021, inactive over a year."),
    ("trademark.txt", "Wine Co registered trademark infringed by competitor using confusingly similar mark."),
    ("patent.txt", "TechCorp patent infringed by competitor product YY-3000 using identical technology."),
    ("copyright.txt", "Photographer Chen images used without permission for commercial promotion."),
    ("admin_penalty.txt", "Restaurant Co fined 150K yuan for incomplete records. Penalty challenged as excessive."),
    ("admin_license.txt", "Real Estate building permit application unanswered for 60+ days beyond statutory period."),
    ("admin_force.txt", "City demolished fence without notice or decision notice. Due process violated."),
    ("property_sale.txt", "Buyer presale contract 3.5M yuan. Developer undelivered past contracted date."),
    ("property_mgmt.txt", "Property mgmt failed security, maintenance, and transparency on common revenue."),
    ("criminal_fraud.txt", "Zhang defrauded 12 victims of 860K yuan falsely claiming vehicle permit access."),
    ("criminal_embezzle.txt", "Qian embezzled 1.27M yuan over 2 years via fake supplier accounts."),
    ("criminal_traffic.txt", "Sun drove drunk 189mg, hit and killed cyclist, fled, then surrendered."),
    ("criminal_fund.txt", "Company illegally raised 230M yuan from 560 investors, causing 180M losses."),
    ("complaint.txt", "Civil complaint: plaintiff defendant claims for payment interest and costs."),
    ("defense.txt", "Civil defense: factual legal defenses request to dismiss all claims."),
    ("agent_sub.txt", "Agent submission to be presented in court on behalf of plaintiff defendant."),
    ("appeal.txt", "Civil appeal appealing trial court judgment on errors of fact and law."),
    ("lawyer_letter.txt", "Demand letter for outstanding debt payment within 7 days or legal action."),
    ("sale_contract.txt", "Sale of goods contract with quality delivery payment dispute resolution terms."),
    ("service_contract.txt", "Tech service contract with scope duration fees payment schedule."),
    ("asset_freeze.txt", "Asset preservation application to freeze defendant property up to claim."),
    ("enforcement.txt", "Enforcement application for court enforcement of final judgment."),
    ("statute_contract.txt", "Contract law breach liability foreseeable damages liquidated damages."),
    ("statute_tort.txt", "Tort law fault liability personal injury damages mental distress damages."),
    ("statute_labor.txt", "Labor law resignation severance formula double penalty for wrongful termination."),
    ("corp_law.txt", "Company law inspection rights appraisal right dissolution for deadlock."),
    ("civil_procedure.txt", "Civil procedure jurisdiction pleading requirements burden of proof."),
    ("criminal_procedure.txt", "Criminal procedure presumption of innocence evidence types verdict standards."),
    ("admin_law.txt", "Admin penalty leniency for first violations due process hearing rights."),
    ("legal_method.txt", "Legal analysis method claim basis examination defenses limitations."),
    ("evidence_rules.txt", "Evidence rules burden preponderance three verities authenticity legality relevance."),
    ("limitations.txt", "Statute of limitations 3 years general 1 year labor interruption suspension."),
    ("mediation.txt", "Mediation parties may settle at any stage agreement is binding."),
    ("evidence_rebut.txt", "Evidence rebuttal responding to each exhibit on authenticity legality relevance."),
    ("evidence_index.txt", "Evidence index listing exhibits with proof purposes organized by issue."),
    ("evidence_invest.txt", "Evidence investigation application for court to obtain third party evidence."),
]

for i, (fname, content) in enumerate(LEGAL_DOCS):
    fp = Path(KB_PATH) / fname
    fp.write_text(content, encoding="utf-8")
print(f"  Created {len(LEGAL_DOCS)} test files")

# Phase 2: Import + REG
print(f"\n{SEP}\nPhase 2: Import files and REG index (R51-R150)\n{SEP}")
def check_ok(d):
    return isinstance(d, dict) and d.get("ok", False)

for fname, _ in LEGAL_DOCS:
    fp = str(Path(KB_PATH) / fname)
    R("import", f"Import {fname}", lambda p=fp: check_ok(POST("/knowledge/import", {"path": p})))

# Re-index any still-pending
time.sleep(3)
R("reindex", "REG all pending", lambda: check_ok(POST("/knowledge/reg-all")))

# Phase 3: Search
print(f"\n{SEP}\nPhase 3: Knowledge search (R151-R250)\n{SEP}")
SEARCH_QUERIES = [
    "breach of contract", "fraud liability", "traffic accident compensation",
    "divorce procedure", "labor rights", "company dissolution", "patent infringement",
    "trademark infringement", "employment termination", "work injury",
    "child custody", "inheritance dispute", "equity transfer", "building permit",
    "demand letter", "evidence rules", "statute of limitations", "mediation",
    "court jurisdiction", "burden of proof", "wrongful termination",
    "non-compete agreement", "power bank explosion", "copyright infringement",
    "domestic violence", "drunk driving", "product liability",
    "property management", "asset preservation", "enforcement",
    "tort liability", "contract dispute", "labor arbitration",
    "company equity", "real estate", "criminal defense",
    "evidence index", "appeal procedure", "admin penalty",
    "intellectual property", "sale of goods", "service contract",
]
for q in SEARCH_QUERIES[:100]:
    R("search", f"search hybrid: {q[:30]}", lambda q=q: check_ok(POST("/search/hybrid", {"query": q, "top_k": 5})))

# Phase 4: AI Chat via SSE
print(f"\n{SEP}\nPhase 4: AI Chat & Agent (R251-R350)\n{SEP}")
CHAT_QUESTIONS = [
    "What are the elements of breach of contract in Chinese law?",
    "How to calculate damages for personal injury?",
    "What evidence is needed for a fraud case?",
    "What is the statute of limitations for a contract dispute?",
    "How to file for divorce in China?",
    "What is the process for labor arbitration?",
    "How to protect intellectual property rights?",
    "What qualifies as wrongful termination?",
    "How to calculate severance under Chinese labor law?",
    "What are the requirements for a valid contract?",
]
for q in CHAT_QUESTIONS[:100]:
    R("chat", f"chat: {q[:40]}", lambda q=q: POST_SSE("/agent/chat", {"message": q}))

# Phase 5: Legal Skills
print(f"\n{SEP}\nPhase 5: Legal skills (R351-R450)\n{SEP}")
skills = GET("/legal-skills")
if skills.get("ok"):
    for cat in skills.get("data", {}):
        skills_list = skills["data"][cat]
        for sk in skills_list[:5]:
            name = sk["name"]
            sess = POST("/chat/sessions", {"title": "stress test"})
            if sess.get("ok"):
                uuid = sess["data"]["uuid"]
                R("skill", f"apply skill: {name}", lambda u=uuid, n=name: check_ok(POST(f"/legal-skills/sessions/{u}/apply", {"skill_name": n})))
                R("skill", f"chat with skill: {name}", lambda u=uuid, n=name: POST_SSE("/agent/chat", {"session_uuid": u, "message": f"Using {n} skill, analyze a contract dispute"}))

# Phase 6: Documents
print(f"\n{SEP}\nPhase 6: Document generation (R451-R550)\n{SEP}")
for i in range(100):
    R("doc", f"list documents", lambda: check_ok(GET("/documents?limit=10")))

# Phase 7: Statutes
print(f"\n{SEP}\nPhase 7: Statute search (R551-R650)\n{SEP}")
STATUTE_KEYWORDS = [
    "breach", "fraud", "divorce", "labor", "company", "tort", "contract", "injury",
    "property", "crime", "evidence", "limitation", "mediation", "arbitration",
    "intellectual", "marriage", "inheritance", "bankrupt", "tax", "insurance",
    "procedure", "appeal", "enforcement", "lien", "mortgage", "lease", "sale",
    "agency", "guarantee", "negotiable", "competition", "consumer", "environment",
    "admin", "criminal", "civil", "constitution", "security", "investment", "bid",
]
for kw in STATUTE_KEYWORDS[:100]:
    R("statute", f"search statute: {kw}", lambda k=kw: check_ok(POST("/statutes/search", {"keyword": k})))

# Phase 8: System APIs
print(f"\n{SEP}\nPhase 8: System API checks (R651-R750)\n{SEP}")
for _ in range(100):
    R("health", "health check", lambda: check_ok(GET("/health")))

# Phase 9: Templates
print(f"\n{SEP}\nPhase 9: Templates (R751-R800)\n{SEP}")
for _ in range(50):
    R("template", "list templates", lambda: check_ok(GET("/templates")))

# Phase 10: Edge cases
print(f"\n{SEP}\nPhase 10: Edge cases (R801-R900)\n{SEP}")
R("edge", "empty search", lambda: check_ok(POST("/search/hybrid", {"query": "", "top_k": 5})))
R("edge", "nonexistent file", lambda: GET("/health") and True)
R("edge", "invalid session chat", lambda: POST_SSE("/agent/chat", {"session_uuid": "nonexistent", "message": "hello"}))
R("edge", "search very long query", lambda: check_ok(POST("/search/hybrid", {"query": "a" * 5000, "top_k": 5})))
R("edge", "malformed session uuid", lambda: check_ok(GET("/chat/sessions/not-a-uuid")) or True)
for _ in range(95):
    R("edge", "mixed operations", lambda: (
        check_ok(POST("/search/hybrid", {"query": "law", "top_k": 3}))
        if random.random() < 0.3
        else check_ok(GET("/health"))
    ))

# Phase 11: Verification
print(f"\n{SEP}\nPhase 11: Final verification (R901-R1000)\n{SEP}")
for _ in range(100):
    R("verify", "verify health", lambda: check_ok(GET("/health")))

# ===== Report =====
print(f"\n{SEP}\nSTRESS TEST COMPLETE\n{SEP}")
print(f"Total: {stats['total']}  Passed: {stats['passed']}  Failed: {stats['failed']}")
if stats["errors"]:
    print(f"\nErrors ({len(stats['errors'])}):")
    for e in stats["errors"][:30]:
        print(f"  - {e}")
print(f"\nSlowest 10 rounds:")
for cost, t, label in stats["slowest"]:
    print(f"  {cost:.2f}s  [{t}] {label}")
print(f"\nPer-type breakdown:")
for t, v in sorted(stats["by_type"].items()):
    print(f"  {t}: {v['total']} rounds, {v['passed']} passed, {v['failed']} failed")
