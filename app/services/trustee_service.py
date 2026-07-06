# Auto-generated service stub for Trustee
# Add business logic here; the router delegates to this layer.

from app.repositories.trustee_repository import TrusteeRepository


class TrusteeService:
    """Business-logic layer for Trustee.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: TrusteeRepository):
        self.repo = repo
