from director_agent.compliance import check_compliance


def test_compliance_flags_risk_terms_and_replacements():
    risks = check_compliance("这是一款全网最低、100%有效、绝对适合你的产品")
    terms = {risk.term: risk.replacement for risk in risks}

    assert terms["全网最低"] == "价格有竞争力"
    assert terms["100%"] == "尽可能"
    assert terms["绝对"] == "更有把握"

