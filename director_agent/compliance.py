"""Compliance risk scanning."""

from __future__ import annotations

from typing import Iterable, List, Optional

from .config import load_compliance_rules
from .models import RiskTerm


def check_compliance(text: str, rules: Optional[Iterable[dict]] = None) -> List[RiskTerm]:
    rule_items = list(rules) if rules is not None else load_compliance_rules().get("risk_terms", [])
    risks: List[RiskTerm] = []
    for item in rule_items:
        term = str(item["term"])
        count = text.count(term)
        if count:
            risks.append(
                RiskTerm(
                    term=term,
                    reason=str(item["reason"]),
                    replacement=str(item["replacement"]),
                    count=count,
                )
            )
    return risks
