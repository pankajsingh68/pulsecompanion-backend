"""Apply confidence to strategy — conservative adaptation under uncertainty."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from confidence.confidence_models import OrchestrationConfidence
    from orchestration.models import UXStrategy


def apply_confidence_to_strategy(
    strategy: "UXStrategy", conf: "OrchestrationConfidence"
) -> "UXStrategy":
    """If confidence is low, apply conservative adaptation.

    Low confidence:
    - Cap emotional_support_level to 0.5
    - Add reasoning note about conservative adaptation

    Args:
        strategy: The proposed UXStrategy.
        conf: The computed orchestration confidence.

    Returns:
        Modified strategy (or unchanged if confidence is high).
    """
    if conf.is_high_confidence:
        return strategy

    updates: dict = {}
    reasoning = list(strategy.reasoning)

    # Cap emotional support under low confidence
    if strategy.emotional_support_level > 0.5:
        updates["emotional_support_level"] = 0.5

    reasoning.append(
        f"conservative adaptation: low confidence ({conf.composite:.2f})"
    )
    updates["reasoning"] = reasoning

    return strategy.model_copy(update=updates)
