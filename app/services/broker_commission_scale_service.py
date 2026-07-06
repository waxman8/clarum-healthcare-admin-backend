# Auto-generated service stub for BrokerCommissionScale
# Add business logic here; the router delegates to this layer.

from app.repositories.broker_commission_scale_repository import BrokerCommissionScaleRepository


class BrokerCommissionScaleService:
    """Business-logic layer for BrokerCommissionScale.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: BrokerCommissionScaleRepository):
        self.repo = repo
