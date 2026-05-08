"""SQLModel domain entities — mirrors 03_Database_Schema.md."""

import uuid
from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


# ── SQLAlchemy column helpers (pgvector + JSONB) ──


def _jsonb_column():
    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import JSONB
    return Column(JSONB)


def _vector_column():
    """Return a pgvector VECTOR column."""
    from sqlalchemy import Column
    try:
        from pgvector.sqlalchemy import Vector
        return Column(Vector(512))
    except ImportError:
        from sqlalchemy.types import UserDefinedType

        class VectorType(UserDefinedType):
            def get_col_spec(self, **kw):
                return "VECTOR(512)"
        return Column(VectorType)


# ── Questions ──

class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=500)
    content: str
    content_hash: str | None = Field(default=None, max_length=128)
    source_type: str = Field(max_length=50)
    source_id: str | None = Field(default=None, max_length=255)
    source_ref: str | None = Field(default=None, max_length=255)
    source_excerpt: str | None = None
    question_type: str | None = Field(default=None, max_length=50)
    domain_type: str | None = Field(default=None, max_length=100)
    difficulty_level: int | None = None
    difficulty_score: float | None = None
    answer_summary: str | None = None
    answer_detail: str | None = None
    explanation: str | None = None
    common_pitfalls: str | None = None
    mastery_level: int | None = None
    review_status: str | None = Field(default=None, max_length=50)
    version: int = Field(default=1)
    model_version: str | None = Field(default=None, max_length=100)
    prompt_version: str | None = Field(default=None, max_length=100)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    deleted_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    tags: list["QuestionTag"] = Relationship(back_populates="question")
    knowledge_nodes: list["QuestionKnowledgeNode"] = Relationship(back_populates="question")
    embeddings: list["QuestionEmbedding"] = Relationship(back_populates="question")
    study_records: list["StudyRecord"] = Relationship(back_populates="question")
    chat_histories: list["ChatHistory"] = Relationship(back_populates="question")


# ── Tags ──

class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100)
    tag_type: str = Field(max_length=50)
    description: str | None = None
    color: str | None = Field(default=None, max_length=20)
    version: int = Field(default=1)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    questions: list["QuestionTag"] = Relationship(back_populates="tag")


# ── Question_Tags ──

class QuestionTag(SQLModel, table=True):
    __tablename__ = "question_tags"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="questions.id")
    tag_id: uuid.UUID = Field(foreign_key="tags.id")
    source_type: str | None = Field(default=None, max_length=50)
    confidence: float | None = None
    version: int = Field(default=1)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)

    question: "Question" = Relationship(back_populates="tags")
    tag: "Tag" = Relationship(back_populates="questions")


# ── Knowledge_Nodes ──

class KnowledgeNode(SQLModel, table=True):
    __tablename__ = "knowledge_nodes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=200)
    description: str | None = None
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="knowledge_nodes.id")
    node_type: str = Field(max_length=50)
    depth_level: int | None = None
    version: int = Field(default=1)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    parent: "KnowledgeNode | None" = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "KnowledgeNode.id"},
    )
    children: list["KnowledgeNode"] = Relationship(back_populates="parent")
    questions: list["QuestionKnowledgeNode"] = Relationship(back_populates="knowledge_node")


# ── Question_Knowledge_Nodes ──

class QuestionKnowledgeNode(SQLModel, table=True):
    __tablename__ = "question_knowledge_nodes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="questions.id")
    knowledge_node_id: uuid.UUID = Field(foreign_key="knowledge_nodes.id")
    relation_type: str = Field(max_length=50)
    confidence: float | None = None
    source_type: str | None = Field(default=None, max_length=50)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)

    question: "Question" = Relationship(back_populates="knowledge_nodes")
    knowledge_node: "KnowledgeNode" = Relationship(back_populates="questions")


# ── Study_Records ──

class StudyRecord(SQLModel, table=True):
    __tablename__ = "study_records"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str | None = Field(default=None, max_length=255)
    session_id: str | None = Field(default=None, max_length=100)
    question_id: uuid.UUID | None = Field(default=None, foreign_key="questions.id")
    study_type: str = Field(max_length=50)
    user_answer: str | None = None
    ai_score: int | None = None
    ai_feedback: str | None = None
    mastery_level: int | None = None
    duration_seconds: int | None = None
    review_result: str | None = Field(default=None, max_length=50)
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    next_review_at: datetime | None = None
    model_version: str | None = Field(default=None, max_length=100)
    prompt_version: str | None = Field(default=None, max_length=100)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    question: "Question | None" = Relationship(back_populates="study_records")


# ── Chat_Histories ──

class ChatHistory(SQLModel, table=True):
    __tablename__ = "chat_histories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: str = Field(max_length=100)
    user_id: str | None = Field(default=None, max_length=255)
    role: str = Field(max_length=20)
    message: str
    message_type: str | None = Field(default=None, max_length=50)
    related_question_id: uuid.UUID | None = Field(default=None, foreign_key="questions.id")
    evaluation_score: int | None = None
    evaluation_summary: str | None = None
    model_version: str | None = Field(default=None, max_length=100)
    prompt_version: str | None = Field(default=None, max_length=100)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)

    question: "Question | None" = Relationship(back_populates="chat_histories")


# ── Files ──

class File(SQLModel, table=True):
    __tablename__ = "files"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    file_name: str = Field(max_length=255)
    file_path: str = Field(max_length=500)
    file_type: str = Field(max_length=50)
    source_type: str = Field(max_length=50)
    parse_status: str = Field(max_length=50)
    parse_error: str | None = None
    file_hash: str | None = Field(default=None, max_length=128)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Question_Embeddings ──

class QuestionEmbedding(SQLModel, table=True):
    __tablename__ = "question_embeddings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="questions.id")
    embedding: list[float] = Field(sa_column=_vector_column())
    model_name: str = Field(max_length=100)
    model_version: str | None = Field(default=None, max_length=100)
    dimension: int | None = None
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)

    question: "Question" = Relationship(back_populates="embeddings")


# ── Prompt_Versions ──

class PromptVersion(SQLModel, table=True):
    __tablename__ = "prompt_versions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    prompt_key: str = Field(max_length=100)
    prompt_content: str
    prompt_version: str = Field(max_length=100)
    model_version: str | None = Field(default=None, max_length=100)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Learning_Profiles ──

class LearningProfile(SQLModel, table=True):
    __tablename__ = "learning_profiles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str = Field(max_length=255)
    weak_topics: dict | None = Field(default=None, sa_column=_jsonb_column())
    strong_topics: dict | None = Field(default=None, sa_column=_jsonb_column())
    mastery_map: dict | None = Field(default=None, sa_column=_jsonb_column())
    review_cycle: str | None = Field(default=None, max_length=50)
    extra_data: dict | None = Field(default=None, sa_column=_jsonb_column())
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Expose metadata for Alembic ──

Base = SQLModel.metadata

