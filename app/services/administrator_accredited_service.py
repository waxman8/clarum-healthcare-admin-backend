# Auto-generated service stub for Administrator
# Add business logic here; the router delegates to this layer.

from app.repositories.administrator_accredited_repository import AdministratorRepository


class AdministratorService:
    """Business-logic layer for Administrator.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: AdministratorRepository):
        self.repo = repo
