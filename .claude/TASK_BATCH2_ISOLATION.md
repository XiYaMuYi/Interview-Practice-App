# Batch 2: data_isolation 工具模块 + deps 改造

## 必读
- `backend/app/api/deps.py` — 现有认证依赖

## 任务

### 1. 新建 data_isolation 模块

创建 `backend/app/infra/data_isolation.py`，内容：

```python
"""Data isolation utilities — multi-tenant user context and ownership checks."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import HTTPException


@dataclass
class UserContext:
    """用户上下文，用于数据隔离查询。"""
    user_id: Optional[str]
    is_anonymous: bool
    is_admin: bool = False


def apply_user_filter(
    filters: Dict[str, Any],
    ctx: UserContext,
    table_has_user_id: bool = True,
    allow_public: bool = False,
) -> Dict[str, Any]:
    """将 user_id 注入查询过滤器。"""
    if ctx.is_admin:
        return filters

    if ctx.is_anonymous:
        if allow_public and table_has_user_id:
            filters["__user_filter_mode"] = "public_only"
        return filters

    if table_has_user_id:
        filters["__user_filter_mode"] = "owned_or_public"
        filters["__user_id"] = ctx.user_id

    return filters


def check_resource_ownership(
    ctx: UserContext,
    resource_user_id: Optional[str],
    resource_name: str = "resource",
) -> bool:
    """检查资源归属。"""
    if ctx.is_admin:
        return True
    if ctx.is_anonymous:
        return resource_user_id is None
    return resource_user_id is None or resource_user_id == ctx.user_id


def ensure_owned_by(
    ctx: UserContext,
    resource_user_id: Optional[str],
    resource_name: str = "resource",
) -> None:
    """确保资源属于当前用户，否则抛出 HTTPException。"""
    if ctx.is_anonymous:
        raise HTTPException(status_code=401, detail="需要登录才能访问此资源")
    if not check_resource_ownership(ctx, resource_user_id, resource_name):
        raise HTTPException(status_code=403, detail=f"无权访问此{resource_name}")
```

### 2. 改造 deps.py

在 `backend/app/api/deps.py` 中：
- 添加 `from dataclasses import dataclass`（如果没有）
- 添加 `from app.infra.data_isolation import UserContext`
- 新增 `get_user_context` 依赖函数

```python
async def get_user_context(
    current_user: User | None = Depends(get_current_user),
) -> UserContext:
    if current_user is None:
        return UserContext(user_id=None, is_anonymous=True, is_admin=False)
    return UserContext(
        user_id=str(current_user.id),
        is_anonymous=False,
        is_admin=current_user.role == "admin",
    )
```

## 完成标准
- `backend/app/infra/data_isolation.py` 存在
- `deps.py` 有 `get_user_context`
- 不需要 docker 重建
