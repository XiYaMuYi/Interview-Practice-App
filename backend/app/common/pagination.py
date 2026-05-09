"""Shared pagination utilities for routes and services."""

from math import ceil

from fastapi import Query


def parse_pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """Return validated page/page_size with offset calculation."""
    offset = (page - 1) * page_size
    return {"page": page, "page_size": page_size, "offset": offset}


def build_paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    """Build unified paginated response dict."""
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(total / page_size) if page_size > 0 else 0,
    }
