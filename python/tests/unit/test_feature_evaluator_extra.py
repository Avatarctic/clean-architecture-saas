from src.app.domain.feature import FeatureFlag, FeatureFlagContext


def test_disabled_flag_returns_default():
    ff = FeatureFlag(key="k", is_enabled=False, default_value={"a": 1}, enabled_value={"a": 2})
    ctx = FeatureFlagContext(user_id=None, tenant_id=None, role=None, plan=None, custom={})
    val, enabled = ff.evaluate(ctx)
    assert enabled is False
    assert val == {"a": 1}


def test_rule_match_returns_rule_value():
    rules = [
        {
            "id": "r1",
            "conditions": [{"attribute": "country", "operator": "equals", "value": "CA"}],
            "value": {"color": "red"},
            "rollout": 100,
        }
    ]
    ff = FeatureFlag(
        key="k",
        is_enabled=True,
        default_value={"color": "blue"},
        enabled_value={"color": "green"},
        rules=rules,
    )
    ctx = FeatureFlagContext(
        user_id=123, tenant_id=None, role=None, plan=None, custom={"country": "CA"}
    )
    val, enabled = ff.evaluate(ctx)
    assert enabled is True
    assert val == {"color": "red"}


def test_rule_rollout_respected():
    # rule rollout 0 means users not in rollout won't match
    rules = [
        {
            "id": "r1",
            "conditions": [{"attribute": "country", "operator": "equals", "value": "CA"}],
            "value": {"color": "red"},
            "rollout": 0,
        }
    ]
    ff = FeatureFlag(
        key="k",
        is_enabled=True,
        default_value={"color": "blue"},
        enabled_value={"color": "green"},
        rules=rules,
    )
    # user_id None must result in not in rollout
    ctx = FeatureFlagContext(
        user_id=None, tenant_id=None, role=None, plan=None, custom={"country": "CA"}
    )
    val, enabled = ff.evaluate(ctx)
    assert enabled is False
    assert val == {"color": "blue"}


def test_flag_level_rollout_applies_enabled_value():
    ff = FeatureFlag(
        key="k",
        is_enabled=True,
        default_value={"color": "blue"},
        enabled_value={"color": "green"},
        rollout={"percentage": 100},
    )
    ctx = FeatureFlagContext(user_id=42, tenant_id=None, role=None, plan=None, custom={})
    val, enabled = ff.evaluate(ctx)
    assert enabled is True
    assert val == {"color": "green"}


def test_rollout_hashing_is_deterministic():
    ff = FeatureFlag(
        key="k",
        is_enabled=True,
        default_value=False,
        enabled_value=True,
        rollout={"percentage": 50},
    )
    # deterministic for same user id
    ctx1 = FeatureFlagContext(user_id=9999, tenant_id=None, role=None, plan=None, custom={})
    ctx2 = FeatureFlagContext(user_id=9999, tenant_id=None, role=None, plan=None, custom={})
    v1, _ = ff.evaluate(ctx1)
    v2, _ = ff.evaluate(ctx2)
    assert v1 == v2
