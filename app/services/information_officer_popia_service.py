# Auto-generated service stub for InformationOfficer
# Add business logic here; the router delegates to this layer.

from app.repositories.information_officer_popia_repository import InformationOfficerRepository


class InformationOfficerService:
    """Business-logic layer for InformationOfficer.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: InformationOfficerRepository):
        self.repo = repo
