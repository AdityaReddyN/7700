"""M8 figures (EVALUATION_PROTOCOL §7): accuracy, confusion, latency, calibration.

Matplotlib with the Agg backend (no display). Each function writes one PNG and
returns its path. Titles carry the sample size; small-n is stated in the summary.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def accuracy_by_config(metrics_by_config: dict, out_path: Path) -> Path:
    configs = list(metrics_by_config)
    top1 = [metrics_by_config[c]["accuracy"]["top1"] or 0 for c in configs]
    top2 = [metrics_by_config[c]["accuracy"]["top2"] or 0 for c in configs]
    n = metrics_by_config[configs[0]]["accuracy"]["n"] if configs else 0
    x = range(len(configs))
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar([i - 0.2 for i in x], top1, 0.4, label="top-1")
    ax.bar([i + 0.2 for i in x], top2, 0.4, label="top-2")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"config {c}" for c in configs])
    ax.set_ylim(0, 1)
    ax.set_ylabel("accuracy")
    ax.set_title(f"Accuracy by config (n={n} evaluated)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def confusion_matrix(conf: dict, out_path: Path, title: str = "Confusion (config D)") -> Path:
    mat, rows, cols = conf["matrix"], conf["rows"], conf["cols"]
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=8)
    ax.set_xlabel("predicted verdict")
    ax.set_ylabel("true label")
    for i in range(len(rows)):
        for j in range(len(cols)):
            ax.text(j, i, str(mat[i][j]), ha="center", va="center", fontsize=8)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def latency_per_case(cases_by_config: dict, out_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    for config, cases in cases_by_config.items():
        secs = [c.get("total_seconds") or 0 for c in cases]
        ax.plot(range(len(secs)), secs, marker="o", label=f"config {config}")
    ax.set_xlabel("case index")
    ax.set_ylabel("seconds")
    ax.set_title("Latency per case (one CPU laptop)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def calibration(cal: list[dict], out_path: Path, title: str = "Calibration (config D)") -> Path:
    bands = [b["band"] for b in cal]
    acc = [b["accuracy"] or 0 for b in cal]
    ns = [b["n"] for b in cal]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(bands, acc, color="#4C78A8")
    for i, (a, nn) in enumerate(zip(acc, ns, strict=True)):
        ax.text(i, a + 0.02, f"n={nn}", ha="center", fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.set_xlabel("confidence band")
    ax.set_ylabel("accuracy")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
