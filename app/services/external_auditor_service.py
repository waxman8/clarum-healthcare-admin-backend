# Auto-generated service stub for ExternalAuditor
# Add business logic here; the router delegates to this layer.

from app.repositories.external_auditor_repository import ExternalAuditorRepository


class ExternalAuditorService:
    """Business-logic layer for ExternalAuditor.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: ExternalAuditorRepository):
        self.repo = repo
