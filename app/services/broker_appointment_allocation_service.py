# Auto-generated service stub for BrokerAppointment
# Add business logic here; the router delegates to this layer.

from app.repositories.broker_appointment_allocation_repository import BrokerAppointmentRepository


class BrokerAppointmentService:
    """Business-logic layer for BrokerAppointment.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: BrokerAppointmentRepository):
        self.repo = repo
