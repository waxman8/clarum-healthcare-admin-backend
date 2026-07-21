import secrets
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.auth import User, AuditLog
from app.schemas.user import UserCreate, UserUpdate
from app.repositories.user_repository import UserRepository
from app.auth.security import get_password_hash
from app.integrations.registry import get as get_integration
from app.integrations.contracts import MessagingGateway


class UserService:
    """Business-logic layer for User, enforcing validation, deactivation guards,
    notifications, and audit logs.
    """

    def __init__(self, repo: UserRepository, db: AsyncSession):
        self.repo = repo
        self.db = db

    def _get_messaging_gateway(self) -> MessagingGateway:
        return get_integration(MessagingGateway)

    def _generate_temp_password(self) -> str:
        # Generate a secure temporary password with letters, digits, and a special character
        return f"Clarum@{secrets.token_hex(4)}1!"

    async def list_users(
        self,
        current_user: User,
        search: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[User], int]:
        # Scoped strictly to the active Super Admin's scheme
        return await self.repo.list(
            scheme_id=current_user.scheme_id,
            search=search,
            role=role,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def get_user(self, user_id: int, current_user: User) -> Optional[User]:
        # Cross-scheme leak check is handled implicitly by passing the current_user's scheme_id
        return await self.repo.get(user_id, current_user.scheme_id)

    async def create_user(self, payload: UserCreate, current_user: User) -> User:
        # Override scheme_id to ensure the created user belongs to the same scheme as the creator
        payload.scheme_id = current_user.scheme_id

        # Generate temporary password
        temp_password = self._generate_temp_password()
        hashed_password = get_password_hash(temp_password)

        # Create user
        user = await self.repo.create(payload, hashed_password)

        # Write AuditLog
        audit = AuditLog(
            user_id=current_user.id,
            entity_type="user",
            entity_id=user.id,
            action="create",
            old_value=None,
            new_value=f"email={user.email}, role={user.role}",
            user_role=current_user.role,
        )
        self.db.add(audit)
        await self.db.flush()

        # Send welcome email containing the temporary password
        gateway = self._get_messaging_gateway()
        subject = "Welcome to Clarum Healthcare Portal"
        body_text = (
            f"Hello {user.full_name},\n\n"
            f"An account has been created for you on the Clarum Healthcare Portal.\n"
            f"Your temporary password is: {temp_password}\n"
            f"You will be required to change your password upon logging in for the first time.\n\n"
            f"Regards,\n"
            f"System Administrator"
        )
        body_html = (
            f"<p>Hello {user.full_name},</p>"
            f"<p>An account has been created for you on the Clarum Healthcare Portal.</p>"
            f"<p>Your temporary password is: <strong>{temp_password}</strong></p>"
            f"<p>You will be required to change your password upon logging in for the first time.</p>"
            f"<p>Regards,<br>System Administrator</p>"
        )
        gateway.send_email(
            to=user.email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

        return user

    async def update_user(self, user_id: int, payload: UserUpdate, current_user: User) -> Optional[User]:
        # Fetch existing user within the same scheme
        existing_user = await self.repo.get(user_id, current_user.scheme_id)
        if not existing_user:
            return None

        # Guard: Cannot deactivate yourself
        if payload.is_active is False and user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )

        # Capture old values for audit logging
        old_role = existing_user.role
        old_is_active = existing_user.is_active
        old_full_name = existing_user.full_name

        # Perform update
        updated_user = await self.repo.update(user_id, payload, current_user.scheme_id)

        # Determine state changes and write audit logs
        if payload.role is not None and payload.role != old_role:
            audit = AuditLog(
                user_id=current_user.id,
                entity_type="user",
                entity_id=user_id,
                action="role_change",
                old_value=old_role,
                new_value=payload.role,
                user_role=current_user.role,
            )
            self.db.add(audit)

        if payload.is_active is not None and payload.is_active != old_is_active:
            action = "activate" if payload.is_active else "deactivate"
            audit = AuditLog(
                user_id=current_user.id,
                entity_type="user",
                entity_id=user_id,
                action=action,
                old_value=str(old_is_active),
                new_value=str(payload.is_active),
                user_role=current_user.role,
            )
            self.db.add(audit)

        if payload.full_name is not None and payload.full_name != old_full_name:
            audit = AuditLog(
                user_id=current_user.id,
                entity_type="user",
                entity_id=user_id,
                action="name_change",
                old_value=old_full_name,
                new_value=payload.full_name,
                user_role=current_user.role,
            )
            self.db.add(audit)

        await self.db.flush()
        return updated_user

    async def deactivate_user(self, user_id: int, current_user: User) -> bool:
        # Guard: Cannot deactivate yourself
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )

        existing_user = await self.repo.get(user_id, current_user.scheme_id)
        if not existing_user:
            return False

        if not existing_user.is_active:
            return True  # Already deactivated

        await self.repo.deactivate(user_id, current_user.scheme_id)

        # Write AuditLog
        audit = AuditLog(
            user_id=current_user.id,
            entity_type="user",
            entity_id=user_id,
            action="deactivate",
            old_value="True",
            new_value="False",
            user_role=current_user.role,
        )
        self.db.add(audit)
        await self.db.flush()

        return True

    async def force_password_reset(self, user_id: int, current_user: User) -> bool:
        existing_user = await self.repo.get(user_id, current_user.scheme_id)
        if not existing_user:
            return False

        # Generate temporary password
        temp_password = self._generate_temp_password()
        hashed_password = get_password_hash(temp_password)

        # Update model directly
        existing_user.hashed_password = hashed_password
        existing_user.must_reset_password = True
        await self.db.flush()

        # Write AuditLog
        audit = AuditLog(
            user_id=current_user.id,
            entity_type="user",
            entity_id=user_id,
            action="reset",
            old_value="False",
            new_value="True",
            user_role=current_user.role,
        )
        self.db.add(audit)
        await self.db.flush()

        # Send password-reset email containing the temporary password
        gateway = self._get_messaging_gateway()
        subject = "Forced Password Reset - Clarum Healthcare Portal"
        body_text = (
            f"Hello {existing_user.full_name},\n\n"
            f"Your account password has been reset by an administrator.\n"
            f"Your temporary password is: {temp_password}\n"
            f"You will be required to change your password upon logging in.\n\n"
            f"Regards,\n"
            f"System Administrator"
        )
        body_html = (
            f"<p>Hello {existing_user.full_name},</p>"
            f"<p>Your account password has been reset by an administrator.</p>"
            f"<p>Your temporary password is: <strong>{temp_password}</strong></p>"
            f"<p>You will be required to change your password upon logging in.</p>"
            f"<p>Regards,<br>System Administrator</p>"
        )
        gateway.send_email(
            to=existing_user.email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

        return True
