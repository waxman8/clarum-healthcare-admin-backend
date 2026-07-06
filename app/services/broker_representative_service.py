# Auto-generated service stub for Broker
# Add business logic here; the router delegates to this layer.

from app.repositories.broker_representative_repository import BrokerRepository


class BrokerService:
    """Business-logic layer for Broker.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: BrokerRepository):
        self.repo = repo
