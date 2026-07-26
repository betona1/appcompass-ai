"""정책 불변식 (CLAUDE.md §12: 점수 가중치 합계 검증)."""

from __future__ import annotations

import pytest

from appcompass.core.enums import DimensionCode, EvidenceType
from appcompass.core.policy import DEFAULT_WEIGHTS, EvaluationPolicy, PolicyError


def test_default_weights_sum_to_100():
    assert sum(DEFAULT_WEIGHTS.values()) == 100


def test_policy_rejects_weight_sum_other_than_100():
    bad = dict(DEFAULT_WEIGHTS)
    bad[DimensionCode.D01] = 20  # 15 -> 20, 합계 105
    with pytest.raises(PolicyError, match="가중치 합계"):
        EvaluationPolicy(weights=bad)


def test_policy_rejects_missing_dimension():
    bad = dict(DEFAULT_WEIGHTS)
    del bad[DimensionCode.D10]
    with pytest.raises(PolicyError, match="가중치가 정의되지 않은"):
        EvaluationPolicy(weights=bad)


def test_policy_rejects_out_of_range_evidence_confidence():
    with pytest.raises(PolicyError, match="근거 신뢰도"):
        EvaluationPolicy(
            evidence_confidence={**EvaluationPolicy().evidence_confidence,
                                 EvidenceType.DESK_RESEARCH: 1.5}
        )


def test_policy_roundtrip():
    original = EvaluationPolicy(version="policy-test", hold_threshold=0.42)
    restored = EvaluationPolicy.from_dict(original.to_dict())
    assert restored.version == "policy-test"
    assert restored.hold_threshold == 0.42
    assert restored.weights == original.weights
    assert restored.evidence_confidence == original.evidence_confidence


def test_evidence_confidence_defaults_match_claude_md():
    p = EvaluationPolicy()
    assert p.confidence_of(EvidenceType.FOUNDER_ASSUMPTION) == 0.20
    assert p.confidence_of(EvidenceType.DESK_RESEARCH) == 0.35
    assert p.confidence_of(EvidenceType.USER_INTERVIEW) == 0.50
    assert p.confidence_of(EvidenceType.PROTOTYPE_TEST) == 0.70
    assert p.confidence_of(EvidenceType.BEHAVIOR_DATA) == 1.00
