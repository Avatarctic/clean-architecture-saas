package repositories

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/feature"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/permission"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/tenant"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/domain/user"
	"github.com/avatarctic/clean-architecture-saas/go/internal/core/ports"
	"github.com/google/uuid"
	"golang.org/x/sync/singleflight"
)

// Utility helpers
func cacheSetSilently(c ports.Cache, ctx context.Context, key string, v any, ttl time.Duration) {
	if c == nil {
		return
	}
	b, err := json.Marshal(v)
	if err != nil {
		return
	}
	_ = c.Set(ctx, key, b, ttl)
}

func cacheGet[T any](c ports.Cache, ctx context.Context, key string) (*T, bool) {
	if c == nil {
		return nil, false
	}
	b, ok, err := c.Get(ctx, key)
	if err != nil || !ok {
		return nil, false
	}
	var v T
	if err := json.Unmarshal(b, &v); err != nil {
		return nil, false
	}
	return &v, true
}

// loadFullListWithSingleflight coalesces a full-list load using singleflight, caches the
// full list and optional count, and returns the list. The loader should fetch the
// complete list when called.
func loadFullListWithSingleflight[T any](cache ports.Cache, ctx context.Context, sfKey, listKey, countKey string, ttl time.Duration, loader func() ([]T, error)) ([]T, error) {
	if cache != nil {
		if v, ok := cacheGet[[]T](cache, ctx, listKey); ok {
			return *v, nil
		}
	}
	res, err, _ := sf.Do(sfKey, func() (any, error) {
		if cache != nil {
			if v, ok := cacheGet[[]T](cache, ctx, listKey); ok {
				return *v, nil
			}
		}
		all, err := loader()
		if err != nil {
			return nil, err
		}
		if cache != nil {
			cacheSetSilently(cache, ctx, listKey, all, ttl)
			if countKey != "" {
				cacheSetSilently(cache, ctx, countKey, len(all), ttl)
			}
		}
		return all, nil
	})
	if err != nil {
		return nil, err
	}
	all, ok := res.([]T)
	if !ok {
		return nil, fmt.Errorf("unexpected type from singleflight result")
	}
	return all, nil
}

// CachingTenantRepository decorates a TenantRepository with cache-aside.
type CachingTenantRepository struct {
	inner ports.TenantRepository
	cache ports.Cache
	ttl   time.Duration
}

func NewCachingTenantRepository(inner ports.TenantRepository, cache ports.Cache, ttl time.Duration) ports.TenantRepository {
	return &CachingTenantRepository{inner: inner, cache: cache, ttl: ttl}
}

func (c *CachingTenantRepository) Create(ctx context.Context, t *tenant.Tenant) error {
	if err := c.inner.Create(ctx, t); err != nil {
		return err
	}
	cacheSetSilently(c.cache, ctx, "tenant:id:"+t.ID.String(), t, c.ttl)
	cacheSetSilently(c.cache, ctx, "tenant:slug:"+t.Slug, t, c.ttl)
	if c.cache != nil {
		// Invalidate full-list / count caches
		_ = c.cache.Delete(ctx, "tenants:all")
		_ = c.cache.Delete(ctx, "tenants:count")
	}
	return nil
}

func (c *CachingTenantRepository) GetByID(ctx context.Context, id uuid.UUID) (*tenant.Tenant, error) {
	if v, ok := cacheGet[tenant.Tenant](c.cache, ctx, "tenant:id:"+id.String()); ok {
		return v, nil
	}
	t, err := c.inner.GetByID(ctx, id)
	if err == nil {
		cacheSetSilently(c.cache, ctx, "tenant:id:"+id.String(), t, c.ttl)
		cacheSetSilently(c.cache, ctx, "tenant:slug:"+t.Slug, t, c.ttl)
	}
	return t, err
}

func (c *CachingTenantRepository) GetBySlug(ctx context.Context, slug string) (*tenant.Tenant, error) {
	if v, ok := cacheGet[tenant.Tenant](c.cache, ctx, "tenant:slug:"+slug); ok {
		return v, nil
	}
	t, err := c.inner.GetBySlug(ctx, slug)
	if err == nil {
		cacheSetSilently(c.cache, ctx, "tenant:slug:"+slug, t, c.ttl)
		cacheSetSilently(c.cache, ctx, "tenant:id:"+t.ID.String(), t, c.ttl)
	}
	return t, err
}

func (c *CachingTenantRepository) Update(ctx context.Context, t *tenant.Tenant) error {
	if err := c.inner.Update(ctx, t); err != nil {
		return err
	}
	// Overwrite cache
	cacheSetSilently(c.cache, ctx, "tenant:id:"+t.ID.String(), t, c.ttl)
	cacheSetSilently(c.cache, ctx, "tenant:slug:"+t.Slug, t, c.ttl)
	if c.cache != nil {
		// Invalidate full-list / count caches
		_ = c.cache.Delete(ctx, "tenants:all")
		_ = c.cache.Delete(ctx, "tenants:count")
	}
	return nil
}

func (c *CachingTenantRepository) Delete(ctx context.Context, id uuid.UUID) error {
	// Need slug to delete slug key
	t, _ := c.inner.GetByID(ctx, id)
	if err := c.inner.Delete(ctx, id); err != nil {
		return err
	}
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "tenant:id:"+id.String())
		if t != nil {
			_ = c.cache.Delete(ctx, "tenant:slug:"+t.Slug)
		}
		// Invalidate full-list / count caches
		_ = c.cache.Delete(ctx, "tenants:all")
		_ = c.cache.Delete(ctx, "tenants:count")
	}
	return nil
}

func (c *CachingTenantRepository) List(ctx context.Context, limit, offset int) ([]*tenant.Tenant, error) {
	loader := func() ([]*tenant.Tenant, error) {
		cnt, err := c.inner.Count(ctx)
		if err != nil {
			return nil, err
		}
		return c.inner.List(ctx, cnt, 0)
	}
	all, err := loadFullListWithSingleflight(c.cache, ctx, "tenants:all", "tenants:all", "tenants:count", c.ttl, loader)
	if err != nil {
		return nil, err
	}
	if offset >= len(all) {
		return []*tenant.Tenant{}, nil
	}
	end := offset + limit
	if limit <= 0 || end > len(all) {
		end = len(all)
	}
	return all[offset:end], nil
}

func (c *CachingTenantRepository) Count(ctx context.Context) (int, error) {
	if c.cache != nil {
		if v, ok := cacheGet[int](c.cache, ctx, "tenants:count"); ok {
			return *v, nil
		}
		if v, ok := cacheGet[[]*tenant.Tenant](c.cache, ctx, "tenants:all"); ok {
			return len(*v), nil
		}
	}
	cnt, err := c.inner.Count(ctx)
	if err == nil && c.cache != nil {
		cacheSetSilently(c.cache, ctx, "tenants:count", cnt, c.ttl)
	}
	return cnt, err
}

// CachingUserRepository: cache GetByID & GetByEmail only (short TTL expected).
type CachingUserRepository struct {
	inner ports.UserRepository
	cache ports.Cache
	ttl   time.Duration
}

func NewCachingUserRepository(inner ports.UserRepository, cache ports.Cache, ttl time.Duration) ports.UserRepository {
	return &CachingUserRepository{inner: inner, cache: cache, ttl: ttl}
}

func (c *CachingUserRepository) Create(ctx context.Context, u *user.User) error {
	if err := c.inner.Create(ctx, u); err != nil {
		return err
	}
	// Invalidate per-tenant user list/count caches
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "tenant:users:"+u.TenantID.String()+":all")
		_ = c.cache.Delete(ctx, "tenant:users:"+u.TenantID.String()+":count")
	}
	return nil
}
func (c *CachingUserRepository) GetByID(ctx context.Context, id uuid.UUID) (*user.User, error) {
	if v, ok := cacheGet[user.User](c.cache, ctx, "user:id:"+id.String()); ok {
		return v, nil
	}
	u, err := c.inner.GetByID(ctx, id)
	if err == nil {
		cacheSetSilently(c.cache, ctx, "user:id:"+id.String(), u, c.ttl)
		cacheSetSilently(c.cache, ctx, "user:email:"+u.Email, u, c.ttl)
	}
	return u, err
}
func (c *CachingUserRepository) GetByEmail(ctx context.Context, email string) (*user.User, error) {
	if v, ok := cacheGet[user.User](c.cache, ctx, "user:email:"+email); ok {
		return v, nil
	}
	u, err := c.inner.GetByEmail(ctx, email)
	if err == nil {
		cacheSetSilently(c.cache, ctx, "user:email:"+email, u, c.ttl)
		cacheSetSilently(c.cache, ctx, "user:id:"+u.ID.String(), u, c.ttl)
	}
	return u, err
}
func (c *CachingUserRepository) Update(ctx context.Context, u *user.User) error {
	if err := c.inner.Update(ctx, u); err != nil {
		return err
	}
	cacheSetSilently(c.cache, ctx, "user:id:"+u.ID.String(), u, c.ttl)
	cacheSetSilently(c.cache, ctx, "user:email:"+u.Email, u, c.ttl)
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "tenant:users:"+u.TenantID.String()+":all")
		_ = c.cache.Delete(ctx, "tenant:users:"+u.TenantID.String()+":count")
	}
	return nil
}
func (c *CachingUserRepository) Delete(ctx context.Context, id uuid.UUID) error {
	// Need current to delete email key
	current, _ := c.inner.GetByID(ctx, id)
	if err := c.inner.Delete(ctx, id); err != nil {
		return err
	}
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "user:id:"+id.String())
		if current != nil {
			_ = c.cache.Delete(ctx, "user:email:"+current.Email)
		}
		if current != nil {
			_ = c.cache.Delete(ctx, "tenant:users:"+current.TenantID.String()+":all")
			_ = c.cache.Delete(ctx, "tenant:users:"+current.TenantID.String()+":count")
		}
	}
	return nil
}
func (c *CachingUserRepository) List(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*user.User, error) {
	listKey := "tenant:users:" + tenantID.String() + ":all"
	countKey := "tenant:users:" + tenantID.String() + ":count"
	loader := func() ([]*user.User, error) {
		cnt, err := c.inner.Count(ctx, tenantID)
		if err != nil {
			return nil, err
		}
		return c.inner.List(ctx, tenantID, cnt, 0)
	}
	all, err := loadFullListWithSingleflight(c.cache, ctx, listKey, listKey, countKey, c.ttl, loader)
	if err != nil {
		return nil, err
	}
	if offset >= len(all) {
		return []*user.User{}, nil
	}
	end := offset + limit
	if limit <= 0 || end > len(all) {
		end = len(all)
	}
	return all[offset:end], nil
}
func (c *CachingUserRepository) Count(ctx context.Context, tenantID uuid.UUID) (int, error) {
	key := "tenant:users:" + tenantID.String() + ":count"
	if c.cache != nil {
		if v, ok := cacheGet[int](c.cache, ctx, key); ok {
			return *v, nil
		}
	}
	// Try to read all and cache count when available
	if c.cache != nil {
		if v, ok := cacheGet[[]*user.User](c.cache, ctx, "tenant:users:"+tenantID.String()+":all"); ok {
			return len(*v), nil
		}
	}
	cnt, err := c.inner.Count(ctx, tenantID)
	if err == nil && c.cache != nil {
		cacheSetSilently(c.cache, ctx, key, cnt, c.ttl)
	}
	return cnt, err
}

// CachingFeatureFlagRepository caches by ID and Key.
type CachingFeatureFlagRepository struct {
	inner ports.FeatureFlagRepository
	cache ports.Cache
	ttl   time.Duration
}

func NewCachingFeatureFlagRepository(inner ports.FeatureFlagRepository, cache ports.Cache, ttl time.Duration) ports.FeatureFlagRepository {
	return &CachingFeatureFlagRepository{inner: inner, cache: cache, ttl: ttl}
}
func (c *CachingFeatureFlagRepository) Create(ctx context.Context, f *feature.FeatureFlag) error {
	if err := c.inner.Create(ctx, f); err != nil {
		return err
	}
	cacheSetSilently(c.cache, ctx, "feature:id:"+f.ID.String(), f, c.ttl)
	cacheSetSilently(c.cache, ctx, "feature:key:"+f.Key, f, c.ttl)
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "features:all")
		_ = c.cache.Delete(ctx, "features:count")
	}
	return nil
}
func (c *CachingFeatureFlagRepository) GetByID(ctx context.Context, id uuid.UUID) (*feature.FeatureFlag, error) {
	if v, ok := cacheGet[feature.FeatureFlag](c.cache, ctx, "feature:id:"+id.String()); ok {
		return v, nil
	}
	f, err := c.inner.GetByID(ctx, id)
	if err == nil {
		cacheSetSilently(c.cache, ctx, "feature:id:"+id.String(), f, c.ttl)
		cacheSetSilently(c.cache, ctx, "feature:key:"+f.Key, f, c.ttl)
	}
	return f, err
}
func (c *CachingFeatureFlagRepository) GetByKey(ctx context.Context, key string) (*feature.FeatureFlag, error) {
	if v, ok := cacheGet[feature.FeatureFlag](c.cache, ctx, "feature:key:"+key); ok {
		return v, nil
	}
	f, err := c.inner.GetByKey(ctx, key)
	if err == nil {
		cacheSetSilently(c.cache, ctx, "feature:key:"+key, f, c.ttl)
		cacheSetSilently(c.cache, ctx, "feature:id:"+f.ID.String(), f, c.ttl)
	}
	return f, err
}
func (c *CachingFeatureFlagRepository) Update(ctx context.Context, f *feature.FeatureFlag) error {
	if err := c.inner.Update(ctx, f); err != nil {
		return err
	}
	cacheSetSilently(c.cache, ctx, "feature:id:"+f.ID.String(), f, c.ttl)
	cacheSetSilently(c.cache, ctx, "feature:key:"+f.Key, f, c.ttl)
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "features:all")
		_ = c.cache.Delete(ctx, "features:count")
	}
	return nil
}
func (c *CachingFeatureFlagRepository) Delete(ctx context.Context, id uuid.UUID) error {
	f, _ := c.inner.GetByID(ctx, id)
	if err := c.inner.Delete(ctx, id); err != nil {
		return err
	}
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "feature:id:"+id.String())
		if f != nil {
			_ = c.cache.Delete(ctx, "feature:key:"+f.Key)
		}
		_ = c.cache.Delete(ctx, "features:all")
		_ = c.cache.Delete(ctx, "features:count")
	}
	return nil
}
func (c *CachingFeatureFlagRepository) List(ctx context.Context, limit, offset int) ([]*feature.FeatureFlag, error) {
	loader := func() ([]*feature.FeatureFlag, error) {
		cnt, err := c.inner.Count(ctx)
		if err != nil {
			return nil, err
		}
		return c.inner.List(ctx, cnt, 0)
	}
	all, err := loadFullListWithSingleflight(c.cache, ctx, "features:all", "features:all", "features:count", c.ttl, loader)
	if err != nil {
		return nil, err
	}
	if offset >= len(all) {
		return []*feature.FeatureFlag{}, nil
	}
	end := offset + limit
	if limit <= 0 || end > len(all) {
		end = len(all)
	}
	return all[offset:end], nil
}
func (c *CachingFeatureFlagRepository) Count(ctx context.Context) (int, error) {
	if c.cache != nil {
		if v, ok := cacheGet[int](c.cache, ctx, "features:count"); ok {
			return *v, nil
		}
		if v, ok := cacheGet[[]*feature.FeatureFlag](c.cache, ctx, "features:all"); ok {
			return len(*v), nil
		}
	}
	cnt, err := c.inner.Count(ctx)
	if err == nil && c.cache != nil {
		cacheSetSilently(c.cache, ctx, "features:count", cnt, c.ttl)
	}
	return cnt, err
}

// CachingPermissionRepository caches role permissions list.
type CachingPermissionRepository struct {
	inner ports.PermissionRepository
	cache ports.Cache
	ttl   time.Duration
}

func NewCachingPermissionRepository(inner ports.PermissionRepository, cache ports.Cache, ttl time.Duration) ports.PermissionRepository {
	return &CachingPermissionRepository{inner: inner, cache: cache, ttl: ttl}
}

func (c *CachingPermissionRepository) GetRolePermissions(ctx context.Context, role user.UserRole) ([]permission.Permission, error) {
	key := "perm:role:" + string(role)
	if c.cache != nil {
		if b, ok, err := c.cache.Get(ctx, key); err == nil && ok {
			var perms []permission.Permission
			if json.Unmarshal(b, &perms) == nil {
				return perms, nil
			}
		}
	}
	perms, err := c.inner.GetRolePermissions(ctx, role)
	if err == nil {
		cacheSetSilently(c.cache, ctx, key, perms, c.ttl)
	}
	return perms, err
}
func (c *CachingPermissionRepository) AddPermissionToRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	if err := c.inner.AddPermissionToRole(ctx, role, perm); err != nil {
		return err
	}
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "perm:role:"+string(role))
	}
	return nil
}
func (c *CachingPermissionRepository) RemovePermissionFromRole(ctx context.Context, role user.UserRole, perm permission.Permission) error {
	if err := c.inner.RemovePermissionFromRole(ctx, role, perm); err != nil {
		return err
	}
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "perm:role:"+string(role))
	}
	return nil
}
func (c *CachingPermissionRepository) SetRolePermissions(ctx context.Context, role user.UserRole, permissions []permission.Permission) error {
	if err := c.inner.SetRolePermissions(ctx, role, permissions); err != nil {
		return err
	}
	if c.cache != nil {
		_ = c.cache.Delete(ctx, "perm:role:"+string(role))
	}
	return nil
}

// Simple validation to ensure decorators implement interfaces at compile time
var _ ports.TenantRepository = (*CachingTenantRepository)(nil)
var _ ports.UserRepository = (*CachingUserRepository)(nil)
var _ ports.FeatureFlagRepository = (*CachingFeatureFlagRepository)(nil)
var _ ports.PermissionRepository = (*CachingPermissionRepository)(nil)

// singleflight group for coalescing cache-miss loads in-process
var sf singleflight.Group
