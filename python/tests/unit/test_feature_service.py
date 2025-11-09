"""Unit tests for FeatureFlagService."""

from unittest.mock import AsyncMock

import pytest

from src.app.domain.feature import FeatureFlag as DomainFeatureFlag
from src.app.services.feature_service import FeatureFlagService


@pytest.fixture
def mock_repo():
    """Create mock feature flag repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_audit():
    """Create mock audit repository."""
    audit = AsyncMock()
    audit.log_event = AsyncMock()
    return audit


@pytest.fixture
def mock_cache():
    """Create mock cache client."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def feature_service(mock_repo, mock_audit, mock_cache):
    """Create FeatureFlagService instance with mocks."""
    return FeatureFlagService(mock_repo, mock_audit, mock_cache)


@pytest.mark.asyncio
async def test_create_feature_flag(feature_service, mock_repo, mock_audit, mock_cache):
    """Test creating a feature flag."""
    mock_repo.create = AsyncMock(
        return_value={
            "id": 1,
            "tenant_id": 10,
            "key": "new_feature",
            "name": "New Feature",
            "is_enabled": True,
            "type": "boolean",
        }
    )

    result = await feature_service.create_feature_flag(
        tenant_id=10,
        key="new_feature",
        name="New Feature",
        description="A new feature",
        is_enabled=True,
        type="boolean",
    )

    assert result["id"] == 1
    assert result["key"] == "new_feature"

    # Verify repo was called
    mock_repo.create.assert_called_once()

    # Verify audit log was created
    mock_audit.log_event.assert_called_once()

    # Verify cache was updated
    mock_cache.set.assert_called_once()
    call_args = mock_cache.set.call_args[0]
    assert call_args[0] == "feature:10:new_feature"
    assert call_args[1] == "True"


@pytest.mark.asyncio
async def test_create_feature_flag_without_audit(mock_repo, mock_cache):
    """Test creating feature flag without audit repository."""
    service = FeatureFlagService(mock_repo, audit=None, cache=mock_cache)

    mock_repo.create = AsyncMock(return_value={"id": 2, "key": "test_feature", "is_enabled": False})

    result = await service.create_feature_flag(
        tenant_id=20, key="test_feature", name="Test Feature", description=None, is_enabled=False
    )

    assert result["id"] == 2
    # Should not raise exception even without audit


@pytest.mark.asyncio
async def test_get_feature_by_key_from_cache(feature_service, mock_repo, mock_cache):
    """Test getting feature from cache."""
    cached_data = {"id": 3, "key": "cached_feature", "is_enabled": True, "tenant_id": 30}
    mock_cache.get = AsyncMock(return_value=cached_data)

    result = await feature_service.get_feature_by_key(30, "cached_feature")

    assert result == cached_data
    mock_cache.get.assert_called_once_with("feature:30:cached_feature")
    # Should not call repo if cache hit
    mock_repo.get_by_key.assert_not_called()


@pytest.mark.asyncio
async def test_get_feature_by_key_from_repo(feature_service, mock_repo, mock_cache):
    """Test getting feature from repository on cache miss."""
    mock_cache.get = AsyncMock(return_value=None)  # Cache miss
    mock_repo.get_by_key = AsyncMock(
        return_value={"id": 4, "key": "db_feature", "is_enabled": True, "tenant_id": 40}
    )

    result = await feature_service.get_feature_by_key(40, "db_feature")

    assert result["id"] == 4
    mock_cache.get.assert_called_once()
    mock_repo.get_by_key.assert_called_once_with(40, "db_feature")


@pytest.mark.asyncio
async def test_is_feature_enabled_true(feature_service, mock_repo, mock_cache):
    """Test checking if feature is enabled (returns True)."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 5,
            "key": "enabled_feature",
            "name": "Enabled Feature",
            "is_enabled": True,
            "type": "boolean",
            "enabled_value": {"value": True},
            "default_value": {"value": False},
            "rules": None,
            "rollout": {"percentage": 100},
        }
    )

    result = await feature_service.is_feature_enabled(
        tenant_id=50, key="enabled_feature", user_id=100
    )

    assert result is True


@pytest.mark.asyncio
async def test_is_feature_enabled_false(feature_service, mock_repo, mock_cache):
    """Test checking if feature is disabled (returns False)."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 6,
            "key": "disabled_feature",
            "name": "Disabled Feature",
            "is_enabled": False,
            "type": "boolean",
            "enabled_value": {"value": True},
            "default_value": {"value": False},
            "rules": None,
            "rollout": {"percentage": 100},
        }
    )

    result = await feature_service.is_feature_enabled(
        tenant_id=60, key="disabled_feature", user_id=200
    )

    assert result is False


@pytest.mark.asyncio
async def test_is_feature_enabled_missing_feature(feature_service, mock_repo, mock_cache):
    """Test checking if non-existent feature is enabled (returns False)."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(return_value=None)

    result = await feature_service.is_feature_enabled(
        tenant_id=70, key="missing_feature", user_id=300
    )

    assert result is False


@pytest.mark.asyncio
async def test_is_feature_enabled_with_rollout_percentage(feature_service, mock_repo, mock_cache):
    """Test feature with rollout percentage."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 7,
            "key": "rollout_feature",
            "name": "Rollout Feature",
            "is_enabled": True,
            "type": "boolean",
            "enabled_value": {"value": True},
            "default_value": {"value": False},
            "rules": None,
            "rollout": {"percentage": 50, "strategy": "random"},
        }
    )

    # Test with specific user_id
    result = await feature_service.is_feature_enabled(
        tenant_id=80, key="rollout_feature", user_id=1  # user_id=1 should be deterministic
    )

    # Result depends on hash, but should be boolean
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_get_feature_value(feature_service, mock_repo, mock_cache):
    """Test getting feature value."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 8,
            "key": "string_feature",
            "name": "String Feature",
            "is_enabled": True,
            "type": "string",
            "enabled_value": {"value": "hello"},
            "default_value": {"value": "default"},
            "rules": None,
            "rollout": {"percentage": 100},
        }
    )

    result = await feature_service.get_feature_value(
        tenant_id=90, key="string_feature", user_id=400
    )

    # Feature evaluation returns the enabled_value dict
    assert result == {"value": "hello"}


@pytest.mark.asyncio
async def test_get_feature_value_missing_feature(feature_service, mock_repo, mock_cache):
    """Test getting value of non-existent feature (returns None)."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(return_value=None)

    result = await feature_service.get_feature_value(
        tenant_id=100, key="missing_feature", user_id=500
    )

    assert result is None


@pytest.mark.asyncio
async def test_list_feature_flags(feature_service, mock_repo):
    """Test listing feature flags."""
    mock_repo.list = AsyncMock(
        return_value=[
            {"id": 1, "key": "feature1", "is_enabled": True},
            {"id": 2, "key": "feature2", "is_enabled": False},
        ]
    )

    result = await feature_service.list_feature_flags(tenant_id=110, limit=50, offset=0)

    assert len(result) == 2
    assert result[0]["key"] == "feature1"
    assert result[1]["key"] == "feature2"

    mock_repo.list.assert_called_once_with(110, 50, 0)


@pytest.mark.asyncio
async def test_update_feature_flag(feature_service, mock_repo, mock_audit, mock_cache):
    """Test updating a feature flag."""
    mock_repo.update = AsyncMock(
        return_value={"id": 9, "key": "updated_feature", "is_enabled": False, "tenant_id": 120}
    )

    result = await feature_service.update_feature_flag(id=9, is_enabled=False, name="Updated Name")

    assert result["id"] == 9
    assert result["is_enabled"] is False

    # Verify repo was called
    mock_repo.update.assert_called_once_with(9, is_enabled=False, name="Updated Name")

    # Verify audit log was created
    mock_audit.log_event.assert_called_once()

    # Verify cache was updated
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_delete_feature_flag(feature_service, mock_repo, mock_audit, mock_cache):
    """Test deleting a feature flag."""
    mock_repo.get_by_id = AsyncMock(
        return_value={"id": 10, "key": "deleted_feature", "tenant_id": 130}
    )
    mock_repo.delete = AsyncMock()

    await feature_service.delete_feature_flag(id=10)

    # Verify repo methods were called
    mock_repo.get_by_id.assert_called_once_with(10)
    mock_repo.delete.assert_called_once_with(10)

    # Verify audit log was created
    mock_audit.log_event.assert_called_once()

    # Verify cache was updated (set to "False")
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_is_feature_enabled_with_context(feature_service, mock_repo, mock_cache):
    """Test feature evaluation with full context (role, plan, custom)."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 11,
            "key": "context_feature",
            "name": "Context Feature",
            "is_enabled": True,
            "type": "boolean",
            "enabled_value": {"value": True},
            "default_value": {"value": False},
            "rules": None,
            "rollout": {"percentage": 100},
        }
    )

    result = await feature_service.is_feature_enabled(
        tenant_id=140,
        key="context_feature",
        user_id=600,
        role="admin",
        plan="premium",
        custom={"beta_tester": True},
    )

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_feature_service_without_cache(mock_repo, mock_audit):
    """Test feature service works without cache."""
    service = FeatureFlagService(mock_repo, mock_audit, cache=None)

    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 12,
            "key": "no_cache_feature",
            "is_enabled": True,
            "type": "boolean",
            "enabled_value": {"value": True},
            "default_value": {"value": False},
            "rules": None,
            "rollout": {"percentage": 100},
        }
    )

    result = await service.is_feature_enabled(tenant_id=150, key="no_cache_feature")

    assert result is True


@pytest.mark.asyncio
async def test_build_domain_flag(feature_service):
    """Test converting repository dict to domain FeatureFlag."""
    ff_dict = {
        "id": 13,
        "name": "Test Flag",
        "key": "test_flag",
        "description": "Test description",
        "type": "boolean",
        "is_enabled": True,
        "enabled_value": {"value": True},
        "default_value": {"value": False},
        "rules": [{"condition": "role == 'admin'"}],
        "rollout": {"percentage": 75},
    }

    domain_flag = feature_service._build_domain_flag(ff_dict)

    assert isinstance(domain_flag, DomainFeatureFlag)
    assert domain_flag.id == 13
    assert domain_flag.key == "test_flag"
    assert domain_flag.is_enabled is True
    # Rollout is converted to FeatureFlagRollout object
    assert domain_flag.rollout.percentage == 75


@pytest.mark.asyncio
async def test_is_feature_enabled_with_rules(feature_service, mock_repo, mock_cache):
    """Test feature evaluation with rules."""
    mock_cache.get = AsyncMock(return_value=None)
    mock_repo.get_by_key = AsyncMock(
        return_value={
            "id": 14,
            "key": "rule_feature",
            "name": "Rule Feature",
            "is_enabled": True,
            "type": "boolean",
            "enabled_value": {"value": True},
            "default_value": {"value": False},
            "rules": [{"condition": "role == 'admin'", "value": True}],
            "rollout": {"percentage": 100},
        }
    )

    # Test with admin role
    result = await feature_service.is_feature_enabled(
        tenant_id=160, key="rule_feature", user_id=700, role="admin"
    )

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_create_feature_flag_with_actor(feature_service, mock_repo, mock_audit, mock_cache):
    """Test creating feature flag with actor_user and current_tenant for audit."""
    mock_repo.create = AsyncMock(
        return_value={"id": 15, "key": "actor_feature", "is_enabled": True}
    )

    actor_user = {"id": 800, "email": "admin@example.com"}
    current_tenant = {"id": 170, "name": "Test Tenant"}

    await feature_service.create_feature_flag(
        tenant_id=170,
        key="actor_feature",
        name="Actor Feature",
        description="Feature with actor",
        is_enabled=True,
        actor_user=actor_user,
        current_tenant=current_tenant,
    )

    # Verify audit was called with actor info
    mock_audit.log_event.assert_called_once()
    call_args = mock_audit.log_event.call_args[0]
    assert call_args[0] == actor_user  # current_user
    assert call_args[1] == current_tenant  # current_tenant
