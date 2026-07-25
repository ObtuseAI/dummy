"""Classifying a new caps field must not rewrite immutable historical evidence.

``_SEMANTIC_POLICY_FIELDS`` was doing two jobs with different temporal scope:

* classification -- how a change to this field should be reviewed *now*
* schema requirement -- this field must exist in *any* caps object, including
  immutable historical snapshots written before the field was invented

So adding a field to the taxonomy made it retroactively required, the archived
V11-V19 caps baselines failed shape validation, ``historical_evidence_valid``
went false, and every historical phase report reported ``config_diff_empty:
False`` -- immutable evidence changing because of a present-day config edit.

The two concerns are now separate sets. Requirements stay frozen at what
historical records actually contain; classification may grow.
"""
from __future__ import annotations

from archive.report_scripts.caps_integrity import (
    _REQUIRED_SEMANTIC_POLICY_FIELDS,
    _SEMANTIC_POLICY_FIELDS,
    _classify_change,
    _validate_caps_shape,
)

HISTORICAL_CAPS = {
    "max_single_order_cents": 100,
    "max_market_exposure_cents": 500,
    "max_daily_loss_cents": 500,
    "max_total_live_exposure_cents": 1000,
    "max_open_markets": 3,
    "max_orders_per_hour": 5,
    "max_spread_cents": 5,
    "min_liquidity": 10,
    "min_edge_bps": 50,
    "allow_market_orders": False,
    "limit_orders_only": True,
    "auto_cancel_stale_orders": True,
    "kill_switch_required": True,
    "allowed_markets": [],
    "blocked_categories": ["Elections", "Politics"],
}


class TestHistoricalRecordsSurviveTaxonomyGrowth:
    def test_a_caps_record_predating_a_new_policy_field_is_still_valid(self):
        """The core regression: archived V11-V19 baselines have no
        allowed_series and must not be invalidated by classifying it."""
        assert _validate_caps_shape(dict(HISTORICAL_CAPS)) == []

    def test_every_classified_field_absent_from_history_is_tolerated(self):
        newly_classified = _SEMANTIC_POLICY_FIELDS - _REQUIRED_SEMANTIC_POLICY_FIELDS
        for field in newly_classified:
            assert field not in HISTORICAL_CAPS
        assert _validate_caps_shape(dict(HISTORICAL_CAPS)) == []

    def test_required_set_is_a_subset_of_the_classified_set(self):
        assert _REQUIRED_SEMANTIC_POLICY_FIELDS <= _SEMANTIC_POLICY_FIELDS


class TestRequirementsStillEnforced:
    def test_missing_required_policy_field_still_errors(self):
        caps = dict(HISTORICAL_CAPS)
        del caps["allowed_markets"]
        errors = _validate_caps_shape(caps)
        assert any("allowed_markets" in e for e in errors)

    def test_missing_required_numeric_field_still_errors(self):
        caps = dict(HISTORICAL_CAPS)
        del caps["max_open_markets"]
        assert any("max_open_markets" in e for e in _validate_caps_shape(caps))

    def test_unsafe_boolean_still_errors(self):
        caps = dict(HISTORICAL_CAPS)
        caps["allow_market_orders"] = "no"
        assert any("allow_market_orders" in e for e in _validate_caps_shape(caps))


class TestPresentFieldsAreStillTypeChecked:
    def test_a_present_new_policy_field_with_a_bad_type_errors(self):
        """Tolerating absence must not tolerate garbage when present."""
        for field in sorted(_SEMANTIC_POLICY_FIELDS):
            caps = dict(HISTORICAL_CAPS)
            caps[field] = "KXSOL15M"  # a bare string, not a list
            assert any(field in e for e in _validate_caps_shape(caps)), field

    def test_a_present_new_policy_field_with_empty_strings_errors(self):
        caps = dict(HISTORICAL_CAPS)
        caps["allowed_series"] = ["  "]
        assert any("allowed_series" in e for e in _validate_caps_shape(caps))

    def test_a_well_formed_new_policy_field_is_accepted(self):
        caps = dict(HISTORICAL_CAPS)
        caps["allowed_series"] = ["KXSOL15M"]
        assert _validate_caps_shape(caps) == []


class TestClassificationStillWorks:
    def test_new_policy_field_classifies_as_semantic_policy_review(self):
        verdict = _classify_change("allowed_series", None, ["KXSOL15M"])
        assert verdict == "SEMANTIC_POLICY_CHANGE_REVIEW_REQUIRED"

    def test_existing_policy_field_classification_unchanged(self):
        verdict = _classify_change("blocked_categories", [], ["Politics"])
        assert verdict == "SEMANTIC_POLICY_CHANGE_REVIEW_REQUIRED"

    def test_an_unknown_field_is_still_unclassified(self):
        verdict = _classify_change("some_future_field", None, 1)
        assert verdict == "UNCLASSIFIED_REVIEW_REQUIRED"
