# Auto-generated service stub for StatutoryActuary
# Add business logic here; the router delegates to this layer.

from app.repositories.statutory_actuary_repository import StatutoryActuaryRepository


class StatutoryActuaryService:
    """Business-logic layer for StatutoryActuary.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: StatutoryActuaryRepository):
        self.repo = repo
