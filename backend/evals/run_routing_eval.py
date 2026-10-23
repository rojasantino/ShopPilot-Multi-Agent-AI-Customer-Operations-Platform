"""Measure routing quality on a fixed test set.  Run:  python -m evals.run_routing_eval"""

import json
from pathlib import Path

from app.agents.intent import classify_with_rules
from app.schemas.intent import Intent

CASES = Path(__file__).with_name("routing_cases.jsonl")


def main() -> None:
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    exact, stats = 0, {i.value: {"tp": 0, "fp": 0, "fn": 0} for i in Intent}
    misses = []
    for case in cases:
        predicted = {i.value for i in classify_with_rules(case["message"]).intents}
        gold = set(case["intents"])
        exact += predicted == gold
        if predicted != gold:
            misses.append((case["message"], sorted(gold), sorted(predicted)))
        for label, s in stats.items():
            s["tp"] += label in predicted and label in gold
            s["fp"] += label in predicted and label not in gold
            s["fn"] += label not in predicted and label in gold

    f1s = []
    for label, s in stats.items():
        p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else 0.0
        r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        f1s.append(f1)
        print(f"{label:16s} precision={p:.2f} recall={r:.2f} f1={f1:.2f}")
    print(
        f"\ncases={len(cases)}  exact-match accuracy={exact / len(cases):.1%}  "
        f"macro-F1={sum(f1s) / len(f1s):.2f}"
    )
    for message, gold, pred in misses:
        print(f"  MISS: {message!r}\n        gold={gold} predicted={pred}")


if __name__ == "__main__":
    main()
