from typing import List, Optional, Protocol


class FeatureFlagRepository(Protocol):
    """Protocol for feature flag repository operations."""

    async def create(
        self,
        tenant_id: int | None,
        key: str,
        name: str,
        description: str | None,
        is_enabled: bool,
        type: str = "boolean",
        enabled_value: dict | None = None,
        default_value: dict | None = None,
        rules: list | None = None,
        rollout: dict | None = None,
    ) -> dict: ...

    async def get_by_key(self, tenant_id: int | None, key: str) -> Optional[dict]: ...
    async def get_by_id(self, id: int) -> Optional[dict]: ...
    async def update(self, id: int, **fields) -> dict: ...
    async def delete(self, id: int) -> None: ...

    async def list(self, tenant_id: int | None, limit: int, offset: int) -> List[dict]: ...
