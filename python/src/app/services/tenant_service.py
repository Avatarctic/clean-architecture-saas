"""Service layer for tenant management operations."""

from typing import Optional

from ..domain.tenant import Tenant
from ..logging_config import get_logger
from ..ports.repositories import TenantRepository

logger = get_logger(__name__)


class TenantService:
    """Encapsulates tenant business logic."""

    def __init__(self, tenant_repo: TenantRepository):
        self.tenant_repo = tenant_repo

    async def suspend_tenant(self, tenant_id: int) -> Tenant:
        """
        Suspend a tenant if transition is valid.

        Raises:
            ValueError: If tenant not found or transition invalid
        """
        logger.info("suspending_tenant", extra={"tenant_id": tenant_id})
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            logger.warning("suspend_tenant_not_found", extra={"tenant_id": tenant_id})
            raise ValueError("Tenant not found")

        if not tenant.can_transition_to("suspended"):
            logger.warning(
                "suspend_tenant_invalid_transition",
                extra={"tenant_id": tenant_id, "current_status": tenant.status},
            )
            raise ValueError(f"Cannot suspend tenant in {tenant.status} status")

        updated: Optional[Tenant] = await self.tenant_repo.update(tenant_id, status="suspended")
        if not updated:
            logger.error("suspend_tenant_update_failed", extra={"tenant_id": tenant_id})
            raise ValueError("Failed to update tenant status")

        logger.info("tenant_suspended", extra={"tenant_id": tenant_id})
        assert updated is not None  # type narrowing after None check
        return updated

    async def activate_tenant(self, tenant_id: int) -> Tenant:
        """
        Activate a tenant if transition is valid.

        Raises:
            ValueError: If tenant not found or transition invalid
        """
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        logger.info(
            "activating_tenant", extra={"tenant_id": tenant_id, "current_status": tenant.status}
        )
        if not tenant.can_transition_to("active"):
            logger.warning(
                "activate_tenant_invalid_transition",
                extra={"tenant_id": tenant_id, "current_status": tenant.status},
            )
            raise ValueError(f"Cannot activate tenant in {tenant.status} status")

        updated: Optional[Tenant] = await self.tenant_repo.update(tenant_id, status="active")
        if not updated:
            logger.error("activate_tenant_update_failed", extra={"tenant_id": tenant_id})
            raise ValueError("Failed to update tenant status")

        logger.info("tenant_activated", extra={"tenant_id": tenant_id, "new_status": "active"})
        assert updated is not None  # type narrowing after None check
        return updated

    async def cancel_tenant(self, tenant_id: int) -> Tenant:
        """
        Cancel a tenant if transition is valid.

        Raises:
            ValueError: If tenant not found or transition invalid
        """
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        logger.info(
            "cancelling_tenant", extra={"tenant_id": tenant_id, "current_status": tenant.status}
        )
        if not tenant.can_transition_to("canceled"):
            logger.warning(
                "cancel_tenant_invalid_transition",
                extra={"tenant_id": tenant_id, "current_status": tenant.status},
            )
            raise ValueError(f"Cannot cancel tenant in {tenant.status} status")

        updated: Optional[Tenant] = await self.tenant_repo.update(tenant_id, status="canceled")
        if not updated:
            logger.error("cancel_tenant_update_failed", extra={"tenant_id": tenant_id})
            raise ValueError("Failed to update tenant status")

        logger.info("tenant_cancelled", extra={"tenant_id": tenant_id, "new_status": "canceled"})
        assert updated is not None  # type narrowing after None check
        return updated
