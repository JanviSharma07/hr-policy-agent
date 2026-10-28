"""Retrieval evaluation: Recall@1, Recall@5 and MRR over the labelled questions.

Compares up to four set-ups on the same questions:
  1. Keyword search (TF-IDF)             - the non-neural baseline
  2. Embeddings only (bi-encoder)        - semantic search
  3. Embeddings + pretrained reranker    - cross-encoder from the internet
  4. Embeddings + fine-tuned reranker    - our model (only if backend/models/reranker exists)

Run from the backend folder, with the venv active and policies uploaded:
    python -m evaluation.run_eval

Writes:
    evaluation/results/metrics.csv          one row per set-up (overall + keyword + paraphrase)
    evaluation/results/per_question.csv     rank of the correct section for every question
    evaluation/results/retrieval_chart.png  bar chart for the report
"""
import argparse
import csv
from pathlib import Path

from app.config import RERANKER_DIR, RERANKER_MODEL, TOP_K_RETRIEVE
from app.retrieval.embeddings import embed_query
from app.retrieval.vector_store import get_collection, query_chunks

HERE = Path(__file__).resolve().parent
K = 5  # we score the top 5 results


# ---------- Data ----------

def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["policy"] = row["policy"].strip()
        row["section"] = row["section"].strip()
        row["type"] = row.get("type", "").strip() or "unlabelled"
    return rows


def active_chunks() -> list[dict]:
    res = get_collection().get(where={"is_active": True}, include=["documents", "metadatas"])
    return [{"text": t, "metadata": m} for t, m in zip(res["documents"], res["metadatas"])]


def same_section(meta: dict, policy: str, section: str) -> bool:
    return meta["title"].strip().lower() == policy.lower() and meta["section"].strip() == section


def check_labels(questions: list[dict], chunks: list[dict]) -> None:
    """Stop early if a question points at a policy/section that isn't indexed."""
    available = {(c["metadata"]["title"].strip().lower(), c["metadata"]["section"].strip()) for c in chunks}
    missing = sorted({(q["policy"], q["section"]) for q in questions
                      if (q["policy"].lower(), q["section"]) not in available})
    if missing:
        titles = sorted({c["metadata"]["title"] for c in chunks})
        lines = "\n".join(f"  - {p} / {s}" for p, s in missing)
        raise SystemExit(
            "These labelled sections are not in the current policies:\n"
            f"{lines}\n\nIndexed policy titles: {', '.join(titles)}\n"
            "Fix the policy title in Manage policies or the 'policy' column in the CSV."
        )


# ---------- The set-ups being compared ----------

def keyword_ranker(chunks: list[dict]):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel

    vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    matrix = vectorizer.fit_transform([c["text"] for c in chunks])

    def rank(question: str, _candidates) -> list[dict]:
        scores = linear_kernel(vectorizer.transform([question]), matrix).ravel()
        order = scores.argsort()[::-1][:K]
        return [chunks[i]["metadata"] for i in order]

    return rank


def embedding_ranker(question: str, candidates: list[dict]) -> list[dict]:
    return [c["metadata"] for c in candidates[:K]]


def reranker(model_name_or_path: str):
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(model_name_or_path)

    def rank(question: str, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []
        scores = model.predict([(question, c["text"]) for c in candidates])
        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)[:K]
        return [candidates[i]["metadata"] for i in order]

    return rank


# ---------- Scoring ----------

def rank_of(results: list[dict], policy: str, section: str):
    for position, meta in enumerate(results, start=1):
        if same_section(meta, policy, section):
            return position
    return None  # not in the top K


def summarise(ranks: list) -> dict:
    n = len(ranks) or 1
    return {
        "questions": len(ranks),
        "recall@1": sum(1 for r in ranks if r == 1) / n,
        f"recall@{K}": sum(1 for r in ranks if r) / n,
        "mrr": sum(1 / r for r in ranks if r) / n,
    }


def save_chart(rows: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    overall = [r for r in rows if r["subset"] == "all"]
    names = [r["setup"] for r in overall]
    ink, muted, grid, bar = "#27352e", "#7d8981", "#e7ebe6", "#315c49"

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, metric, title in zip(axes, [f"recall@{K}", "mrr"], [f"Recall@{K}", "MRR"]):
        values = [r[metric] for r in overall]
        ax.bar(range(len(values)), values, width=0.55, color=bar)
        for i, v in enumerate(values):
            ax.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=10, color=ink)
        ax.set_title(title, fontsize=12, color=ink, loc="left")
        ax.set_xticks(range(len(names)), [n.replace(" + ", "\n+ ") for n in names], fontsize=9, color=muted)
        ax.set_ylim(0, 1.08)
        ax.yaxis.grid(True, color=grid, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", colors=muted, labelsize=9)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(grid)
    n = overall[0]["questions"] if overall else 0
    fig.suptitle(f"Retrieval quality on {n} labelled HR questions", fontsize=13, color=ink, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", default=str(HERE / "questions.csv"))
    parser.add_argument("--out", default=str(HERE / "results"))
    args = parser.parse_args()

    questions = load_questions(Path(args.questions))
    chunks = active_chunks()
    if not chunks:
        raise SystemExit("No policies are indexed. Start the backend and upload the policies first.")
    check_labels(questions, chunks)

    setups = [
        ("Keyword (TF-IDF)", keyword_ranker(chunks)),
        ("Embeddings only", embedding_ranker),
        ("Embeddings + pretrained reranker", reranker(RERANKER_MODEL)),
    ]
    if (RERANKER_DIR / "config.json").exists():
        setups.append(("Embeddings + fine-tuned reranker", reranker(str(RERANKER_DIR))))
    else:
        print(f"(No fine-tuned reranker in {RERANKER_DIR} yet, so that bar is skipped.)\n")

    # Embed every question once and reuse its top-20 candidates for every set-up
    candidates = {q["id"]: query_chunks(embed_query(q["question"]), TOP_K_RETRIEVE) for q in questions}

    per_question = []
    for q in questions:
        row = {"id": q["id"], "question": q["question"], "type": q["type"],
               "correct": f'{q["policy"]} / {q["section"]}'}
        for name, rank_fn in setups:
            row[name] = rank_of(rank_fn(q["question"], candidates[q["id"]]), q["policy"], q["section"]) or ""
        per_question.append(row)

    metrics = []
    for name, _ in setups:
        for subset in ["all", "keyword", "paraphrase"]:
            ranks = [int(r[name]) if r[name] != "" else None for r in per_question
                     if subset == "all" or r["type"] == subset]
            if ranks:
                metrics.append({"setup": name, "subset": subset, **summarise(ranks)})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_question.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_question[0]))
        writer.writeheader()
        writer.writerows(per_question)
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows({**m, **{k: round(v, 3) for k, v in m.items() if isinstance(v, float)}} for m in metrics)
    save_chart(metrics, out / "retrieval_chart.png")

    print(f"{'Set-up':36} {'Subset':11} {'R@1':>6} {f'R@{K}':>6} {'MRR':>6}")
    for m in metrics:
        print(f"{m['setup']:36} {m['subset']:11} {m['recall@1']:6.2f} {m[f'recall@{K}']:6.2f} {m['mrr']:6.2f}")
    misses = [r for r in per_question if any(r[name] == "" for name, _ in setups[1:])]
    print(f"\n{len(misses)} question(s) missed by at least one neural set-up (see per_question.csv).")
    print(f"Saved results to {out}")


if __name__ == "__main__":
    main()
