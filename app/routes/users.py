from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.security import limiter, verify_api_key
from app.services.user_service import user_service

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(verify_api_key)]
)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_user(
    request: Request, obj_in: UserCreate, db: AsyncSession = Depends(get_db)
):
    """Register a new user and profile."""
    # Check if a user with this WhatsApp number already exists
    existing_user = await user_service.get_by_whatsapp_number(
        db, whatsapp_number=obj_in.profile.whatsapp_number
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp number already registered",
        )

    return await user_service.create(db, user_in=obj_in)


@router.get("/{user_id}", response_model=UserResponse)
@limiter.limit("30/minute")
async def get_user(request: Request, user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve a user's details."""
    user = await user_service.get_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch("/{user_id}", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_user(
    request: Request,
    user_id: UUID,
    obj_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update user or profile information."""
    db_user = await user_service.get_by_id(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return await user_service.update(db, db_obj=db_user, obj_in=obj_in)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def delete_user(
    request: Request, user_id: UUID, db: AsyncSession = Depends(get_db)
):
    """Soft-delete a user account, scheduling it for permanent removal in 90 days."""
    db_user = await user_service.get_by_id(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await user_service.soft_delete(db, user_id=user_id)
    return {"message": "Account scheduled for deletion"}
