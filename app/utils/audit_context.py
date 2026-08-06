from contextvars import ContextVar
from typing import Optional
from app.models.auth import User

# Context variable to store the current user for auditing purposes
current_user_context: ContextVar[Optional[User]] = ContextVar("current_user_context", default=None)

def set_current_user(user: User):
    current_user_context.set(user)

def get_current_user_context() -> Optional[User]:
    return current_user_context.get()
