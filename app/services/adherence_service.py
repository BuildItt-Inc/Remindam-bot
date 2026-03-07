from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.adherence_report import AdherenceReport
from app.models.medication import MedicationSchedule
from app.models.reminder import ReminderLog
from app.services.report_formatter import (
    format_whatsapp_report,
    generate_pdf_report,
)
from app.services.subscription_service import subscription_service


class AdherenceService:
    """Generates weekly/monthly adherence reports for users (paid feature).

    The report flow:
    1. User requests a report via WhatsApp (e.g., "Send my weekly report")
    2. This service calculates stats from ReminderLog
    3. Returns a formatted WhatsApp message + a PDF file path
    4. The WhatsApp service sends the text message and attaches the PDF
    """

    async def generate_report(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        user_name: str,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict:
        """Generate a full adherence report.

        Returns a dict with:
          - "report": the saved AdherenceReport model instance
          - "whatsapp_message": formatted text for WhatsApp
          - "pdf_path": path to the generated PDF file
          - "medication_breakdown": per-medication stats
        """
        # ── 0. Check Authorization ──
        has_access = await subscription_service.can_access_reports(db, user_id)
        if not has_access:
            return {
                "error": (
                    "weekly adherence reports are only available with an active "
                    "subscription. Upgrade for just ₦500/month!"
                )
            }

        # ── 1. Overall stats ──
        total_reminders = await self._count_reminders(
            db, user_id, period_start, period_end, statuses=["sent", "taken", "missed"]
        )
        taken_count = await self._count_reminders(
            db, user_id, period_start, period_end, statuses=["taken"]
        )
        missed_count = await self._count_reminders(
            db, user_id, period_start, period_end, statuses=["missed"]
        )

        adherence_percentage = (
            (taken_count / total_reminders * 100) if total_reminders > 0 else 0.0
        )

        # ── 2. Per-medication breakdown ──
        medication_breakdown = await self._get_medication_breakdown(
            db, user_id, period_start, period_end
        )

        # ── 3. Save report to DB ──
        report = AdherenceReport(
            user_id=user_id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            total_reminders=total_reminders,
            taken_count=taken_count,
            missed_count=missed_count,
            adherence_percentage=round(adherence_percentage, 1),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

        # ── 4. Generate formatted outputs ──
        format_kwargs = dict(
            user_name=user_name,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            total_reminders=total_reminders,
            taken_count=taken_count,
            missed_count=missed_count,
            adherence_percentage=round(adherence_percentage, 1),
            medication_breakdown=medication_breakdown,
        )

        whatsapp_message = format_whatsapp_report(**format_kwargs)
        pdf_path = generate_pdf_report(**format_kwargs)

        return {
            "report": report,
            "whatsapp_message": whatsapp_message,
            "pdf_path": pdf_path,
            "medication_breakdown": medication_breakdown,
        }

    async def get_user_reports(
        self,
        db: AsyncSession,
        user_id: UUID,
        report_type: str | None = None,
    ) -> list[AdherenceReport]:
        """Fetch all reports for a user, optionally filtered by type."""
        query = select(AdherenceReport).where(AdherenceReport.user_id == user_id)
        if report_type:
            query = query.where(AdherenceReport.report_type == report_type)

        query = query.order_by(AdherenceReport.period_end.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    # ── Private helpers ──

    async def _count_reminders(
        self,
        db: AsyncSession,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime,
        *,
        statuses: list[str],
    ) -> int:
        """Count reminder logs matching the given statuses within a period."""
        query = (
            select(func.count())
            .select_from(ReminderLog)
            .where(
                ReminderLog.user_id == user_id,
                ReminderLog.scheduled_for >= period_start,
                ReminderLog.scheduled_for <= period_end,
                ReminderLog.status.in_(statuses),
            )
        )
        result = await db.execute(query)
        return result.scalar() or 0

    async def _get_medication_breakdown(
        self,
        db: AsyncSession,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict]:
        """Get per-medication adherence stats for the period."""
        # Fetch all relevant reminder logs with medication info
        query = (
            select(ReminderLog)
            .options(
                selectinload(ReminderLog.schedule).selectinload(
                    MedicationSchedule.medication
                )
            )
            .where(
                ReminderLog.user_id == user_id,
                ReminderLog.scheduled_for >= period_start,
                ReminderLog.scheduled_for <= period_end,
                ReminderLog.status.in_(["sent", "taken", "missed"]),
            )
        )
        result = await db.execute(query)
        logs = result.scalars().all()

        # Group by medication
        med_stats: dict[str, dict] = {}
        for log in logs:
            med = log.schedule.medication
            key = str(med.id)
            if key not in med_stats:
                med_stats[key] = {
                    "name": med.name,
                    "form": med.medication_form,
                    "taken": 0,
                    "missed": 0,
                    "total": 0,
                }
            med_stats[key]["total"] += 1
            if log.status == "taken":
                med_stats[key]["taken"] += 1
            elif log.status == "missed":
                med_stats[key]["missed"] += 1

        # Calculate per-medication adherence
        breakdown = []
        for stats in med_stats.values():
            adherence = (
                (stats["taken"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
            )
            breakdown.append({**stats, "adherence": round(adherence, 1)})

        # Sort by adherence (lowest first so user sees problem areas)
        breakdown.sort(key=lambda x: x["adherence"])
        return breakdown


adherence_service = AdherenceService()
