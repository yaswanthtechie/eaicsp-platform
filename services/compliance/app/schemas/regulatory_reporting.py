from pydantic import BaseModel


class RegulatoryRuleResponse(BaseModel):
    rule_code: str
    rule_name: str
    description: str


class RegulatoryRulesResponse(BaseModel):
    country: str
    applicable_rules: list[RegulatoryRuleResponse]


class RegulatoryRuleResult(BaseModel):
    rule_code: str
    rule_name: str
    status: str


class RegulatoryReportResponse(BaseModel):
    country: str
    overall_status: str
    rules: list[RegulatoryRuleResult]
    passed_count: int
    failed_count: int
    review_count: int
    reason: str | None = None