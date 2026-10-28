"""Fine-tune the cross-encoder reranker on our own HR question/section pairs.

Input:  evaluation/data/train_questions.csv with columns  question,policy,section
        (same format as questions.csv, about 150 NEW questions; never copy the 60 test
        questions, or the evaluation becomes meaningless)

How the training pairs are made, for every training question:
  - take the 20 chunks the embedding search returns (exactly what the reranker sees at run time)
  - the chunk from the labelled section = relevant (label 1)
  - the other retrieved chunks = not relevant (label 0), the "hard negatives"

Run from the backend folder, with the venv active and policies uploaded:
    python -m evaluation.train_reranker

Writes:
    models/reranker/                        the fine-tuned model (the backend loads it automatically)
    evaluation/data/reranker_pairs.csv      the generated pairs, for the report
    evaluation/results/reranker_training.txt
Then re-run  python -m evaluation.run_eval  to get the fourth bar.
"""
import argparse
import csv
import random
from pathlib import Path

from app.config import RERANKER_DIR, RERANKER_MODEL, TOP_K_RETRIEVE
from app.retrieval.embeddings import embed_query
from app.retrieval.vector_store import get_collection, query_chunks

HERE = Path(__file__).resolve().parent
NEGATIVES_PER_QUESTION = 7


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [{k: v.strip() for k, v in r.items()} for r in csv.DictReader(f) if r.get("question", "").strip()]


def section_text(policy: str, section: str) -> str | None:
    res = get_collection().get(where={"$and": [{"is_active": True}, {"section": section}]},
                               include=["documents", "metadatas"])
    for text, meta in zip(res["documents"], res["metadatas"]):
        if meta["title"].strip().lower() == policy.lower():
            return text
    return None


def build_pairs(questions: list[dict], rng: random.Random) -> list[dict]:
    pairs, skipped = [], []
    for q in questions:
        candidates = query_chunks(embed_query(q["question"]), TOP_K_RETRIEVE)
        is_match = [c["metadata"]["title"].strip().lower() == q["policy"].lower()
                    and c["metadata"]["section"].strip() == q["section"] for c in candidates]
        positive = next((c["text"] for c, m in zip(candidates, is_match) if m), None) \
            or section_text(q["policy"], q["section"])  # still learn from it if search missed it
        if positive is None:
            skipped.append(q["question"])
            continue
        negatives = [c["text"] for c, m in zip(candidates, is_match) if not m][:NEGATIVES_PER_QUESTION]
        pairs.append({"question": q["question"], "passage": positive, "label": 1})
        pairs += [{"question": q["question"], "passage": n, "label": 0} for n in negatives]
    if skipped:
        print(f"Skipped {len(skipped)} question(s) whose policy/section isn't indexed, e.g. {skipped[0]!r}")
    return pairs


def split_by_question(pairs: list[dict], rng: random.Random, val_share=0.15):
    questions = sorted({p["question"] for p in pairs})
    rng.shuffle(questions)
    val_q = set(questions[: max(1, int(len(questions) * val_share))])
    return [p for p in pairs if p["question"] not in val_q], [p for p in pairs if p["question"] in val_q]


def top1_accuracy(model, pairs: list[dict]) -> float:
    """Share of validation questions where the relevant passage gets the highest score."""
    by_question = {}
    for p in pairs:
        by_question.setdefault(p["question"], []).append(p)
    hits = 0
    for q, group in by_question.items():
        scores = model.predict([(q, p["passage"]) for p in group])
        best = max(range(len(group)), key=lambda i: scores[i])
        hits += group[best]["label"] == 1
    return hits / max(len(by_question), 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(HERE / "data" / "train_questions.csv"))
    parser.add_argument("--base", default=RERANKER_MODEL)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    train_questions = load(Path(args.data))
    test_questions = {r["question"].lower() for r in load(HERE / "questions.csv")}
    leaked = [q["question"] for q in train_questions if q["question"].lower() in test_questions]
    if leaked:
        raise SystemExit(f"{len(leaked)} training question(s) are copied from questions.csv, e.g. {leaked[0]!r}. "
                         "Remove them: the test set must stay unseen.")

    pairs = build_pairs(train_questions, rng)
    (HERE / "data").mkdir(exist_ok=True)
    with (HERE / "data" / "reranker_pairs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "passage", "label"])
        writer.writeheader()
        writer.writerows(pairs)
    train, val = split_by_question(pairs, rng)
    print(f"{len(pairs)} pairs from {len(train_questions)} questions -> train {len(train)}, validation {len(val)}")

    from sentence_transformers import CrossEncoder, InputExample
    from torch.utils.data import DataLoader

    model = CrossEncoder(args.base, num_labels=1)
    before = top1_accuracy(model, val)
    print(f"Validation top-1 accuracy before fine-tuning: {before:.3f}")

    examples = [InputExample(texts=[p["question"], p["passage"]], label=float(p["label"])) for p in train]
    loader = DataLoader(examples, shuffle=True, batch_size=args.batch_size)
    model.fit(train_dataloader=loader, epochs=args.epochs,
              warmup_steps=int(0.1 * len(loader) * args.epochs), show_progress_bar=True)

    after = top1_accuracy(model, val)
    print(f"Validation top-1 accuracy after fine-tuning:  {after:.3f}")
    RERANKER_DIR.mkdir(parents=True, exist_ok=True)
    model.save(str(RERANKER_DIR))

    results = HERE / "results"
    results.mkdir(exist_ok=True)
    (results / "reranker_training.txt").write_text(
        f"Base model: {args.base}\nTraining questions: {len(train_questions)}\n"
        f"Pairs: {len(pairs)} (train {len(train)}, validation {len(val)})\nEpochs: {args.epochs}\n"
        f"Validation top-1 accuracy: before {before:.3f}, after {after:.3f}\n", encoding="utf-8")
    print(f"Saved to {RERANKER_DIR}. Restart the backend, then run: python -m evaluation.run_eval")


if __name__ == "__main__":
    main()
