from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.medication import MedicationCreate, MedicationResponse
from app.security import limiter, verify_api_key
from app.services.medication import medication_service

router = APIRouter(
    prefix="/medications", tags=["medications"], dependencies=[Depends(verify_api_key)]
)


@router.post(
    "/",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_medication(
    request: Request,
    user_id: UUID,
    obj_in: MedicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new medication for a user."""
    try:
        return await medication_service.create_medication(
            db, user_id=user_id, obj_in=obj_in
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/user/{user_id}", response_model=list[MedicationResponse])
@limiter.limit("30/minute")
async def list_user_medications(
    request: Request, user_id: UUID, db: AsyncSession = Depends(get_db)
):
    """List all active medications for a specific user."""
    return await medication_service.get_user_medications(db, user_id=user_id)
