import asyncio, asyncpg, json, uuid, hashlib
from datetime import datetime, timedelta

async def inject():
    conn = await asyncpg.connect('postgresql://postgres:dev_password@localhost:5432/interview_practice')

    questions = [
        # RAG (5 questions)
        ('RAG 系统中的检索器如何选择？', '在检索增强生成系统中，检索器的选择对最终生成质量至关重要。请描述常见的检索器类型及其优缺点，包括 BM25、DPR、Contriever 等。', 'concept', 'RAG', 4, 4.0),
        ('什么是 Chunking 策略？', '在 RAG 系统中，文档切分策略（Chunking）直接影响检索效果。请解释固定大小切分、语义切分、递归切分等策略的适用场景。', 'concept', 'RAG', 3, 3.5),
        ('RAG 中的重排序（Reranking）有什么作用？', '在检索出候选文档后，为什么需要 reranking 步骤？常见的 reranker 模型有哪些？Cross-encoder 和 Bi-encoder 有什么区别？', 'concept', 'RAG', 4, 4.2),
        ('如何实现 RAG 系统中的混合检索？', '混合检索结合关键词检索（BM25）和向量检索（Embedding），请描述其实现原理和权重调整策略。', 'architecture', 'RAG', 5, 4.5),
        ('RAG 系统如何处理多轮对话中的上下文？', '在多轮对话场景中，RAG 系统需要维护对话历史并动态调整检索策略。请描述常见的解决方案。', 'scenario', 'RAG', 4, 3.8),
        # Backend (5 questions)
        ('如何设计一个高并发的 API 网关？', 'API 网关需要处理限流、鉴权、路由转发等功能。请描述使用 FastAPI/Go 实现高并发 API 网关的关键设计点。', 'architecture', 'Backend', 5, 4.5),
        ('微服务架构中的服务发现是如何工作的？', '请解释 Consul、Etcd、Nacos 等服务发现工具的工作原理，以及它们在微服务架构中的作用。', 'concept', 'Backend', 3, 3.5),
        ('什么是 CQRS 模式？', 'Command Query Responsibility Segregation 模式将读写操作分离。请描述其适用场景和实现方式。', 'concept', 'Backend', 4, 4.0),
        ('如何设计分布式系统的重试机制？', '在微服务架构中，网络不稳定导致需要重试。请解释指数退避、抖动、熔断器等概念及其组合使用方式。', 'scenario', 'Backend', 4, 4.2),
        ('RESTful API 版本管理的最佳实践是什么？', '请描述 URL 路径版本化、Header 版本化、内容协商等 API 版本管理策略的优缺点。', 'concept', 'Backend', 2, 3.0),
        # Database (3 questions)
        ('PostgreSQL 中索引优化的常见策略有哪些？', '请解释 B-tree、GIN、GiST、BRIN 等索引类型的适用场景，以及如何通过 EXPLAIN ANALYZE 分析查询性能。', 'concept', 'Database', 3, 3.5),
        ('数据库事务隔离级别有哪些？', '请解释 Read Uncommitted、Read Committed、Repeatable Read、Serializable 四种隔离级别及其对应的并发问题（脏读、不可重复读、幻读）。', 'concept', 'Database', 3, 3.8),
        ('如何设计一个支持水平扩展的分库分表方案？', '当单表数据量达到千万级别时，需要考虑分库分表。请描述常见的分片策略（Range、Hash、Consistent Hash）及其适用场景。', 'architecture', 'Database', 5, 4.8),
        # Frontend (3 questions)
        ('React 中如何实现高性能的大列表渲染？', '当需要渲染数千条数据时，直接渲染会导致性能问题。请描述虚拟滚动（Virtual Scrolling）的原理和常见实现方案。', 'scenario', 'Frontend', 4, 3.5),
        ('Next.js 中 SSR、SSG、ISR 有什么区别？', '请解释服务端渲染、静态生成、增量静态再生成的区别，以及各自的适用场景。', 'concept', 'Frontend', 3, 3.8),
        ('前端性能优化的常见手段有哪些？', '请从代码分割、懒加载、图片优化、缓存策略、CDN 等方面描述前端性能优化的实践方法。', 'concept', 'Frontend', 2, 3.0),
        # ML (2 questions)
        ('Transformer 架构中的 Self-Attention 是如何工作的？', '请解释 Query、Key、Value 矩阵的作用，以及 Multi-Head Attention 的计算过程和优势。', 'concept', 'ML', 4, 4.0),
        ('什么是 LoRA 微调？', 'Low-Rank Adaptation 是一种参数高效的微调方法。请解释其原理、相比全量微调的优势，以及在 LLM 场景中的应用。', 'concept', 'ML', 4, 4.2),
    ]

    now = datetime.utcnow()
    inserted_ids = []
    for title, content, qtype, domain, difficulty, score in questions:
        qid = str(uuid.uuid4())
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        await conn.execute(
            """INSERT INTO questions (id, title, content, content_hash, source_type, question_type, domain_type, difficulty_level, difficulty_score, version, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
            qid, title, content, content_hash, 'manual', qtype, domain, difficulty, score, 1, now, now
        )
        inserted_ids.append(qid)

    # Create some tags
    tag_names = ['Python', 'PostgreSQL', 'React', 'RAG', 'LLM', '分布式系统', '性能优化', '微服务', '深度学习', 'Next.js']
    tag_ids = []
    for name in tag_names:
        tid = str(uuid.uuid4())
        await conn.execute(
            'INSERT INTO tags (id, name, tag_type, version, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6)',
            tid, name, 'topic', 1, now, now
        )
        tag_ids.append(tid)

    # Link tags to questions
    # RAG questions -> RAG tag (index 3)
    for i in range(5):
        await conn.execute(
            'INSERT INTO question_tags (id, question_id, tag_id, source_type, confidence, version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
            str(uuid.uuid4()), inserted_ids[i], tag_ids[3], 'manual', 1.0, 1, now
        )
    # Backend questions -> 微服务 tag (index 7)
    for i in range(5, 10):
        await conn.execute(
            'INSERT INTO question_tags (id, question_id, tag_id, source_type, confidence, version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
            str(uuid.uuid4()), inserted_ids[i], tag_ids[7], 'manual', 1.0, 1, now
        )
    # Database questions -> PostgreSQL tag (index 1)
    for i in range(10, 13):
        await conn.execute(
            'INSERT INTO question_tags (id, question_id, tag_id, source_type, confidence, version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
            str(uuid.uuid4()), inserted_ids[i], tag_ids[1], 'manual', 1.0, 1, now
        )
    # Frontend: React question -> React tag (index 2)
    await conn.execute(
        'INSERT INTO question_tags (id, question_id, tag_id, source_type, confidence, version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
        str(uuid.uuid4()), inserted_ids[13], tag_ids[2], 'manual', 1.0, 1, now
    )
    # Frontend: Next.js question -> Next.js tag (index 9)
    await conn.execute(
        'INSERT INTO question_tags (id, question_id, tag_id, source_type, confidence, version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
        str(uuid.uuid4()), inserted_ids[15], tag_ids[9], 'manual', 1.0, 1, now
    )
    # ML questions -> LLM tag (index 4)
    for i in range(16, 18):
        await conn.execute(
            'INSERT INTO question_tags (id, question_id, tag_id, source_type, confidence, version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
            str(uuid.uuid4()), inserted_ids[i], tag_ids[4], 'manual', 1.0, 1, now
        )

    # Create study records
    study_types = ['practice', 'review', 'interview_simulation']
    for i in range(10):
        qid = inserted_ids[i % len(inserted_ids)]
        sid = str(uuid.uuid4())
        reviewed = now - timedelta(days=i, hours=i*2)
        await conn.execute(
            """INSERT INTO study_records (id, user_id, session_id, question_id, study_type, user_answer, ai_score, ai_feedback, mastery_level, duration_seconds, review_result, reviewed_at, next_review_at, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)""",
            sid, 'test_user', f'session_{i}', qid, study_types[i % 3],
            f'Sample answer for question {i}',
            70 + (i * 3) % 30,
            f'Good understanding, needs improvement on detail {i}',
            3 + (i % 3),
            120 + i * 30,
            'pass' if i % 2 == 0 else 'fail',
            reviewed,
            reviewed + timedelta(days=7),
            reviewed,
            reviewed
        )

    # Create knowledge nodes
    node_data = [
        ('检索增强生成', 'concept', 1),
        ('向量数据库', 'concept', 2),
        ('API设计', 'concept', 1),
        ('数据库优化', 'concept', 1),
        ('React组件', 'concept', 1),
        ('Transformer', 'concept', 1),
        ('分库分表', 'technique', 2),
        ('服务网格', 'concept', 2),
    ]
    for name, ntype, depth in node_data:
        nid = str(uuid.uuid4())
        await conn.execute(
            'INSERT INTO knowledge_nodes (id, name, node_type, depth_level, version, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
            nid, name, ntype, depth, 1, now, now
        )

    total = await conn.fetchval('SELECT COUNT(*) FROM questions')
    tags_count = await conn.fetchval('SELECT COUNT(*) FROM tags')
    study_count = await conn.fetchval('SELECT COUNT(*) FROM study_records')
    nodes_count = await conn.fetchval('SELECT COUNT(*) FROM knowledge_nodes')
    print(f'Injected! Total questions: {total}, tags: {tags_count}, study_records: {study_count}, knowledge_nodes: {nodes_count}')

    await conn.close()

asyncio.run(inject())
