from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.adherence_report import AdherenceReportResponse
from app.security import limiter, verify_api_key
from app.services.adherence_service import adherence_service
from app.services.user_service import user_service

router = APIRouter(
    prefix="/reports", tags=["reports"], dependencies=[Depends(verify_api_key)]
)


class ReportResult(BaseModel):
    """Serializable response for report generation."""

    report: AdherenceReportResponse
    whatsapp_message: str
    pdf_path: str | None = None
    medication_breakdown: list[dict] = []


@router.post("/generate/weekly", response_model=ReportResult)
@limiter.limit("5/minute")
async def generate_weekly_report(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate a weekly text-only adherence report."""
    user = await user_service.get_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_name = user.profile.first_name
    if not user_name or user_name.strip().lower() == "new":
        user_name = "User"
    now = datetime.now(UTC)
    start = now - timedelta(days=7)

    result = await adherence_service.generate_report(
        db,
        user_id=user_id,
        user_name=user_name,
        report_type="weekly",
        period_start=start,
        period_end=now,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result["error"],
        )

    return result


@router.post("/generate/monthly", response_model=ReportResult)
@limiter.limit("5/minute")
async def generate_monthly_report(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Generate a monthly adherence report with PDF attachment."""
    user = await user_service.get_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_name = user.profile.first_name or "User"
    now = datetime.now(UTC)
    start = now - timedelta(days=30)

    result = await adherence_service.generate_report(
        db,
        user_id=user_id,
        user_name=user_name,
        report_type="monthly",
        period_start=start,
        period_end=now,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result["error"],
        )

    return result


@router.get(
    "/history",
    response_model=list[AdherenceReportResponse],
)
async def get_report_history(
    request: Request,
    user_id: UUID,
    report_type: str | None = Query(
        None, description="Filter by 'weekly' or 'monthly'"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve past adherence reports for a user."""
    return await adherence_service.get_user_reports(
        db, user_id, report_type=report_type
    )
