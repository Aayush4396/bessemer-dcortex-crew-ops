"""
src/tier3/models.py
===================
Pydantic and typed data models for Tier 3 Recovery Optimizer.
Defines schemas for candidate options, excluded candidates, recovery plans, and notification drafts.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class RecoveryOption(BaseModel):
    rank: int = Field(..., description="1-indexed recommendation rank")
    action: str = Field(..., description="Human-readable operational recovery action description")
    crew_id: str | None = Field(None, description="Assigned candidate crew ID, or None for cancellation")
    legal: bool = Field(True, description="Whether this recovery option is fully legal under CAR rules")
    rules_checked: list[str] = Field(default_factory=list, description="List of rule IDs validated")
    cost_inr: int = Field(..., description="Total incremental financial cost in INR")
    delay_hours: float = Field(0.0, description="Delay to first departure caused by this option")
    reasoning: str | None = Field(None, description="Operational justification and trade-off summary")


class ExcludedCandidate(BaseModel):
    crew_id: str = Field(..., description="Excluded candidate crew ID")
    reason: str = Field(..., description="Operational reason or specific CAR rule violation causing exclusion")


class JointPlan(BaseModel):
    total_cost_inr: int = Field(..., description="Combined financial cost for joint recovery in INR")
    assign_dxa: RecoveryOption = Field(..., description="Chosen option for first disrupted rotation")
    assign_dxb: RecoveryOption = Field(..., description="Chosen option for second disrupted rotation")


class RecoveryPlan(BaseModel):
    disruption_type: str = Field(..., description="Disruption event type")
    pairing_id: str | None = Field(None, description="Disrupted pairing identifier")
    role: str | None = Field(None, description="Crew role needing replacement")
    options: list[RecoveryOption] = Field(default_factory=list, description="Ranked valid recovery options")
    excluded_candidates: list[ExcludedCandidate] = Field(default_factory=list, description="Excluded candidates with reasons")
    expected_choice: RecoveryOption | None = Field(None, description="Top-ranked optimal choice")
    optimal_joint_plan: JointPlan | None = Field(None, description="Optimal plan for joint multi-event disruptions")
    notification_draft: dict[str, Any] | None = Field(None, description="Draft crew callout notification")


class CalloutNotification(BaseModel):
    recipient_crew_id: str
    recipient_name: str
    pairing_id: str
    report_utc: str
    report_location: str
    flights_summary: list[dict[str, Any]]
    overnight_hotel: str | None = None
    acknowledgement_deadline_utc: str
    dispatch_contact: str
    message_text: str
