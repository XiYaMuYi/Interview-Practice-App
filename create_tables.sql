-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- files (no deps)
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    parse_status VARCHAR(50) NOT NULL,
    parse_error TEXT,
    file_hash VARCHAR(128),
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- tags (no deps)
CREATE TABLE IF NOT EXISTS tags (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    tag_type VARCHAR(50) NOT NULL,
    description TEXT,
    color VARCHAR(20),
    version INT NOT NULL DEFAULT 1,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- knowledge_nodes (self-ref)
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES knowledge_nodes(id),
    node_type VARCHAR(50) NOT NULL,
    depth_level INT,
    version INT NOT NULL DEFAULT 1,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- prompt_versions (no deps)
CREATE TABLE IF NOT EXISTS prompt_versions (
    id UUID PRIMARY KEY,
    prompt_key VARCHAR(100) NOT NULL,
    prompt_content TEXT NOT NULL,
    prompt_version VARCHAR(100) NOT NULL,
    model_version VARCHAR(100),
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- learning_profiles (no deps)
CREATE TABLE IF NOT EXISTS learning_profiles (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    weak_topics JSONB,
    strong_topics JSONB,
    mastery_map JSONB,
    review_cycle VARCHAR(50),
    extra_data JSONB,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- questions
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(128),
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(255),
    source_ref VARCHAR(255),
    source_excerpt TEXT,
    question_type VARCHAR(50),
    domain_type VARCHAR(100),
    difficulty_level INT,
    difficulty_score FLOAT,
    answer_summary TEXT,
    answer_detail TEXT,
    explanation TEXT,
    common_pitfalls TEXT,
    mastery_level INT,
    review_status VARCHAR(50),
    version INT NOT NULL DEFAULT 1,
    model_version VARCHAR(100),
    prompt_version VARCHAR(100),
    extra_data JSONB,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_questions_user_id ON questions(user_id);

-- resumes
CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES files(id),
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    parse_status VARCHAR(50) NOT NULL,
    raw_text TEXT,
    structured_summary JSONB,
    model_version VARCHAR(100),
    prompt_version VARCHAR(100),
    extra_data JSONB,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
ALTER TABLE resumes ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_resumes_user_id ON resumes(user_id);

-- resume_experiences
CREATE TABLE IF NOT EXISTS resume_experiences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id UUID NOT NULL REFERENCES resumes(id),
    experience_type VARCHAR(50) NOT NULL,
    company_or_project VARCHAR(255),
    role_title VARCHAR(255),
    start_date VARCHAR(20),
    end_date VARCHAR(20),
    description TEXT,
    tech_stack JSONB,
    extracted_keywords JSONB,
    confidence FLOAT,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- tasks
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(100),
    status VARCHAR(20) NOT NULL,
    progress FLOAT NOT NULL DEFAULT 0,
    current_phase VARCHAR(50),
    total_chunks INT,
    processed_chunks INT,
    error_message VARCHAR(500),
    retry_count INT NOT NULL DEFAULT 0,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- llm_call_logs
CREATE TABLE IF NOT EXISTS llm_call_logs (
    id UUID PRIMARY KEY,
    task_id UUID,
    session_id VARCHAR(100),
    prompt_key VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    request_preview VARCHAR(500) NOT NULL DEFAULT '',
    response_preview VARCHAR(500) NOT NULL DEFAULT '',
    duration_ms INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_code VARCHAR(50),
    error_message VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- chat_histories
CREATE TABLE IF NOT EXISTS chat_histories (
    id UUID PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(255),
    role VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    message_type VARCHAR(50),
    related_question_id UUID REFERENCES questions(id),
    evaluation_score INT,
    evaluation_summary TEXT,
    model_version VARCHAR(100),
    prompt_version VARCHAR(100),
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- question_embeddings
CREATE TABLE IF NOT EXISTS question_embeddings (
    id UUID PRIMARY KEY,
    question_id UUID NOT NULL REFERENCES questions(id),
    embedding vector(512),
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(100),
    dimension INT,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- question_knowledge_nodes
CREATE TABLE IF NOT EXISTS question_knowledge_nodes (
    id UUID PRIMARY KEY,
    question_id UUID NOT NULL REFERENCES questions(id),
    knowledge_node_id UUID NOT NULL REFERENCES knowledge_nodes(id),
    relation_type VARCHAR(50) NOT NULL,
    confidence FLOAT,
    source_type VARCHAR(50),
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- question_tags
CREATE TABLE IF NOT EXISTS question_tags (
    id UUID PRIMARY KEY,
    question_id UUID NOT NULL REFERENCES questions(id),
    tag_id UUID NOT NULL REFERENCES tags(id),
    source_type VARCHAR(50),
    confidence FLOAT,
    version INT NOT NULL DEFAULT 1,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- study_records
CREATE TABLE IF NOT EXISTS study_records (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),
    session_id VARCHAR(100),
    question_id UUID REFERENCES questions(id),
    study_type VARCHAR(50) NOT NULL,
    user_answer TEXT,
    ai_score INT,
    ai_feedback TEXT,
    mastery_level INT,
    duration_seconds INT,
    review_result VARCHAR(50),
    reviewed_at TIMESTAMP NOT NULL,
    next_review_at TIMESTAMP,
    model_version VARCHAR(100),
    prompt_version VARCHAR(100),
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- exam_sessions
CREATE TABLE IF NOT EXISTS exam_sessions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),
    title VARCHAR(200),
    duration_minutes INT NOT NULL,
    total_questions INT NOT NULL,
    difficulty_filter VARCHAR(50),
    source_filter VARCHAR(50),
    question_ids JSONB,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    total_score FLOAT,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- exam_answers
CREATE TABLE IF NOT EXISTS exam_answers (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES exam_sessions(id),
    question_id UUID NOT NULL REFERENCES questions(id),
    user_answer TEXT,
    score FLOAT,
    feedback TEXT,
    time_spent_seconds INT,
    extra_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

-- event_audit_logs
CREATE TABLE IF NOT EXISTS event_audit_logs (
    id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    backend VARCHAR(50) NOT NULL,
    task_id UUID,
    session_id VARCHAR(100),
    source VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'ok',
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- alembic version tracking
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL
);
INSERT INTO alembic_version (version_num) VALUES ('b9c8d7e6f5a4') ON CONFLICT (version_num) DO NOTHING;
