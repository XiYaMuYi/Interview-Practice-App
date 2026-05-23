"""Event type constants."""

# Task lifecycle
TASK_CREATED = "task.created"
TASK_STARTED = "task.started"
TASK_DONE = "task.done"
TASK_FAILED = "task.failed"

# Processing events
CHUNK_PROCESSED = "chunk.processed"
QUESTION_GENERATED = "question.generated"
FOLLOWUP_GENERATED = "followup.generated"

# LLM events
LLM_CALL_SUCCESS = "llm.call.success"
LLM_CALL_FAILED = "llm.call.failed"

# Cache events
CACHE_HIT = "cache.hit"
CACHE_MISS = "cache.miss"
