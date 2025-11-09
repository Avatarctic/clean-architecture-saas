from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FeatureFlagCreateRequest(BaseModel):
    """Request model for creating a new feature flag."""

    tenant_id: Optional[int] = None
    key: str
    name: str
    description: Optional[str] = None
    is_enabled: bool = False
    type: str = "boolean"
    enabled_value: Optional[Dict[str, Any]] = None
    default_value: Optional[Dict[str, Any]] = None
    rules: Optional[List[Dict[str, Any]]] = None
    rollout: Optional[Dict[str, Any]] = None


class FeatureFlagUpdateRequest(BaseModel):
    """Request model for updating a feature flag."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    enabled_value: Optional[Dict[str, Any]] = None
    default_value: Optional[Dict[str, Any]] = None
    rules: Optional[List[Dict[str, Any]]] = None
    rollout: Optional[Dict[str, Any]] = None


class FeatureFlagEvaluateRequest(BaseModel):
    """Request model for evaluating a feature flag."""

    key: str
    tenant_id: Optional[int] = None
    return_value: Optional[bool] = False
    custom: Optional[Dict[str, Any]] = None


class FeatureFlagResponse(BaseModel):
    """Response model for a feature flag."""

    id: int
    tenant_id: Optional[int] = None
    key: str
    name: str
    description: Optional[str] = None
    is_enabled: bool
    type: str
    enabled_value: Optional[Dict[str, Any]] = None
    default_value: Optional[Dict[str, Any]] = None
    rules: Optional[List[Dict[str, Any]]] = None
    rollout: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FeatureFlagEvaluationResponse(BaseModel):
    """Response model for feature flag evaluation."""

    key: str
    is_enabled: Optional[bool] = None
    value: Optional[Any] = None


class FeatureFlagListResponse(BaseModel):
    """Response model for listing feature flags."""

    flags: List[FeatureFlagResponse]
    total: Optional[int] = None


class FeatureFlagActionResponse(BaseModel):
    """Generic response for feature flag actions."""

    status: str
