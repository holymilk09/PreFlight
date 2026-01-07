"""Correction rules service.

Deterministic rule selection based on template and reliability.
"""

from src.models import CorrectionRule, Template


# Standard correction rules available in the system
STANDARD_RULES = {
    "sum_line_items": CorrectionRule(
        field="total",
        rule="sum_line_items",
        parameters={"tolerance": 0.01},
    ),
    "iso8601_normalize": CorrectionRule(
        field="date",
        rule="iso8601_normalize",
        parameters={"output_format": "YYYY-MM-DD"},
    ),
    "currency_standardize": CorrectionRule(
        field="amount",
        rule="currency_standardize",
        parameters={"decimal_places": 2},
    ),
    "address_normalize": CorrectionRule(
        field="address",
        rule="address_normalize",
        parameters={"format": "usps"},
    ),
    "name_case_normalize": CorrectionRule(
        field="name",
        rule="name_case_normalize",
        parameters={"style": "title"},
    ),
    "cross_field_validation": CorrectionRule(
        field="*",
        rule="cross_field_validation",
        parameters={"strict": False},
    ),
    "confidence_threshold": CorrectionRule(
        field="*",
        rule="confidence_threshold",
        parameters={"min_confidence": 0.80},
    ),
}


async def select_correction_rules(
    template: Template,
    reliability_score: float,
) -> list[CorrectionRule]:
    """Select correction rules based on template and reliability.

    MVP algorithm:
    1. Start with template-defined correction rules
    2. Add reliability-based rules when score < 0.95
    3. Add stricter validation for low reliability

    Args:
        template: The matched template with defined rules.
        reliability_score: Current reliability score (0-1).

    Returns:
        Ordered list of correction rules to apply.
    """
    rules: list[CorrectionRule] = []

    # 1. Add template-defined rules first
    for rule_dict in template.correction_rules:
        rules.append(CorrectionRule.model_validate(rule_dict))

    # 2. Add reliability-based rules
    if reliability_score < 0.95:
        # Add cross-field validation
        cross_field = CorrectionRule(
            field="*",
            rule="cross_field_validation",
            parameters={"strict": reliability_score < 0.80},
        )
        if not _has_rule(rules, "cross_field_validation"):
            rules.append(cross_field)

    if reliability_score < 0.80:
        # Add confidence threshold rule for low reliability
        confidence = CorrectionRule(
            field="*",
            rule="confidence_threshold",
            parameters={"min_confidence": 0.85},
        )
        if not _has_rule(rules, "confidence_threshold"):
            rules.append(confidence)

        # Add enhanced validation
        enhanced = CorrectionRule(
            field="*",
            rule="enhanced_validation",
            parameters={"level": "strict"},
        )
        rules.append(enhanced)

    if reliability_score < 0.60:
        # Flag for manual review
        review = CorrectionRule(
            field="*",
            rule="flag_for_review",
            parameters={"reason": "low_reliability", "threshold": reliability_score},
        )
        rules.append(review)

    return rules


def _has_rule(rules: list[CorrectionRule], rule_name: str) -> bool:
    """Check if a rule type is already in the list."""
    return any(r.rule == rule_name for r in rules)


def get_available_rules() -> dict[str, CorrectionRule]:
    """Get all available standard correction rules.

    Returns a dictionary of rule name to rule definition.
    """
    return STANDARD_RULES.copy()


def validate_correction_rules(rules: list[CorrectionRule]) -> list[str]:
    """Validate a list of correction rules.

    Returns list of validation errors (empty if valid).
    """
    errors = []

    for i, rule in enumerate(rules):
        # Validate field name
        if not rule.field:
            errors.append(f"Rule {i}: field is required")

        # Validate rule name
        if not rule.rule:
            errors.append(f"Rule {i}: rule name is required")

        # Validate rule exists (for standard rules)
        # Custom rules are allowed but not validated
        if rule.rule in STANDARD_RULES:
            standard = STANDARD_RULES[rule.rule]
            # Check field compatibility
            if standard.field != "*" and rule.field != "*" and rule.field != standard.field:
                errors.append(
                    f"Rule {i}: {rule.rule} is designed for field '{standard.field}', "
                    f"not '{rule.field}'"
                )

    return errors
