"""Prompt 版本管理与可观测性 API 路由。

提供 prompt 模板的查询、版本列表、版本对比、调用统计等只读接口，
以及新版本的注册接口（追加写，不允许修改已有版本）。
"""

from datetime import datetime

import difflib
from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.domain.schemas import (
    LLMCallLogResponse,
    PromptStats,
    PromptVersionCompare,
    PromptVersionCreate,
    PromptVersionDetail,
    PromptVersionInfo,
)
from app.infra.llm.prompt_registry import prompt_registry

router = APIRouter()


@router.get("/", response_model=list[PromptVersionInfo])
async def list_prompts():
    """列出所有已注册的 prompt 模板（key + 当前活跃版本）。

    从内存中的 PromptRegistry 读取，返回每个 key 的最新版模板元信息。
    """
    keys = prompt_registry.list_keys()
    result = []
    for key in keys:
        tpl = prompt_registry.get_template(key)
        if tpl:
            result.append(
                PromptVersionInfo(
                    id=None,  # 内存模板无 DB id
                    key=tpl.key,
                    version=tpl.version,
                    description=tpl.description,
                    created_at=tpl.created_at,
                    is_active=tpl.is_active,
                )
            )
    return result

# 无尾斜杠版本（redirect_slashes=False 导致 /prompts 不会自动重定向到 /prompts/）
@router.get("", response_model=list[PromptVersionInfo])
async def list_prompts_no_slash():
    return await list_prompts()


@router.get("/{key}/versions", response_model=list[dict])
async def list_prompt_versions(key: str, session: DbSession):
    """列出某个 prompt key 的所有历史版本。

    从 `prompt_versions` 数据库表中查询，按创建时间倒序返回。
    """
    versions = await prompt_registry.list_versions(key, session)
    if not versions:
        # 如果数据库中没有，回退到检查内存注册模板
        tpl = prompt_registry.get_template(key)
        if tpl:
            return [
                {
                    "id": None,
                    "prompt_key": tpl.key,
                    "prompt_version": tpl.version,
                    "model_version": tpl.model_hints.get("model") if tpl.model_hints else None,
                    "created_at": tpl.created_at,
                }
            ]
    return versions


@router.get("/{key}/versions/{version}", response_model=PromptVersionDetail)
async def get_prompt_version_detail(key: str, version: str, session: DbSession):
    """查看某个 prompt 版本的完整内容。

    优先从数据库读取；如果数据库中没有，回退到内存中的注册模板。
    """
    from sqlmodel import select

    from app.domain.models import PromptVersion

    stmt = select(PromptVersion).where(
        PromptVersion.prompt_key == key,
        PromptVersion.prompt_version == version,
    )
    result = await session.exec(stmt)
    pv = result.first()

    if pv:
        model_hints = pv.extra_data.get("model_hints", {}) if pv.extra_data else {}
        description = pv.extra_data.get("description", "") if pv.extra_data else ""
        return PromptVersionDetail(
            id=pv.id,
            key=pv.prompt_key,
            version=pv.prompt_version,
            description=description,
            content=pv.prompt_content,
            model_hints=model_hints,
            created_at=pv.created_at,
            is_active=True,
        )

    # 回退到内存模板
    tpl = prompt_registry.get_template(key)
    if tpl and tpl.version == version:
        return PromptVersionDetail(
            id=tpl.key,
            key=tpl.key,
            version=tpl.version,
            description=tpl.description,
            content=tpl.system_template,
            model_hints=tpl.model_hints,
            created_at=tpl.created_at,
            is_active=tpl.is_active,
        )

    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"Prompt version {key}@{version} not found")


@router.get("/compare", response_model=PromptVersionCompare)
@router.get("compare", response_model=PromptVersionCompare)
async def compare_prompt_versions(
    key: str,
    v1: str = Query(..., description="第一个版本号"),
    v2: str = Query(..., description="第二个版本号"),
    session: DbSession = None,
):
    """比较同一个 prompt key 的两个版本，返回 diff 文本。

    按行对比两个版本的 system_template/content，输出 unified diff。
    """
    from sqlmodel import select

    from app.domain.models import PromptVersion

    async def _get_content(ver: str) -> str | None:
        stmt = select(PromptVersion).where(
            PromptVersion.prompt_key == key,
            PromptVersion.prompt_version == ver,
        )
        result = await session.exec(stmt)
        pv = result.first()
        if pv:
            return pv.prompt_content
        tpl = prompt_registry.get_template(key)
        if tpl and tpl.version == ver:
            return tpl.system_template
        return None

    content_v1 = await _get_content(v1)
    content_v2 = await _get_content(v2)

    if content_v1 is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Version {v1} not found for prompt '{key}'")
    if content_v2 is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Version {v2} not found for prompt '{key}'")

    diff_lines = difflib.unified_diff(
        content_v1.splitlines(keepends=True),
        content_v2.splitlines(keepends=True),
        fromfile=f"{key}@{v1}",
        tofile=f"{key}@{v2}",
        lineterm="",
    )
    diff_text = "".join(diff_lines)

    # 生成简短的 diff 摘要
    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    diff_summary = f"+{added} lines, -{removed} lines"

    return PromptVersionCompare(
        key=key,
        v1_version=v1,
        v1_content=content_v1,
        v2_version=v2,
        v2_content=content_v2,
        diff_summary=diff_summary,
    )


@router.get("/{key}/stats", response_model=PromptStats)
async def get_prompt_stats(key: str, days: int = Query(default=7, ge=1, le=90), session: DbSession = None):
    """查看某个 prompt 的调用统计。

    基于 `llm_call_logs` 表聚合计算：总调用次数、成功率、平均耗时、错误率。
    默认统计最近 7 天的数据。
    """
    from sqlmodel import select, func
    from datetime import timedelta

    from app.domain.models import LLMCallLog

    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            func.count(LLMCallLog.id).label("total_calls"),
            func.sum(func.case((LLMCallLog.status == "success", 1), else_=0)).label("success_count"),
            func.avg(LLMCallLog.duration_ms).label("avg_duration"),
        )
        .where(LLMCallLog.prompt_key == key, LLMCallLog.created_at >= cutoff)
    )
    result = await session.exec(stmt)
    row = result.first()

    if not row or row.total_calls == 0:
        return PromptStats(
            key=key,
            total_calls=0,
            success_rate=0.0,
            avg_duration_ms=0.0,
            error_rate=0.0,
        )

    total_calls = row.total_calls
    success_count = row.success_count or 0
    avg_duration = float(row.avg_duration) if row.avg_duration else 0.0
    success_rate = success_count / total_calls if total_calls > 0 else 0.0
    error_rate = 1.0 - success_rate

    return PromptStats(
        key=key,
        total_calls=total_calls,
        success_rate=round(success_rate, 4),
        avg_duration_ms=round(avg_duration, 1),
        error_rate=round(error_rate, 4),
    )


@router.post("/{key}/versions", response_model=dict)
async def register_prompt_version(
    key: str,
    data: PromptVersionCreate,
    session: DbSession,
):
    """注册一个新的 prompt 版本到数据库。

    这是追加写操作，不会修改已有的版本。新注册的版本会自动写入
    `prompt_versions` 表，但不会替换内存中的模板。
    """
    result = await prompt_registry.save_version(
        key=key,
        version=data.version,
        content=data.content,
        model_hints=data.model_hints or None,
        description=data.description,
        session=session,
    )
    return {"status": "registered", **result}
