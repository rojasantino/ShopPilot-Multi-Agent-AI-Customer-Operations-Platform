from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApprovalRequest, SupportTicket


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create_refund_request(
        self, *, order_id: str, customer_id: str, reason: str, amount: Decimal, details: dict
    ) -> tuple[ApprovalRequest, bool]:
        """Idempotent: re-sending the same request returns the existing PENDING one."""
        existing = self._s.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.order_id == order_id,
                ApprovalRequest.kind == "refund",
                ApprovalRequest.status == "pending",
            )
        ).first()
        if existing:
            return existing, False
        row = ApprovalRequest(
            kind="refund",
            order_id=order_id,
            customer_id=customer_id,
            reason=reason,
            amount=amount,
            details=details,
        )
        self._s.add(row)
        self._s.flush()
        return row, True

    def get(self, approval_id: int) -> ApprovalRequest | None:
        return self._s.get(ApprovalRequest, approval_id)

    def list(self, status: str | None = None) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        return list(self._s.scalars(stmt))

    def decide(
        self, row: ApprovalRequest, *, decision: str, decided_by: str, note: str | None
    ) -> ApprovalRequest:
        row.status = decision
        row.decided_by = decided_by
        row.decision_note = note
        row.decided_at = datetime.now(UTC)
        self._s.flush()
        return row

    def create_ticket(self, *, customer_id: str, order_id: str | None, issue: str) -> SupportTicket:
        ticket = SupportTicket(customer_id=customer_id, order_id=order_id, issue=issue)
        self._s.add(ticket)
        self._s.flush()
        return ticket
