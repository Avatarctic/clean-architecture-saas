from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base: Any = declarative_base()


class TenantModel(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=True, unique=True)
    domain = Column(String, nullable=True)
    plan = Column(String, nullable=False, default="free")
    status = Column(String, nullable=False, default="active")
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_tenants_slug", "slug"),)


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uix_tenant_email"),)
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="member")
    email_verified = Column(Boolean, nullable=False, default=False)
    audit_enabled = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("TenantModel")


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("UserModel")


# Roles & permissions
metadata = Base.metadata

role_permissions = Table(
    "role_permissions",
    metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


class RoleModel(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)


class PermissionModel(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)


class AuditModel(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    action = Column(String, nullable=False)
    resource = Column(String, nullable=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True, default=dict)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserModel")
    tenant = relationship("TenantModel")


# Feature flags
class FeatureFlagModel(Base):
    __tablename__ = "feature_flags"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id"), nullable=True
    )  # nullable => global flag when null
    key = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    type = Column(String, nullable=False, default="boolean")
    is_enabled = Column(Boolean, default=False)
    enabled_value = Column(JSON, nullable=True)
    default_value = Column(JSON, nullable=True)
    rules = Column(JSON, nullable=False, default=list)
    rollout = Column(JSON, nullable=False, default=lambda: {"percentage": 0, "strategy": "random"})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("TenantModel")

    __table_args__ = (UniqueConstraint("key", name="uix_feature_key"),)


# Blacklisted tokens table (persisted blacklist for immediate invalidation)
class BlacklistedTokenModel(Base):
    __tablename__ = "blacklisted_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    token = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
