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
            "conditions": [{"attribute": "country", "operator": "equals", "value": "US"}],
            "value": {"flag": "rule"},
            "rollout": 100,
        }
    ]
    ff = FeatureFlag(
        key="k",
        is_enabled=True,
        default_value={"a": 0},
        enabled_value={"a": 1},
        rules=rules,
    )
    ctx = FeatureFlagContext(
        user_id=123, tenant_id=None, role=None, plan=None, custom={"country": "US"}
    )
    val, enabled = ff.evaluate(ctx)
    assert enabled is True
    assert val == {"flag": "rule"}


def test_rollout_inclusion_int_userid():
    ff = FeatureFlag(
        key="k",
        is_enabled=True,
        default_value=False,
        enabled_value=True,
        rollout={"percentage": 100},
    )
    # any int should be included when percentage==100
    ctx = FeatureFlagContext(user_id=42, tenant_id=None, role=None, plan=None, custom={})
    val, enabled = ff.evaluate(ctx)
    assert enabled is True
    assert val is True
