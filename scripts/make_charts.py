"""Draw every chart from the aggregate CSVs in results/csv/, never from the database."""

from project_paths import project_file

import csv
import os
import json
from pathlib import Path
import textwrap

from artifact_values import CHART_INPUTS, digest

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = project_file('')
CSV_DIR = os.path.join(ROOT, "results", "csv")
OUT_DIR = os.path.join(ROOT, "results", "charts")

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e5e4e0"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
POS, NEG, MID = "#2a78d6", "#e34948", "#cfcec9"
_INPUT_HASHES = {}
_CHART_RECORDS = {}


def record_input(name):
    path = Path(CSV_DIR) / (name + ".csv")
    _INPUT_HASHES[name] = digest(path)


def load(name):
    record_input(name)
    with open(os.path.join(CSV_DIR, name + ".csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def style(ax, title, subtitle=None, xlabel=None, ylabel=None):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    subtitle_lines = len(subtitle.splitlines()) if subtitle else 0
    if title:
        title_artist = ax.set_title(textwrap.fill(title, width=72), color=INK,
                                    fontsize=12, fontweight="bold", loc="left",
                                    pad=16 + 13 * subtitle_lines)
    if subtitle:
        subtitle_artist = ax.text(0, 1.012, subtitle, transform=ax.transAxes,
                                  color=INK2, fontsize=9.5, va="bottom")
        if title:
            pairs = getattr(ax.figure, "_title_subtitle_pairs", [])
            pairs.append((title_artist, subtitle_artist))
            ax.figure._title_subtitle_pairs = pairs
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=9.5)


def save(fig, name):
    fig.tight_layout()
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for title, subtitle in getattr(fig, "_title_subtitle_pairs", []):
        if title.get_window_extent(renderer).overlaps(subtitle.get_window_extent(renderer)):
            raise ValueError(f"Title overlaps subtitle in {name}")
    expected = set(CHART_INPUTS[name])
    if set(_INPUT_HASHES) != expected:
        raise ValueError(f"Unexpected chart inputs for {name}: {_INPUT_HASHES}")
    if any(digest(Path(CSV_DIR) / (key + '.csv')) != value for key, value in _INPUT_HASHES.items()):
        raise ValueError(f"Chart input changed while rendering {name}")
    output = Path(OUT_DIR) / (name + ".png")
    fig.savefig(output, dpi=150,
                facecolor=SURFACE, bbox_inches="tight")
    _CHART_RECORDS[name] = {
        "inputs": dict(_INPUT_HASHES), "png_sha256": digest(output),
        "title_subtitle_overlap": False,
    }
    _INPUT_HASHES.clear()
    plt.close(fig)
    print("wrote", name + ".png")


def bar_labels(ax, bars, fmt="{:.0f}", dy=0.01, fontsize=9):
    top = max(b.get_height() for b in bars)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + top * dy,
                fmt.format(b.get_height()), ha="center", va="bottom",
                color=INK2, fontsize=fontsize)


def chart_rating_distribution():
    d = load("p2_rating_distribution")
    x = [r["rating"] for r in d]
    y = [float(r["pct"]) for r in d]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(x, y, color=S1, width=0.62)
    bar_labels(ax, bars, "{:.1f}%")
    style(ax, "Google reviews are overwhelmingly five-star",
          "Share of reviews by star rating, 9.99M-review national sample",
          "star rating", "% of reviews")
    ax.set_ylim(0, max(y) * 1.16)
    save(fig, "01_rating_distribution")


def chart_volume_and_inflation():
    v = load("p2_reviews_per_year")
    m = load("p2_mean_rating_per_year")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.4, 6.4), sharex=True)
    yrs = [int(r["year"]) for r in v]
    a1.plot(yrs, [int(r["n"]) for r in v], color=S1, linewidth=2,
            marker="o", markersize=5)
    style(a1, "Review volume peaked in 2019; ratings kept drifting up",
          "Two measures, two panels - never two y-axes on one plot",
          None, "reviews sampled")
    a1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1e6:.1f}M"))
    a2.plot([int(r["year"]) for r in m], [float(r["mean_rating"]) for r in m],
            color=S2, linewidth=2, marker="o", markersize=5)
    style(a2, None, None, "year", "mean star rating")
    a2.text(0.995, 0.06, "2021 is a part-year: data ends September 2021",
            transform=a2.transAxes, ha="right", color=INK2, fontsize=8.5, style="italic")
    save(fig, "02_volume_and_rating_inflation")


def chart_length_vs_rating():
    d = load("p2_length_vs_rating")
    x = [r["rating"] for r in d]
    y = [float(r["median_length"]) for r in d]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(x, y, color=S1, width=0.62)
    bar_labels(ax, bars, "{:.0f}")
    style(ax, "One-star reviews have the longest median text",
          "Median review length in characters. The relationship is U-shaped, not linear",
          "star rating", "median characters")
    ax.set_ylim(0, max(y) * 1.16)
    save(fig, "03_length_vs_rating")


def chart_response_rate():
    d = load("p2_response_rate_by_rating")
    x = [r["rating"] for r in d]
    y = [float(r["pct_with_response"]) for r in d]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(x, y, color=S1, width=0.62)
    bar_labels(ax, bars, "{:.2f}%")
    style(ax, "Owners reply more often to one-star and five-star reviews",
          "Share of reviews receiving an owner response, by star rating",
          "star rating", "% receiving a reply")
    ax.set_ylim(0, max(y) * 1.18)
    save(fig, "04_owner_response_rate")


def chart_state_rank_shift():
    d = load("p3_state_raw_vs_std")
    for r in d:
        r["shift"] = int(r["raw_rank"]) - int(r["std_rank"])
    movers = sorted(d, key=lambda r: -abs(r["shift"]))[:15]
    movers = sorted(movers, key=lambda r: r["shift"])
    names = [r["state"].replace("_", " ") for r in movers]
    ypos = range(len(movers))
    fig, ax = plt.subplots(figsize=(7.8, 5.6))
    for i, r in enumerate(movers):
        ax.plot([int(r["raw_rank"]), int(r["std_rank"])], [i, i],
                color=GRID, linewidth=2, zorder=1)
    ax.scatter([int(r["raw_rank"]) for r in movers], list(ypos), s=62,
               color=S1, zorder=2, label="raw rank")
    ax.scatter([int(r["std_rank"]) for r in movers], list(ypos), s=62,
               color=S2, zorder=2, label="after category control")
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(names)
    ax.invert_xaxis()
    style(ax, "States reorder substantially once business mix is held constant",
          "15 biggest movers. Holding the category set fixed, reweighting cuts the "
          "spread 41.7%",
          "rank (1 = highest average rating)", None)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    # Legend outside the axes so it doesn't cover the DC and Vermont markers.
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, ncol=2,
              loc="upper center", bbox_to_anchor=(0.5, -0.09))
    save(fig, "05_state_rank_shift")


def chart_reliability():
    d = load("reliability_contrast")
    labels = [r["measure"] for r in d]
    obs = [float(r["split_half_observed"]) for r in d]
    exp = [float(r["noise_only_expected"]) for r in d]
    x = range(len(d))
    w = 0.34
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    b1 = ax.bar([i - w / 2 for i in x], obs, w, color=S1, label="observed split-half")
    b2 = ax.bar([i + w / 2 for i in x], exp, w, color=S3,
                label="ceiling if only sampling noise")
    for bars in (b1, b2):
        bar_labels(ax, bars, "{:.3f}")
    ax.set_xticks(list(x))
    ax.set_xticklabels([l.replace(": ", ":\n") for l in labels], fontsize=9.5)
    style(ax, "Writing-warmth rankings agree across category splits more than "
              "rating rankings do",
          "Split-half reliability over random halves of the category set.\n"
          "Different samples and category sets, so NOT a controlled comparison\n"
          "of the two measures. The noise-only ceiling is approximate.",
          None, "rank correlation")
    ax.set_ylim(0, 1.08)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left",
              bbox_to_anchor=(0, -0.17), ncol=2)
    save(fig, "06_reliability_contrast")


def chart_auc():
    d = load("p4a_auc")
    signals = ["rating level", "trajectory", "final-window rating"]
    years = sorted({int(r["end_year"]) for r in d})
    colors = [S1, S2, S3]
    w = 0.26
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for k, sig in enumerate(signals):
        vals = [float(next(r["auc"] for r in d
                           if r["signal"] == sig and int(r["end_year"]) == y)) for y in years]
        bars = ax.bar([i + (k - 1) * w for i in range(len(years))], vals, w,
                      color=colors[k], label=sig)
        bar_labels(ax, bars, "{:.3f}", dy=0.004, fontsize=8)
    ax.axhline(0.5, color=NEG, linewidth=1.4, linestyle="--")
    ax.text(len(years) - 0.52, 0.505, "0.50 = coin flip", color=NEG, fontsize=8.5, va="bottom")
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years)
    style(ax, "These three signals rank closures only weakly",
          "AUC in a retrospective cohort. AUC measures ranking, not accuracy,\n"
          "and does not settle utility at every threshold or use case.",
          "year of last review", "AUC")
    ax.set_ylim(0.45, 0.63)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, ncol=3, loc="upper center")
    save(fig, "07_closure_auc")


def chart_did_by_year():
    d = load("p4a_did_by_year")
    yrs = [r["end_year"] for r in d]
    did = [float(r["did"]) for r in d]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(yrs, did, color=NEG, width=0.55)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() - 0.006,
                f"{b.get_height():.3f}", ha="center", va="top", color=INK2, fontsize=9)
    ax.axhline(0, color=INK2, linewidth=1)
    ax.set_ylim(min(0, min(did)) - 0.035, max(0, max(did)) + 0.01)
    style(ax, "Closed businesses show larger declines in this retrospective sample",
          "Final 6 months vs own 24-12 month baseline, aligned on last observed review.\n"
          "The 2019 estimate's 95% interval includes zero; see the report for uncertainty.",
          "year of last review", "extra decline (stars)")
    save(fig, "08_closure_did")


def chart_p5_by_star():
    d = load("p5_accuracy_by_star")
    methods = [("vader", "VADER", S1), ("bert", "BERT (pretrained)", S2),
               ("naive_bayes", "Naive Bayes (trained)", S3), ("svm", "SVM (trained)", S4)]
    stars = [r["rating"] for r in d]
    w = 0.2
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for k, (key, label, col) in enumerate(methods):
        vals = [float(r[key]) for r in d]
        bars = ax.bar([i + (k - 1.5) * w for i in range(len(stars))], vals, w,
                      color=col, label=label)
        bar_labels(ax, bars, "{:.0f}", dy=0.008, fontsize=7.5)
    ax.set_xticks(range(len(stars)))
    ax.set_xticklabels([f"{s} star" for s in stars])
    style(ax, "VADER's agreement varies sharply by star rating",
          "Binary predictions compared with review stars; 10,000 reviews per rating",
          None, "% correct")
    ax.set_ylim(0, 112)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, ncol=4, loc="upper center")
    save(fig, "09_sentiment_accuracy_by_star")


def chart_category_gap():
    d = load("p6_category_gap")
    # Length-controlled gap: the same measure the BERT check uses.
    d.sort(key=lambda r: float(r["mean_gap_lenctl"]))
    picks = d[:12] + d[-12:]
    names = [r["category"] for r in picks]
    vals = [float(r["mean_gap_lenctl"]) for r in picks]
    cols = [NEG if v < 0 else POS for v in vals]
    fig, ax = plt.subplots(figsize=(8.4, 7.4))
    ax.barh(range(len(picks)), vals, color=cols, height=0.68)
    ax.set_yticks(range(len(picks)))
    ax.set_yticklabels(names, fontsize=9)
    ax.axvline(0, color=INK2, linewidth=1)
    style(ax, "Category differences in rating/length-adjusted VADER scores",
          "Mean residual from a pooled baseline within star rating and length bucket",
          "mean VADER residual (lower  <-->  higher)", None)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    save(fig, "10_category_gap")


def chart_length_effect():
    d = load("p6_length_vader")
    labels = ["<50", "50-149", "150-399", "400+"]
    vals = [float(r["mean_gap"]) for r in d]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(labels, vals, color=[NEG if v < 0 else POS for v in vals], width=0.6)
    for b in bars:
        off = 0.008 if b.get_height() >= 0 else -0.008
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + off,
                f"{b.get_height():+.3f}", ha="center",
                va="bottom" if b.get_height() >= 0 else "top", color=INK2, fontsize=9)
    ax.axhline(0, color=INK2, linewidth=1)
    ax.margins(y=0.18)
    style(ax, "Longer reviews have higher rating-adjusted VADER scores",
          "Mean gap by review length. This association does not isolate a causal length effect.",
          "review length (characters)", "mean gap")
    save(fig, "11_length_effect")


def chart_bert_check():
    record_input("p6_bert_check")
    rows = []
    with open(os.path.join(CSV_DIR, "p6_bert_check.csv"), encoding="utf-8") as f:
        for r in csv.reader(f):
            if r and r[0] in ("A_grim_minus_reference", "B_cold10_minus_warm10"):
                rows.append(r)
    labels = ["Grim topics\n(funerals, hospitals)", "Coldest vs warmest\ncategories"]
    v = [float(r[1]) for r in rows]
    b = [float(r[2]) for r in rows]
    x = range(len(rows))
    w = 0.34
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    b1 = ax.bar([i - w / 2 for i in x], v, w, color=S1, label="VADER")
    b2 = ax.bar([i + w / 2 for i in x], b, w, color=S3, label="BERT (reads context)")
    for bars in (b1, b2):
        for bb in bars:
            off = 0.02 if bb.get_height() >= 0 else -0.02
            ax.text(bb.get_x() + bb.get_width() / 2, bb.get_height() + off,
                    f"{bb.get_height():+.2f}", ha="center",
                    va="bottom" if bb.get_height() >= 0 else "top",
                    color=INK2, fontsize=9)
    ax.axhline(0, color=INK2, linewidth=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9.5)
    style(ax, "Model-score contrasts for selected five-star review groups",
          "Difference / SD of all four groups; 5 stars, equal length-band counts.\n"
          "The ratio of these scaled contrasts does not estimate\n"
          "a fraction of human sentiment explained.",
          None, "standardized difference")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="lower left")
    save(fig, "12_bert_check")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _INPUT_HASHES.clear()
    _CHART_RECORDS.clear()
    source_hash = digest(__file__)
    for fn in (chart_rating_distribution, chart_volume_and_inflation,
               chart_length_vs_rating, chart_response_rate, chart_state_rank_shift,
               chart_reliability, chart_auc, chart_did_by_year, chart_p5_by_star,
               chart_category_gap, chart_length_effect, chart_bert_check):
        fn()
    if source_hash != digest(__file__):
        raise ValueError("Renderer changed during chart generation")
    manifest = {"schema": 1, "renderer_sha256": source_hash,
                "charts": _CHART_RECORDS}
    path = Path(OUT_DIR) / "manifest.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


if __name__ == "__main__":
    main()
