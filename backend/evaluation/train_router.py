"""Train the query router: TF-IDF + logistic regression baseline vs fine-tuned DistilBERT.

Input:  evaluation/data/router_data.csv with columns  text,label
        label must be one of the six intents below (300-400 rows, roughly balanced).

Run from the backend folder, with the venv active:
    python -m evaluation.train_router
    python -m evaluation.train_router --epochs 6        (optional settings, see --help)

Writes:
    models/router/                          the fine-tuned DistilBERT (the backend loads it automatically)
    evaluation/results/router_report.txt    accuracy, macro F1 and per-class F1 for both models
    evaluation/results/router_loss.png      training and validation loss per epoch
    evaluation/results/router_confusion.png confusion matrix of DistilBERT on the test set
"""
import argparse
import csv
import random
from pathlib import Path

INTENTS = ["policy_qa", "summarize", "compare", "eligibility", "calculation", "out_of_scope"]
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent


def load_data(path: Path):
    with path.open(encoding="utf-8") as f:
        rows = [(r["text"].strip(), r["label"].strip()) for r in csv.DictReader(f) if r["text"].strip()]
    bad = sorted({label for _, label in rows if label not in INTENTS})
    if bad:
        raise SystemExit(f"Unknown labels {bad}. Use only: {', '.join(INTENTS)}")
    texts, labels = zip(*rows)
    return list(texts), [INTENTS.index(label) for label in labels]


def split(texts, labels, seed):
    """70 / 15 / 15, stratified so every intent appears in every split."""
    from sklearn.model_selection import train_test_split
    x_train, x_rest, y_train, y_rest = train_test_split(texts, labels, test_size=0.30, stratify=labels, random_state=seed)
    x_val, x_test, y_val, y_test = train_test_split(x_rest, y_rest, test_size=0.50, stratify=y_rest, random_state=seed)
    return (x_train, y_train), (x_val, y_val), (x_test, y_test)


def report(name, y_true, y_pred):
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    present = sorted(set(y_true) | set(y_pred))
    return (
        f"=== {name} ===\n"
        f"Accuracy: {accuracy_score(y_true, y_pred):.3f}   Macro F1: {f1_score(y_true, y_pred, average='macro'):.3f}\n"
        + classification_report(y_true, y_pred, labels=present,
                                target_names=[INTENTS[i] for i in present], digits=3, zero_division=0)
    )


def train_baseline(train, test):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
                          LogisticRegression(max_iter=2000))
    model.fit(*train)
    return model.predict(test[0]).tolist()


def train_distilbert(train, val, test, args):
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base, num_labels=len(INTENTS),
        id2label=dict(enumerate(INTENTS)), label2id={name: i for i, name in enumerate(INTENTS)},
    ).to(device)

    def batches(texts, labels, shuffle):
        pairs = list(zip(texts, labels))

        def collate(batch):
            enc = tokenizer([t for t, _ in batch], padding=True, truncation=True, max_length=64, return_tensors="pt")
            enc["labels"] = torch.tensor([y for _, y in batch])
            return enc

        return DataLoader(pairs, batch_size=args.batch_size, shuffle=shuffle, collate_fn=collate)

    train_dl, val_dl, test_dl = batches(*train, True), batches(*val, False), batches(*test, False)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = len(train_dl) * args.epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * steps), steps)

    def run_epoch(dl, training):
        model.train(training)
        total, preds = 0.0, []
        for batch in dl:
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.set_grad_enabled(training):
                out = model(**batch)
            if training:
                out.loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
            total += out.loss.item() * len(batch["labels"])
            preds += out.logits.argmax(-1).tolist()
        return total / len(dl.dataset), preds

    history, best_val, out_dir = [], float("inf"), BACKEND / "models" / "router"
    for epoch in range(1, args.epochs + 1):
        train_loss, _ = run_epoch(train_dl, True)
        val_loss, val_pred = run_epoch(val_dl, False)
        val_acc = sum(p == y for p, y in zip(val_pred, val[1])) / len(val[1])
        history.append((epoch, train_loss, val_loss))
        print(f"epoch {epoch}: train loss {train_loss:.4f}  val loss {val_loss:.4f}  val acc {val_acc:.3f}")
        if val_loss < best_val:  # keep the epoch with the lowest validation loss
            best_val = val_loss
            out_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(out_dir)
            tokenizer.save_pretrained(out_dir)

    model = AutoModelForSequenceClassification.from_pretrained(out_dir).to(device)
    _, test_pred = run_epoch(test_dl, False)
    return test_pred, history, out_dir


def save_plots(history, y_true, y_pred, results: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay

    ink, muted, grid = "#27352e", "#7d8981", "#e7ebe6"
    epochs = [h[0] for h in history]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(epochs, [h[1] for h in history], marker="o", linewidth=2, color="#315c49", label="Training loss")
    ax.plot(epochs, [h[2] for h in history], marker="o", linewidth=2, color="#c27c2c", label="Validation loss")
    ax.set_xlabel("Epoch", color=muted)
    ax.set_ylabel("Cross-entropy loss", color=muted)
    ax.set_xticks(epochs)
    ax.set_title("DistilBERT router: loss per epoch", color=ink, loc="left")
    ax.yaxis.grid(True, color=grid)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(results / "router_loss.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    ConfusionMatrixDisplay.from_predictions(
        y_true, y_pred, labels=list(range(len(INTENTS))), display_labels=INTENTS,
        cmap="Greens", colorbar=False, ax=ax, xticks_rotation=35,
    )
    ax.set_title("DistilBERT router: confusion matrix (test set)", color=ink, loc="left")
    fig.tight_layout()
    fig.savefig(results / "router_confusion.png", dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(HERE / "data" / "router_data.csv"))
    parser.add_argument("--base", default="distilbert-base-uncased")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)

    texts, labels = load_data(Path(args.data))
    train, val, test = split(texts, labels, args.seed)
    print(f"{len(texts)} examples -> train {len(train[0])}, validation {len(val[0])}, test {len(test[0])}")

    baseline_pred = train_baseline(train, test)
    bert_pred, history, out_dir = train_distilbert(train, val, test, args)

    results = HERE / "results"
    results.mkdir(parents=True, exist_ok=True)
    text = report("TF-IDF + logistic regression (baseline)", test[1], baseline_pred) + "\n" + \
        report("Fine-tuned DistilBERT", test[1], bert_pred)
    (results / "router_report.txt").write_text(text, encoding="utf-8")
    save_plots(history, test[1], bert_pred, results)
    print("\n" + text)
    print(f"Model saved to {out_dir}. Restart the backend: the trace will show 'Router (DistilBERT)'.")


if __name__ == "__main__":
    main()
