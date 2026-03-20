"""
api/v1/staging.py - Staging data preview and summary endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from infrastructure.storage import in_memory_store as store

router = APIRouter(prefix="/staging", tags=["Staging"])


@router.get("/summary")
def get_staging_overview():
    """Return row count per staging table."""
    summary = store.get_staging_summary()
    return {
        "tables": [{"table": t, "rows": r} for t, r in summary.items()],
        "total_rows": sum(summary.values()),
    }


@router.get("/{table_name}")
def get_staging_table_preview(
    table_name: str,
    limit: int = Query(20, le=500),
    offset: int = Query(0, ge=0),
):
    """Paginated preview of a staging table's loaded data."""
    df = store.get_staging_table(table_name)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    total = len(df)
    page = df.iloc[offset: offset + limit]

    return {
        "table": table_name,
        "total_rows": total,
        "offset": offset,
        "limit": limit,
        "columns": list(page.columns),
        "rows": page.where(page.notna(), None).to_dict(orient="records"),
    }
