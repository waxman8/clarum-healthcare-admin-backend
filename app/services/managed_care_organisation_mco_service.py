# Auto-generated service stub for ManagedCareOrganisation
# Add business logic here; the router delegates to this layer.

from app.repositories.managed_care_organisation_mco_repository import ManagedCareOrganisationRepository


class ManagedCareOrganisationService:
    """Business-logic layer for ManagedCareOrganisation.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: ManagedCareOrganisationRepository):
        self.repo = repo
