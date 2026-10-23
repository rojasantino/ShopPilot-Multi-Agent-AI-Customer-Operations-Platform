from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_for_customer(self, order_id: str, customer_id: str) -> Order | None:
        """Authorization lives here: a customer can only ever load their OWN orders."""
        stmt = select(Order).where(Order.id == order_id.upper(), Order.customer_id == customer_id)
        return self._s.scalars(stmt).first()

    def latest_for_customer(
        self, customer_id: str, *, delivered_only: bool = False
    ) -> Order | None:
        stmt = select(Order).where(Order.customer_id == customer_id)
        if delivered_only:
            stmt = stmt.where(Order.status == "delivered")
        return self._s.scalars(stmt.order_by(Order.placed_at.desc())).first()

    def list_for_customer(self, customer_id: str) -> list[Order]:
        stmt = (
            select(Order).where(Order.customer_id == customer_id).order_by(Order.placed_at.desc())
        )
        return list(self._s.scalars(stmt))
