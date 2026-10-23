"""Create extension/tables/index, seed demo data and ingest policy documents (idempotent)."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.db.models import Base, Customer, Order, OrderItem, Product
from app.repositories.knowledge import KnowledgeRepository
from app.services.chunker import chunk_markdown
from app.services.embeddings import Embedder

logger = logging.getLogger(__name__)
POLICY_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"


def init_schema(engine: Engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:
        logger.debug("Extension creation notice: %s", exc)
    Base.metadata.create_all(engine)
    try:
        with engine.begin() as conn:
            # HNSW = fast approximate nearest-neighbour index for cosine distance.
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_embedding_hnsw "
                    "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
    except Exception as exc:
        logger.debug("HNSW index notice: %s", exc)


def seed_demo_data(session: Session, now: datetime | None = None) -> bool:
    if session.scalar(select(func.count()).select_from(Customer)):
        return False
    now = now or datetime.now(UTC)
    day = lambda n: now - timedelta(days=n)  # noqa: E731

    session.add_all(
        [
            Customer(id="CUST-001", name="Aisha Khan", email="aisha@example.com"),
            Customer(id="CUST-002", name="Omar Ali", email="omar@example.com"),
            Customer(id="CUST-003", name="Priya Nair", email="priya@example.com"),
        ]
    )
    products = [
        Product(
            id="P-001",
            name="Wireless Earbuds Pro",
            category="electronics",
            price=Decimal("249"),
            stock=42,
            description="Bluetooth earbuds with charging case and 24h battery",
        ),
        Product(
            id="P-002",
            name="Noise-Cancelling Headphones",
            category="electronics",
            price=Decimal("599"),
            stock=15,
            description="Over-ear wireless headphones with ANC",
        ),
        Product(
            id="P-003",
            name="Smart Watch Series 5",
            category="electronics",
            price=Decimal("899"),
            stock=0,
            description="Fitness tracking smartwatch with GPS",
        ),
        Product(
            id="P-004",
            name="USB-C Fast Charger 65W",
            category="electronics",
            price=Decimal("119"),
            stock=120,
            description="GaN charger for phone and laptop",
        ),
        Product(
            id="P-005",
            name="AeroFit Running Shoes",
            category="apparel",
            price=Decimal("379"),
            stock=30,
            description="Lightweight running shoes for road and treadmill",
        ),
        Product(
            id="P-006",
            name="Cotton T-Shirt",
            category="apparel",
            price=Decimal("59"),
            stock=200,
            description="Soft everyday cotton t-shirt",
        ),
        Product(
            id="P-007",
            name="Yoga Mat",
            category="sports",
            price=Decimal("129"),
            stock=25,
            description="Non-slip 6mm yoga mat",
        ),
        Product(
            id="P-008",
            name="Clearance Backpack",
            category="accessories",
            price=Decimal("79"),
            stock=8,
            is_final_sale=True,
            description="Clearance daypack, final sale",
        ),
    ]
    session.add_all(products)
    session.flush()
    price = {p.id: p.price for p in products}

    def order(oid, cust, status, placed, expected, delivered, items):
        session.add(
            Order(
                id=oid,
                customer_id=cust,
                status=status,
                placed_at=placed,
                expected_delivery=expected,
                delivered_at=delivered,
                items=[
                    OrderItem(product_id=pid, quantity=q, unit_price=price[pid]) for pid, q in items
                ],
            )
        )

    order(
        "ORD-1001", "CUST-001", "delivered", day(12), day(8), day(5), [("P-001", 1), ("P-004", 1)]
    )
    order("ORD-1002", "CUST-001", "shipped", day(3), now + timedelta(days=2), None, [("P-002", 1)])
    order("ORD-1003", "CUST-002", "delivered", day(52), day(47), day(45), [("P-005", 1)])
    order(
        "ORD-1004", "CUST-002", "delivered", day(14), day(11), day(10), [("P-008", 1), ("P-006", 2)]
    )
    order(
        "ORD-1005", "CUST-003", "processing", day(1), now + timedelta(days=4), None, [("P-007", 1)]
    )
    session.commit()
    return True


def ingest_policies(session: Session, embedder: Embedder, force: bool = False) -> int:
    repo = KnowledgeRepository(session)
    if repo.count() and not force:
        return 0
    total = 0
    for path in sorted(POLICY_DIR.glob("*.md")):
        chunks = chunk_markdown(path.read_text(encoding="utf-8"))
        total += repo.replace_source(path.name, chunks, embedder.embed(chunks))
    session.commit()
    logger.info("Ingested %d policy chunks", total)
    return total
