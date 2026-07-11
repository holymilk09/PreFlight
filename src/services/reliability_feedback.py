"""Reliability self-calibration from reported outcomes.

``Template.baseline_reliability`` (40% of the reliability score) was frozen at
whatever the tenant typed at registration — the feedback loop existed but was
never wired into scoring. When feedback arrives for an evaluation that matched
a template, the template's baseline now takes one small EWMA step toward the
observed truth, so reliability scores converge on each template's real-world
accuracy as feedback accumulates.

Contract mirrors src/services/baseline.py: mutate in memory, caller commits —
the baseline move lands in the same transaction as the feedback row.

Anti-ratchet rule (enforced by the caller): the step is applied on FIRST
submission, and on resubmission only when the outcome actually changed.
Otherwise a client replaying "rejected" N times would drag a healthy 0.85
baseline to 0.85 * (1-rate)^N — an unbounded penalty from one document.
"""

import structlog

from src.config import settings
from src.models import FeedbackOutcome, Template

logger = structlog.get_logger()

# What each outcome says the "true" reliability of this template's
# extractions was for that document.
OUTCOME_TARGET = {
    FeedbackOutcome.CORRECT: 1.0,
    FeedbackOutcome.CORRECTED: 0.5,
    FeedbackOutcome.REJECTED: 0.0,
}


def apply_reliability_feedback(template: Template, outcome: FeedbackOutcome) -> bool:
    """EWMA ``baseline_reliability`` toward the outcome target.

    Returns True when the baseline moved. The caller owns persistence and the
    anti-ratchet decision (first submission, or outcome changed).
    """
    rate = settings.reliability_learning_rate
    if rate <= 0.0:
        return False

    target = OUTCOME_TARGET[outcome]
    old = template.baseline_reliability
    template.baseline_reliability = round(max(0.0, min(1.0, (1.0 - rate) * old + rate * target)), 4)
    return True
