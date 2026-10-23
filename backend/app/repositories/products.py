import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Product

_STOP = frozenset(
    "a an the do you have any i me my is are in stock price of for looking search find show "
    "buy want need available please what how much does cost can get sell u there some".split()
)


def extract_keywords(message: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", message.lower())
    return [w.rstrip("s") if len(w) > 3 else w for w in words if w not in _STOP]


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def search(self, keywords: list[str], limit: int = 5) -> list[Product]:
        if not keywords:
            return []
        conditions = []
        for kw in keywords:
            like = f"%{kw}%"
            conditions += [
                Product.name.ilike(like),
                Product.category.ilike(like),
                Product.description.ilike(like),
            ]
        candidates = list(self._s.scalars(select(Product).where(or_(*conditions))))

        def score(p: Product) -> int:
            haystack = f"{p.name} {p.category} {p.description}".lower()
            return sum(kw in haystack for kw in keywords)

        return sorted(candidates, key=score, reverse=True)[:limit]
