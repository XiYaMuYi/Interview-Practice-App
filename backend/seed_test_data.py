"""注入测试数据到 Interview Practice App"""
import asyncio
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import httpx

BASE_URL = "http://localhost:8000/api/v1"

QUESTIONS = [
    # ── RAG ──
    {
        "title": "什么是 RAG？它解决了 LLM 的哪些问题？",
        "content": "请解释 RAG（Retrieval-Augmented Generation）的基本概念，以及它如何解决 LLM 的知识更新和幻觉问题。",
        "reference_answer": "RAG 通过检索外部知识库来增强 LLM 的生成能力，解决了模型知识过时和幻觉问题。",
        "question_type": "concept",
        "domain_type": "RAG",
        "difficulty_level": 3,
        "tags": ["基础", "架构"]
    },
    {
        "title": "RAG 中 retrieval 和 generation 如何协同工作？",
        "content": "详细描述 RAG 系统中检索模块和生成模块的协作流程。",
        "reference_answer": "检索模块从知识库中找到相关文档片段，生成模块将这些片段作为上下文来生成回答。",
        "question_type": "concept",
        "domain_type": "RAG",
        "difficulty_level": 4,
        "tags": ["架构", "流程"]
    },
    {
        "title": "RAG 中的文档分块策略有哪些？如何选择？",
        "content": "讨论不同的文档分块（Chunking）策略及其适用场景。",
        "reference_answer": "常见策略包括固定大小分块、语义分块、递归分块等。选择取决于文档类型和检索需求。",
        "question_type": "concept",
        "domain_type": "RAG",
        "difficulty_level": 4,
        "tags": ["优化", "工程"]
    },
    {
        "title": "什么是混合检索？为什么要结合 BM25 和向量检索？",
        "content": "解释混合检索的概念和优势。",
        "reference_answer": "混合检索结合 BM25 的关键词匹配和向量检索的语义理解，提高检索准确性。",
        "question_type": "concept",
        "domain_type": "RAG",
        "difficulty_level": 3,
        "tags": ["检索", "优化"]
    },
    # ── Backend ──
    {
        "title": "RESTful API 设计的基本原则是什么？",
        "content": "列出并解释 RESTful API 的核心设计原则。",
        "reference_answer": "包括资源导向、统一接口（CRUD 对应 HTTP 方法）、无状态、可缓存等原则。",
        "question_type": "concept",
        "domain_type": "Backend",
        "difficulty_level": 3,
        "tags": ["设计", "API"]
    },
    {
        "title": "什么是幂等性？在 API 设计中如何实现？",
        "content": "解释幂等性的概念，并举例说明哪些 HTTP 方法是幂等的。",
        "reference_answer": "幂等性指多次执行同一操作结果相同。GET、PUT、DELETE 是幂等的，POST 不是。",
        "question_type": "concept",
        "domain_type": "Backend",
        "difficulty_level": 4,
        "tags": ["设计", "HTTP"]
    },
    {
        "title": "如何设计一个高并发的缓存系统？",
        "content": "讨论缓存策略、缓存穿透/击穿/雪崩的解决方案。",
        "reference_answer": "使用多级缓存（本地+Redis）、布隆过滤器防穿透、互斥锁防击穿、随机过期时间防雪崩。",
        "question_type": "design",
        "domain_type": "Backend",
        "difficulty_level": 5,
        "tags": ["架构", "性能"]
    },
    {
        "title": "微服务之间如何保证数据一致性？",
        "content": "讨论分布式事务、Saga 模式、事件溯源等方案。",
        "reference_answer": "可选方案包括两阶段提交、Saga 模式、事件驱动架构、最终一致性等。",
        "question_type": "design",
        "domain_type": "Backend",
        "difficulty_level": 5,
        "tags": ["架构", "分布式"]
    },
    # ── Database ──
    {
        "title": "什么是 B+ 树？为什么数据库索引使用 B+ 树而不是 B 树？",
        "content": "解释 B+ 树的结构特点及其作为数据库索引的优势。",
        "reference_answer": "B+ 树所有数据都在叶子节点，叶子节点间有链表连接，适合范围查询和顺序访问。",
        "question_type": "concept",
        "domain_type": "Database",
        "difficulty_level": 4,
        "tags": ["索引", "数据结构"]
    },
    {
        "title": "事务的 ACID 特性是什么？分别解释。",
        "content": "详细解释原子性、一致性、隔离性、持久性。",
        "reference_answer": "A-原子性（全部成功或全部回滚）、C-一致性、I-隔离性（事务互不干扰）、D-持久性（提交后不可逆）。",
        "question_type": "concept",
        "domain_type": "Database",
        "difficulty_level": 3,
        "tags": ["事务", "基础"]
    },
    {
        "title": "什么是数据库连接池？为什么需要它？",
        "content": "解释连接池的工作原理和使用场景。",
        "reference_answer": "连接池预先创建并维护一批数据库连接，复用连接减少创建开销，提高性能。",
        "question_type": "concept",
        "domain_type": "Database",
        "difficulty_level": 3,
        "tags": ["性能", "连接"]
    },
    # ── Frontend ──
    {
        "title": "React 的虚拟 DOM 是如何工作的？",
        "content": "解释虚拟 DOM 的原理和 Diff 算法。",
        "reference_answer": "虚拟 DOM 是真实 DOM 的 JS 对象映射，React 通过 Diff 算法比较新旧虚拟 DOM，最小化真实 DOM 操作。",
        "question_type": "concept",
        "domain_type": "Frontend",
        "difficulty_level": 3,
        "tags": ["React", "原理"]
    },
    {
        "title": "什么是 SSR？它与 CSR 有什么区别？",
        "content": "比较服务端渲染和客户端渲染的优缺点。",
        "reference_answer": "SSR 在服务端生成 HTML，首屏快、SEO 好；CSR 在浏览器渲染，交互体验好但首屏慢。",
        "question_type": "concept",
        "domain_type": "Frontend",
        "difficulty_level": 3,
        "tags": ["渲染", "性能"]
    },
    {
        "title": "前端性能优化有哪些常见手段？",
        "content": "列举并解释常用的前端性能优化方法。",
        "reference_answer": "包括代码分割、懒加载、CDN 缓存、图片压缩、Tree Shaking、HTTP/2 多路复用等。",
        "question_type": "concept",
        "domain_type": "Frontend",
        "difficulty_level": 4,
        "tags": ["性能", "优化"]
    },
    # ── ML ──
    {
        "title": "什么是过拟合？如何防止过拟合？",
        "content": "解释过拟合现象，并列举防止过拟合的方法。",
        "reference_answer": "过拟合指模型在训练集表现好但在测试集差。防止方法：正则化、Dropout、早停、数据增强、交叉验证。",
        "question_type": "concept",
        "domain_type": "ML",
        "difficulty_level": 3,
        "tags": ["训练", "优化"]
    },
    {
        "title": "Transformer 的核心机制是什么？",
        "content": "解释 Self-Attention 和 Multi-Head Attention 的原理。",
        "reference_answer": "Self-Attention 让序列中每个位置关注其他位置，Multi-Head 从不同子空间提取信息，Positional Encoding 提供位置信息。",
        "question_type": "concept",
        "domain_type": "ML",
        "difficulty_level": 5,
        "tags": ["架构", "Attention"]
    },
]


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        created = 0
        for q in QUESTIONS:
            resp = await client.post(f"{BASE_URL}/questions/", json=q)
            if resp.status_code in (200, 201):
                created += 1
                data = resp.json()
                print(f"✅ [{data.get('domain_type','?')}] {data.get('title','')[:50]} (id={data.get('id','')[:8]}...)")
            else:
                print(f"❌ 失败 [{resp.status_code}] {q['title'][:50]}")
                print(f"   {resp.text[:200]}")

        print(f"\n完成！成功创建 {created}/{len(QUESTIONS)} 条题目")

        # 获取总数
        resp = await client.get(f"{BASE_URL}/questions/?limit=1")
        total = resp.json()["total"]
        print(f"数据库中共有 {total} 条题目")


if __name__ == "__main__":
    asyncio.run(main())
