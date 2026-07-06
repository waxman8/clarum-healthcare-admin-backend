# Auto-generated service stub for EmployerGroup
# Add business logic here; the router delegates to this layer.

from app.repositories.employer_group_repository import EmployerGroupRepository


class EmployerGroupService:
    """Business-logic layer for EmployerGroup.

    Thin wrapper around the repository. Add validations, cross-entity
    checks, and side-effects (audit log, notifications) here.
    """

    def __init__(self, repo: EmployerGroupRepository):
        self.repo = repo
