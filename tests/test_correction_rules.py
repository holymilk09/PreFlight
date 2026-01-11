"""Tests for correction rules service."""

import pytest

from src.models import CorrectionRule
from src.services.correction_rules import (
    STANDARD_RULES,
    _has_rule,
    get_available_rules,
    select_correction_rules,
    validate_correction_rules,
)


class TestSelectCorrectionRules:
    """Tests for correction rule selection."""

    @pytest.mark.asyncio
    async def test_high_reliability_minimal_rules(self, sample_template):
        """High reliability should only include template rules."""
        rules = await select_correction_rules(
            template=sample_template,
            reliability_score=0.98,
        )

        # Should only have template-defined rule
        assert len(rules) == 1
        assert rules[0].rule == "sum_line_items"

    @pytest.mark.asyncio
    async def test_moderate_reliability_adds_cross_field(self, sample_template):
        """Reliability < 0.95 should add cross-field validation."""
        rules = await select_correction_rules(
            template=sample_template,
            reliability_score=0.90,
        )

        rule_names = [r.rule for r in rules]
        assert "sum_line_items" in rule_names  # Template rule
        assert "cross_field_validation" in rule_names  # Added for reliability

    @pytest.mark.asyncio
    async def test_low_reliability_adds_strict_rules(self, sample_template):
        """Reliability < 0.80 should add strict validation rules."""
        rules = await select_correction_rules(
            template=sample_template,
            reliability_score=0.70,
        )

        rule_names = [r.rule for r in rules]
        assert "cross_field_validation" in rule_names
        assert "confidence_threshold" in rule_names
        assert "enhanced_validation" in rule_names

        # Cross-field validation should be strict
        cross_field = next(r for r in rules if r.rule == "cross_field_validation")
        assert cross_field.parameters["strict"] is True

    @pytest.mark.asyncio
    async def test_very_low_reliability_flags_review(self, sample_template):
        """Reliability < 0.60 should flag for manual review."""
        rules = await select_correction_rules(
            template=sample_template,
            reliability_score=0.50,
        )

        rule_names = [r.rule for r in rules]
        assert "flag_for_review" in rule_names

        review_rule = next(r for r in rules if r.rule == "flag_for_review")
        assert review_rule.parameters["reason"] == "low_reliability"

    @pytest.mark.asyncio
    async def test_empty_template_rules(self, sample_template):
        """Template with no rules should still work."""
        sample_template.correction_rules = []

        rules = await select_correction_rules(
            template=sample_template,
            reliability_score=0.70,
        )

        # Should still add reliability-based rules
        assert len(rules) > 0
        rule_names = [r.rule for r in rules]
        assert "cross_field_validation" in rule_names


class TestHasRule:
    """Tests for rule existence check."""

    def test_has_rule_found(self):
        """Should return True when rule exists."""
        rules = [
            CorrectionRule(field="total", rule="sum_line_items", parameters=None),
            CorrectionRule(field="date", rule="iso8601_normalize", parameters=None),
        ]
        assert _has_rule(rules, "sum_line_items") is True

    def test_has_rule_not_found(self):
        """Should return False when rule doesn't exist."""
        rules = [
            CorrectionRule(field="total", rule="sum_line_items", parameters=None),
        ]
        assert _has_rule(rules, "nonexistent_rule") is False

    def test_has_rule_empty_list(self):
        """Should return False for empty list."""
        assert _has_rule([], "any_rule") is False


class TestGetAvailableRules:
    """Tests for available rules listing."""

    def test_returns_standard_rules(self):
        """Should return copy of standard rules."""
        rules = get_available_rules()

        assert len(rules) > 0
        assert "sum_line_items" in rules
        assert "iso8601_normalize" in rules
        assert "currency_standardize" in rules

    def test_returns_copy(self):
        """Should return a copy, not the original."""
        rules = get_available_rules()
        rules["new_rule"] = CorrectionRule(field="test", rule="test", parameters=None)

        # Original should be unchanged
        original = get_available_rules()
        assert "new_rule" not in original


class TestValidateCorrectionRules:
    """Tests for correction rule validation."""

    def test_valid_rules(self):
        """Valid rules should return no errors."""
        rules = [
            CorrectionRule(field="total", rule="sum_line_items", parameters=None),
            CorrectionRule(field="date", rule="iso8601_normalize", parameters=None),
        ]
        errors = validate_correction_rules(rules)
        assert len(errors) == 0

    def test_empty_field(self):
        """Empty field should produce error."""
        rules = [
            CorrectionRule(field="", rule="some_rule", parameters=None),
        ]
        errors = validate_correction_rules(rules)
        assert len(errors) == 1
        assert "field is required" in errors[0]

    def test_empty_rule_name(self):
        """Empty rule name should produce error."""
        rules = [
            CorrectionRule(field="total", rule="", parameters=None),
        ]
        errors = validate_correction_rules(rules)
        assert len(errors) == 1
        assert "rule name is required" in errors[0]

    def test_field_compatibility_warning(self):
        """Using standard rule on wrong field should produce error."""
        rules = [
            # sum_line_items is for "total" field, not "name"
            CorrectionRule(field="name", rule="sum_line_items", parameters=None),
        ]
        errors = validate_correction_rules(rules)
        assert len(errors) == 1
        assert "designed for field" in errors[0]

    def test_wildcard_field_allowed(self):
        """Wildcard field should be allowed for any rule."""
        rules = [
            CorrectionRule(field="*", rule="cross_field_validation", parameters=None),
        ]
        errors = validate_correction_rules(rules)
        assert len(errors) == 0

    def test_custom_rule_allowed(self):
        """Custom (non-standard) rules should be allowed."""
        rules = [
            CorrectionRule(
                field="custom_field",
                rule="my_custom_rule",
                parameters={"custom_param": True},
            ),
        ]
        errors = validate_correction_rules(rules)
        assert len(errors) == 0


class TestStandardRules:
    """Tests for standard rule definitions."""

    def test_standard_rules_have_required_fields(self):
        """All standard rules should have required fields."""
        for name, rule in STANDARD_RULES.items():
            assert rule.field, f"Rule {name} missing field"
            assert rule.rule, f"Rule {name} missing rule name"
            assert rule.rule == name, f"Rule {name} has mismatched name"

    def test_standard_rules_parameters(self):
        """Standard rules should have appropriate parameters."""
        # sum_line_items should have tolerance
        assert STANDARD_RULES["sum_line_items"].parameters["tolerance"] == 0.01

        # iso8601_normalize should have output format
        assert "output_format" in STANDARD_RULES["iso8601_normalize"].parameters

        # currency_standardize should have decimal places
        assert STANDARD_RULES["currency_standardize"].parameters["decimal_places"] == 2
