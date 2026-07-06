# Auto-generated service stub for ComplianceOfficer
# Add business logic here; the router delegates to this layer.

from app.repositories.compliance_officer_repository import ComplianceOfficerRepository


class ComplianceOfficerService:
    """Business-logic layer for ComplianceOfficer.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: ComplianceOfficerRepository):
        self.repo = repo
