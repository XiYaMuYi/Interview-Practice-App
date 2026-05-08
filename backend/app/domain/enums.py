import enum


class SourceType(str, enum.Enum):
    upload = "upload"
    paste = "paste"
    manual = "manual"
    web = "web"


class QuestionType(str, enum.Enum):
    concept = "concept"
    compare = "compare"
    scenario = "scenario"
    architecture = "architecture"
    project = "project"
    followup = "followup"


class DomainType(str, enum.Enum):
    rag = "RAG"
    agent = "Agent"
    langgraph = "LangGraph"
    prompting = "Prompting"
    vector_db = "VectorDB"
    deployment = "Deployment"
    evaluation = "Evaluation"
    general = "General"


class TagType(str, enum.Enum):
    domain = "domain"
    difficulty = "difficulty"
    status = "status"
    custom = "custom"


class TagSourceType(str, enum.Enum):
    manual = "manual"
    ai = "ai"
    rule = "rule"


class RelationType(str, enum.Enum):
    prerequisite = "prerequisite"
    related = "related"
    same_domain = "same_domain"
    deepens = "deepens"


class NodeType(str, enum.Enum):
    concept = "concept"
    prerequisite = "prerequisite"
    topic = "topic"


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


class StudyType(str, enum.Enum):
    review = "review"
    practice = "practice"
    mock = "mock"
    interview = "interview"
    chat = "chat"


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    mastered = "mastered"
    needs_reinforcement = "needs_reinforcement"
