# Auto-generated service stub for Brokerage
# Add business logic here; the router delegates to this layer.

from app.repositories.brokerage_fsp_repository import BrokerageRepository


class BrokerageService:
    """Business-logic layer for Brokerage.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: BrokerageRepository):
        self.repo = repo
