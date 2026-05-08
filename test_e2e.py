"""E2E test: import text -> verify questions in DB."""
import httpx

BASE = "http://localhost:8000/api/v1"

SAMPLE_TEXT = """
题目：什么是 RAG（检索增强生成）？
难度：3
分类：RAG
类型：concept
内容：请解释 RAG 的核心思想，以及它如何解决大语言模型的知识时效性和幻觉问题。

题目：请解释 Python 中的 GIL 是什么
难度：4
分类：Backend
类型：concept
内容：什么是 GIL（Global Interpreter Lock）？它对多线程 Python 程序有什么影响？如何绕过 GIL 实现真正的并发？

题目：设计一个 URL 短链服务
难度：5
分类：System Design
类型：system_design
内容：请设计一个类似 bit.ly 的 URL 短链服务。需要考虑：短链生成算法、高并发读写、缓存策略、数据存储方案。
"""

print("[1] POST /api/v1/import/text ...")
r = httpx.post(f"{BASE}/import/text", data={"text": SAMPLE_TEXT}, timeout=300.0)
print(f"    Status: {r.status_code}")
body = r.json()
print(f"    Extracted: {body}")

print()
print("[2] GET /api/v1/questions/ ...")
r2 = httpx.get(f"{BASE}/questions/", params={"limit": 50}, timeout=30)
print(f"    Status: {r2.status_code}")
body2 = r2.json()
total = body2.get("total")
print(f"    Total: {total}")
for item in body2.get("items", [])[:10]:
    title = item["title"][:50]
    qtype = item["question_type"]
    domain = item["domain_type"]
    diff = item["difficulty_level"]
    print(f"      - {title} | type={qtype} | domain={domain} | diff={diff}")

print()
print("E2E test OK.")
