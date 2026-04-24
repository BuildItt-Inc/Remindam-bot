from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserProfile
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Service layer for user CRUD and lifecycle management."""

    async def get_by_id(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> User | None:
        """Get a user by ID, including their profile."""
        query = (
            select(User).options(selectinload(User.profile)).where(User.id == user_id)
        )
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_whatsapp_number(
        self,
        db: AsyncSession,
        whatsapp_number: str,
        *,
        include_deleted: bool = False,
    ) -> User | None:
        """Get a user by their WhatsApp number, including profile."""
        query = (
            select(User)
            .join(UserProfile)
            .options(selectinload(User.profile))
            .where(UserProfile.whatsapp_number == whatsapp_number)
        )
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        result = await db.execute(query)
        return result.scalars().first()

    async def create(self, db: AsyncSession, user_in: UserCreate) -> User:
        """Create a new user with their profile."""
        new_user = User()
        db.add(new_user)
        await db.flush()

        profile_data = user_in.profile.model_dump()
        new_profile = UserProfile(user_id=new_user.id, **profile_data)
        db.add(new_profile)

        await db.commit()
        await db.refresh(new_user)
        return await self.get_by_id(db, new_user.id)

    async def update(
        self, db: AsyncSession, *, db_obj: User, obj_in: UserUpdate | dict
    ) -> User:
        """Update a user and/or their profile."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if "is_active" in update_data:
            db_obj.is_active = update_data["is_active"]

        if "profile" in update_data and db_obj.profile:
            profile_data = update_data["profile"]
            for field, value in profile_data.items():
                setattr(db_obj.profile, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return await self.get_by_id(db, db_obj.id)

    async def soft_delete(self, db: AsyncSession, user_id: UUID) -> User | None:
        """Mark a user as deleted without removing their data."""
        user = await self.get_by_id(db, user_id)
        if not user:
            return None

        user.is_active = False
        user.deleted_at = datetime.now(UTC)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def restore_account(self, db: AsyncSession, user_id: UUID) -> User | None:
        """Reactivate a soft-deleted user within the 90-day window."""
        user = await self.get_by_id(db, user_id, include_deleted=True)
        if not user or user.deleted_at is None:
            return None

        cutoff = datetime.now(UTC) - timedelta(days=90)
        if user.deleted_at < cutoff:
            return None

        user.is_active = True
        user.deleted_at = None
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


user_service = UserService()
