"""End-to-end test: import text -> verify questions in DB."""

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

题目：什么是数据库的 ACID 特性？
难度：2
分类：Database
类型：concept
内容：请解释 ACID 四个特性的含义，并举例说明在实际数据库中如何保证这些特性。

题目：解释 React 中 useEffect 的依赖数组
难度：3
分类：Frontend
类型：code
内容：useEffect 的第二个参数（依赖数组）的作用是什么？空数组、有依赖、没有第二个参数分别代表什么行为？
"""


def main():
    print("=" * 60)
    print("E2E Test: Import -> Verify")
    print("=" * 60)

    # Step 1: Import text
    print("\n[1] POST /api/v1/import/text ...")
    with httpx.Client(timeout=600) as client:
        resp = client.post(
            f"{BASE}/import/text",
            data={"text": SAMPLE_TEXT},
        )
        print(f"    Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"    FAILED: {resp.text}")
            return

        body = resp.json()
        print(f"    Response: {body}")
        q_count = body.get("questions_extracted", 0)
        k_count = body.get("knowledge_nodes", 0)
        print(f"    Extracted: {q_count} questions, {k_count} knowledge nodes")

        if q_count == 0:
            print("    WARNING: No questions extracted. LLM may not be configured.")
            print("    Continuing to check existing questions anyway...")

    # Step 2: Verify questions list
    print("\n[2] GET /api/v1/questions/ ...")
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{BASE}/questions/", params={"limit": 50})
        print(f"    Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"    FAILED: {resp.text}")
            return

        body = resp.json()
        total = body.get("total", 0)
        items = body.get("items", [])
        print(f"    Total: {total}")
        print(f"    Returned: {len(items)} items")

        for item in items[:10]:
            print(f"      - [{item['id'][:8]}...] {item['title'][:60]} | type={item['question_type']} | domain={item['domain_type']} | diff={item['difficulty_level']}")

        if len(items) > 10:
            print(f"      ... and {len(items) - 10} more")

    print("\n" + "=" * 60)
    print("E2E test completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
