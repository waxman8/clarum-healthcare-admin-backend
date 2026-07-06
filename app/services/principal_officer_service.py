# Auto-generated service stub for PrincipalOfficer
# Add business logic here; the router delegates to this layer.

from app.repositories.principal_officer_repository import PrincipalOfficerRepository


class PrincipalOfficerService:
    """Business-logic layer for PrincipalOfficer.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: PrincipalOfficerRepository):
        self.repo = repo
