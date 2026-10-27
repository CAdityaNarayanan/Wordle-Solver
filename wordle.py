"""Rank Wordle opening guesses and benchmark four continuation strategies.

Expected files:
    data/answers.txt          one possible answer per line
    data/extra_guesses.txt    legal guesses that are not answer candidates

The benchmark uses the fixed answer list as the answer universe. Entropy and
minimax may choose any word in the combined legal-guess list. The random
baseline chooses randomly from the answers still consistent with feedback.
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import pickle
import random
import statistics
import time
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ADIEU and OUIJA are always included as familiar, vowel-heavy baselines.
# Other finalist openers are selected by measurable criteria below.
BASELINE_OPENERS = ("adieu", "ouija")
TOP_OPENERS_PER_METRIC = 3
MAX_TURNS = 6
STRATEGIES = ("random", "common", "entropy", "minimax")
GREEN_PATTERN = 2 + 2 * (3**1) + 2 * (3**2) + 2 * (3**3) + 2 * (3**4)
MARKS = "BYG"  # base-3 digit 0=grey, 1=yellow, 2=green

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
RESULTS_DIR = PROJECT_DIR / "results"
ANSWERS_FILE = DATA_DIR / "answers.txt"
EXTRA_GUESSES_FILE = DATA_DIR / "extra_guesses.txt"
FREQUENCY_FILE = DATA_DIR / "count_1w.txt"
MATRIX_CACHE_FILE = DATA_DIR / "feedback_matrix.pkl"


def load_words(path: Path) -> list[str]:
    """Load and validate a one-word-per-line, five-letter word file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Put the downloaded word list in the data folder."
        )

    words = [line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()]
    words = [word for word in words if word]

    invalid = [word for word in words if len(word) != 5 or not word.isascii() or not word.isalpha()]
    if invalid:
        raise ValueError(f"{path.name} contains invalid entries, for example {invalid[:3]}")
    if len(words) != len(set(words)):
        raise ValueError(f"{path.name} contains duplicate entries.")
    return sorted(words)


def load_word_frequencies(path: Path) -> dict[str, int]:
    """Read Norvig's `word count` corpus file; keep five-letter words only."""
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Download count_1w.txt from https://norvig.com/ngrams/."
        )

    frequencies: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        word, count_text = fields
        word = word.lower()
        if len(word) == 5 and word.isascii() and word.isalpha():
            try:
                frequencies[word] = int(count_text)
            except ValueError:
                continue
    return frequencies


def feedback_code(guess: str, answer: str) -> int:
    """Return Wordle feedback as a base-3 integer (grey=0, yellow=1, green=2).

    Greens are assigned first. Yellows then use only the unmatched copies of
    answer letters, which correctly handles duplicate letters.
    """
    marks = [0] * 5
    unmatched = Counter(answer)

    for position in range(5):
        if guess[position] == answer[position]:
            marks[position] = 2
            unmatched[guess[position]] -= 1

    for position in range(5):
        letter = guess[position]
        if marks[position] == 0 and unmatched[letter] > 0:
            marks[position] = 1
            unmatched[letter] -= 1

    # Position zero is the least significant base-3 digit.
    return sum(mark * (3**position) for position, mark in enumerate(marks))


def feedback_text(code: int) -> str:
    """Convert a feedback code into a readable string such as GYBYB."""
    marks = []
    for _ in range(5):
        marks.append(MARKS[code % 3])
        code //= 3
    return "".join(marks)


def filter_candidates(
    candidate_ids: tuple[int, ...], guess_row: bytes, observed_code: int
) -> tuple[int, ...]:
    """Keep answer indices that match the feedback from a guess."""
    return tuple(i for i in candidate_ids if guess_row[i] == observed_code)


def build_feedback_matrix(
    answers: list[str], guesses: list[str], cache_file: Path
) -> dict[str, bytes]:
    """Precompute feedback for each legal guess against each answer.

    Caching this table avoids recalculating repeated-letter feedback during
    thousands of simulated games. The table is about 30 MB for the original
    2,315-answer and 12,972-guess lists.
    """
    if cache_file.exists():
        try:
            with cache_file.open("rb") as file:
                saved_answers, saved_guesses, saved_matrix = pickle.load(file)
            if saved_answers == answers and saved_guesses == guesses:
                print(f"Loaded feedback cache: {cache_file}")
                return saved_matrix
        except (OSError, EOFError, pickle.UnpicklingError, ValueError):
            print("The old feedback cache could not be read; rebuilding it.")

    print(f"Building feedback table for {len(guesses):,} guesses x {len(answers):,} answers...")
    started = time.time()
    matrix: dict[str, bytes] = {}
    for row_number, guess in enumerate(guesses, start=1):
        matrix[guess] = bytes(feedback_code(guess, answer) for answer in answers)
        if row_number % 2000 == 0 or row_number == len(guesses):
            print(f"  Built {row_number:,}/{len(guesses):,} guess rows")

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("wb") as file:
        pickle.dump((answers, guesses, matrix), file, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Feedback table ready in {time.time() - started:.1f} seconds.")
    return matrix


def expected_remaining(bucket_counts: list[int], candidate_count: int) -> float:
    """Expected number of possible answers left after a guess."""
    return sum(count * count for count in bucket_counts) / candidate_count


def choose_guess(
    strategy: str,
    candidates: tuple[int, ...],
    answers: list[str],
    legal_guesses: list[str],
    matrix: dict[str, bytes],
    word_frequencies: dict[str, int],
    rng: random.Random,
    used_guesses: frozenset[str],
    decision_cache: dict[tuple[str, tuple[int, ...], tuple[str, ...]], str],
) -> str:
    """Choose the next guess according to one of the four strategies."""
    if not candidates:
        raise RuntimeError("No possible answers remain; check feedback or word lists.")
    if len(candidates) == 1:
        return answers[candidates[0]]

    if strategy == "random":
        # Simple baseline: pick a random answer still consistent with clues.
        return answers[rng.choice(candidates)]
    if strategy == "common":
        # Proxy for choosing a familiar-looking answer, not an information probe.
        best_candidate = min(
            candidates,
            key=lambda answer_id: (
                -word_frequencies.get(answers[answer_id], 0),
                answers[answer_id],
            ),
        )
        return answers[best_candidate]

    used_key = tuple(sorted(used_guesses))
    state = (strategy, candidates, used_key)
    if state in decision_cache:
        return decision_cache[state]

    candidate_set = set(candidates)
    best_guess = None
    best_key = None
    count = len(candidates)

    for guess in legal_guesses:
        if guess in used_guesses:
            continue
        row = matrix[guess]
        buckets = [0] * 243
        for answer_id in candidates:
            buckets[row[answer_id]] += 1
        nonempty = [size for size in buckets if size]
        worst_bucket = max(nonempty)
        mean_remaining = expected_remaining(nonempty, count)

        if strategy == "entropy":
            entropy = -sum(
                (size / count) * math.log2(size / count) for size in nonempty
            )
            # Maximize information; break ties by expected remaining answers.
            key = (entropy, -mean_remaining, guess in candidate_set)
            is_better = best_key is None or key > best_key
        elif strategy == "minimax":
            # Minimize the largest possible feedback group, then its average.
            key = (worst_bucket, mean_remaining, guess not in candidate_set)
            is_better = best_key is None or key < best_key
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # legal_guesses is sorted, so exact ties keep the alphabetically first word.
        if is_better:
            best_key = key
            best_guess = guess

    if best_guess is None:
        raise RuntimeError(f"Could not choose a guess for strategy {strategy}.")

    decision_cache[state] = best_guess
    return best_guess


def stable_answer_seed(answer: str, base_seed: int) -> int:
    """Make a repeatable per-answer random seed without Python's salted hash."""
    word_number = sum((position + 1) * ord(letter) for position, letter in enumerate(answer))
    return base_seed + word_number


def simulate_answer(
    answer_id: int,
    strategy: str,
    opening_word: str,
    answers: list[str],
    legal_guesses: list[str],
    matrix: dict[str, bytes],
    word_frequencies: dict[str, int],
    decision_cache: dict[tuple[str, tuple[int, ...], tuple[str, ...]], str],
    seed: int,
) -> dict[str, object]:
    """Play one game with a fixed opener, then use the chosen strategy."""
    answer = answers[answer_id]
    candidate_ids = tuple(range(len(answers)))
    rng = random.Random(stable_answer_seed(answer, seed))
    guessed_words: list[str] = []
    feedbacks: list[str] = []
    guess = opening_word

    for turn in range(1, MAX_TURNS + 1):
        if guess not in matrix:
            raise ValueError(f"{guess.upper()} is not in the legal guess list.")

        code = matrix[guess][answer_id]
        guessed_words.append(guess)
        feedbacks.append(feedback_text(code))

        if code == GREEN_PATTERN:
            return {
                "answer": answer,
                "strategy": strategy,
                "opening_word": opening_word,
                "solved": True,
                "guesses_used": turn,
                "guess_sequence": " ".join(guessed_words),
                "feedback_sequence": " ".join(feedbacks),
            }

        candidate_ids = filter_candidates(candidate_ids, matrix[guess], code)
        if answer_id not in candidate_ids:
            raise RuntimeError(
                f"The true answer {answer} was filtered out after {guess}: {feedback_text(code)}"
            )

        if turn < MAX_TURNS:
            guess = choose_guess(
                strategy,
                candidate_ids,
                answers,
                legal_guesses,
                matrix,
                word_frequencies,
                rng,
                frozenset(guessed_words),
                decision_cache,
            )

    return {
        "answer": answer,
        "strategy": strategy,
        "opening_word": opening_word,
        "solved": False,
        "guesses_used": MAX_TURNS,
        "guess_sequence": " ".join(guessed_words),
        "feedback_sequence": " ".join(feedbacks),
    }


def percentile(values: list[int], fraction: float) -> int:
    """Nearest-rank percentile, with fraction between 0 and 1."""
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def summarize(
    results: list[dict[str, object]], opening_word: str, strategy: str
) -> dict[str, object]:
    """Calculate metrics for one opener/continuation-strategy pair."""
    rows = [
        row for row in results
        if row["opening_word"] == opening_word and row["strategy"] == strategy
    ]
    total = len(rows)
    solved_rows = [row for row in rows if row["solved"]]
    turns = [int(row["guesses_used"]) for row in rows]
    solved_turns = [int(row["guesses_used"]) for row in solved_rows]
    return {
        "opening_word": opening_word,
        "strategy": strategy,
        "answers_tested": total,
        "solved": len(solved_rows),
        "failed": total - len(solved_rows),
        "solve_rate_percent": 100 * len(solved_rows) / total if total else 0,
        "mean_guesses_all_games": statistics.mean(turns) if turns else 0,
        "mean_guesses_when_solved": statistics.mean(solved_turns) if solved_turns else None,
        "median_guesses_all_games": statistics.median(turns) if turns else 0,
        "p95_guesses_all_games": percentile(turns, 0.95) if turns else 0,
        "solved_in_1": sum(row["solved"] and row["guesses_used"] == 1 for row in rows),
        "solved_in_2": sum(row["solved"] and row["guesses_used"] == 2 for row in rows),
        "solved_in_3": sum(row["solved"] and row["guesses_used"] == 3 for row in rows),
        "solved_in_4": sum(row["solved"] and row["guesses_used"] == 4 for row in rows),
        "solved_in_5": sum(row["solved"] and row["guesses_used"] == 5 for row in rows),
        "solved_in_6": sum(row["solved"] and row["guesses_used"] == 6 for row in rows),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def opening_analysis(
    answers: list[str],
    legal_guesses: list[str],
    matrix: dict[str, bytes],
    word_frequencies: dict[str, int],
) -> list[dict[str, object]]:
    """Score openers by information, candidate reduction, worst case, and word use."""
    total = len(answers)
    rows = []
    answer_set = set(answers)
    for guess in legal_guesses:
        buckets = Counter(matrix[guess])
        sizes = list(buckets.values())
        entropy = -sum((size / total) * math.log2(size / total) for size in sizes)
        rows.append({
            "opening_word": guess,
            "in_answer_list": guess in answer_set,
            "corpus_count": word_frequencies.get(guess, 0),
            "answers_tested": total,
            "feedback_patterns_seen": len(buckets),
            "entropy_bits": entropy,
            "expected_candidates_remaining": sum(size * size for size in sizes) / total,
            "median_candidates_remaining": statistics.median(
                buckets[matrix[guess][answer_id]] for answer_id in range(total)
            ),
            "worst_case_candidates_remaining": max(sizes),
        })
    return rows


def select_finalists(opening_scores: list[dict[str, object]], top_count: int) -> list[str]:
    """Take top words under four criteria and retain ADIEU/OUIJA baselines."""
    by_entropy = sorted(
        opening_scores,
        key=lambda row: (-float(row["entropy_bits"]), float(row["expected_candidates_remaining"]), str(row["opening_word"])),
    )
    by_expected = sorted(
        opening_scores,
        key=lambda row: (float(row["expected_candidates_remaining"]), str(row["opening_word"])),
    )
    by_worst = sorted(
        opening_scores,
        key=lambda row: (int(row["worst_case_candidates_remaining"]), float(row["expected_candidates_remaining"]), str(row["opening_word"])),
    )
    by_common = sorted(
        opening_scores,
        key=lambda row: (-int(row["corpus_count"]), str(row["opening_word"])),
    )

    finalists = set(BASELINE_OPENERS)
    finalists.update(str(row["opening_word"]) for row in by_entropy[:top_count])
    finalists.update(str(row["opening_word"]) for row in by_expected[:top_count])
    finalists.update(str(row["opening_word"]) for row in by_worst[:top_count])
    finalists.update(str(row["opening_word"]) for row in by_common[:top_count])
    return sorted(finalists)


def make_solve_rate_chart(
    summary: list[dict[str, object]], strategy: str, path: Path
) -> None:
    """Write a horizontal SVG chart for one continuation strategy."""
    rows = sorted(
        [row for row in summary if row["strategy"] == strategy],
        key=lambda row: (-float(row["solve_rate_percent"]), str(row["opening_word"])),
    )
    width = 850
    row_height = 30
    height = 105 + row_height * len(rows)
    left, top, plot_width = 160, 65, 600
    bar_height = 15
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#253243}.grid{stroke:#d8e1e8;stroke-width:1}</style>',
        f'<text x="425" y="28" text-anchor="middle" font-size="19" font-weight="700">Solve rate by opening word: {html.escape(strategy)}</text>',
        '<text x="425" y="48" text-anchor="middle" font-size="11">Each opener is held fixed across the answer list; all games use the same continuation rule</text>',
    ]
    for tick in range(0, 101, 20):
        x = left + plot_width * tick / 100
        pieces.append(f'<line class="grid" x1="{x}" y1="{top-8}" x2="{x}" y2="{top + row_height*len(rows) - 3}"/>')
        pieces.append(f'<text x="{x}" y="{top-15}" text-anchor="middle" font-size="10">{tick}%</text>')
    color = {"random": "#94A3B8", "common": "#6A994E", "entropy": "#168AAD", "minimax": "#F4A261"}[strategy]
    for i, row in enumerate(rows):
        y = top + i * row_height
        rate = float(row["solve_rate_percent"])
        pieces.append(f'<text x="{left-12}" y="{y+12}" text-anchor="end" font-size="11">{html.escape(str(row["opening_word"]).upper())}</text>')
        pieces.append(f'<rect x="{left}" y="{y}" width="{plot_width*rate/100}" height="{bar_height}" rx="3" fill="{color}"/>')
        pieces.append(f'<text x="{left + plot_width*rate/100 + 6}" y="{y+12}" font-size="10">{rate:.2f}%</text>')
    pieces.append('</svg>')
    path.write_text("\n".join(pieces), encoding="utf-8")


def make_analysis_charts(
    opening_scores: list[dict[str, object]],
    summary: list[dict[str, object]],
    results_dir: Path,
) -> None:
    """Create report-ready plots from the opener and full-game benchmarks."""
    results_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

    # 1. One-turn information trade-off for every legal opener.
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    x = [float(row["expected_candidates_remaining"]) for row in opening_scores]
    y = [float(row["entropy_bits"]) for row in opening_scores]
    counts = [int(row["corpus_count"]) for row in opening_scores]
    scatter = ax.scatter(x, y, c=[math.log10(count + 1) for count in counts],
                         cmap="viridis", s=13, alpha=0.55, linewidths=0)
    fig.colorbar(scatter, ax=ax, label="log10 general-corpus word count + 1")
    lookup = {str(row["opening_word"]).lower(): row for row in opening_scores}
    for word in ("soare", "roate", "raise", "about", "adieu", "ouija"):
        row = lookup.get(word)
        if row:
            ax.scatter(float(row["expected_candidates_remaining"]), float(row["entropy_bits"]),
                       s=45, edgecolors="black", linewidths=0.7, zorder=3)
            ax.annotate(word.upper(), (float(row["expected_candidates_remaining"]),
                                      float(row["entropy_bits"])), xytext=(5, 5),
                        textcoords="offset points", fontsize=8)
    ax.set(title="Opening guesses: information versus expected candidates",
           xlabel="Expected possible answers remaining after turn 1 (lower is better)",
           ylabel="Feedback entropy (bits; higher is better)")
    ax.grid(alpha=0.22)
    fig.tight_layout()
    fig.savefig(results_dir / "opening_tradeoff.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # Pivot summary rows into strategy x opener values.
    openers = sorted({str(row["opening_word"]).upper() for row in summary})
    colors = {"random": "#94A3B8", "common": "#6A994E", "entropy": "#168AAD", "minimax": "#F4A261"}
    strategies = list(STRATEGIES)
    width = 0.19
    positions = list(range(len(openers)))

    # 2. Solve rates: makes failures under simpler policies visible.
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for idx, strategy in enumerate(strategies):
        values = [next(float(r["solve_rate_percent"]) for r in summary
                       if str(r["opening_word"]).upper() == opener and r["strategy"] == strategy)
                  for opener in openers]
        offset = (idx - (len(strategies) - 1) / 2) * width
        ax.bar([p + offset for p in positions], values, width=width, label=strategy.title(),
               color=colors[strategy])
    ax.set(title="Full-game solve rate by opener and continuation policy",
           xlabel="Fixed opening guess", ylabel="Answers solved within six guesses (%)",
           ylim=(90, 100.8), xticks=positions, xticklabels=openers)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(results_dir / "solve_rate_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    # 3. Mean number of guesses, counting unsolved games as six turns.
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for idx, strategy in enumerate(strategies):
        values = [next(float(r["mean_guesses_all_games"]) for r in summary
                       if str(r["opening_word"]).upper() == opener and r["strategy"] == strategy)
                  for opener in openers]
        offset = (idx - (len(strategies) - 1) / 2) * width
        ax.bar([p + offset for p in positions], values, width=width, label=strategy.title(),
               color=colors[strategy])
    ax.set(title="Mean guesses used by opener and continuation policy",
           xlabel="Fixed opening guess", ylabel="Mean guesses (failed games count as six)",
           ylim=(3.3, 4.5), xticks=positions, xticklabels=openers)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(results_dir / "mean_guesses_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_readable_summary(
    path: Path,
    summary: list[dict[str, object]],
    opening_scores: list[dict[str, object]],
    answer_count: int,
    seed: int,
    is_sample: bool,
) -> None:
    """Write a concise interpretation of the opener and game-level results."""
    scope = "sample benchmark" if is_sample else "full fixed-answer-list benchmark"
    ranking = sorted(
        opening_scores,
        key=lambda row: (-float(row["entropy_bits"]), float(row["expected_candidates_remaining"]), str(row["opening_word"])),
    )
    best_pair = max(
        summary,
        key=lambda row: (float(row["solve_rate_percent"]), -float(row["mean_guesses_all_games"])),
    )
    lines = [
        "# Wordle opening-word and strategy benchmark",
        "",
        f"This {scope} tested {answer_count:,} possible answers. The random baseline used seed {seed}.",
        "The common-word proxy uses word counts from Peter Norvig's `count_1w.txt`, derived from the Google Web Trillion Word Corpus (see https://www.norvig.com/ngrams/). This corpus measures general web-text frequency, not Wordle answer frequency or human decision performance.",
        "Opening candidates were ranked by immediate feedback statistics and corpus frequency. The top words under "
        "entropy, expected remaining candidates, worst-case remaining candidates, and word frequency were then played "
        "through six turns, along with ADIEU and OUIJA as baselines.",
        "",
        "## Top opening words by entropy",
        "",
        "| Rank | Word | Entropy (bits) | Expected candidates left | Worst-case group |",
        "|---:|---|---:|---:|---:|",
    ]
    for rank, row in enumerate(ranking[:10], start=1):
        lines.append(
            f"| {rank} | {str(row['opening_word']).upper()} | {float(row['entropy_bits']):.4f} | "
            f"{float(row['expected_candidates_remaining']):.2f} | {row['worst_case_candidates_remaining']} |"
        )
    common_ranking = sorted(
        opening_scores,
        key=lambda row: (-int(row["corpus_count"]), str(row["opening_word"])),
    )
    lines.extend([
        "",
        "## Top opening words by corpus frequency",
        "",
        "These are common five-letter words in the general English corpus. Corpus frequency is only a proxy for familiarity; it is not a measured Wordle-answer probability.",
        "",
        "| Rank | Word | Corpus count | Entropy (bits) | Expected candidates left |",
        "|---:|---|---:|---:|---:|",
    ])
    for rank, row in enumerate(common_ranking[:10], start=1):
        lines.append(
            f"| {rank} | {str(row['opening_word']).upper()} | {int(row['corpus_count']):,} | "
            f"{float(row['entropy_bits']):.4f} | {float(row['expected_candidates_remaining']):.2f} |"
        )
    lines.extend([
        "",
        "## Full-game results",
        "",
        "| Opening | Continuation strategy | Solved | Failed | Solve rate | Mean turns (all games) | Mean turns (solved only) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in sorted(summary, key=lambda r: (str(r["opening_word"]), STRATEGIES.index(str(r["strategy"])) )):
        solved_mean = row["mean_guesses_when_solved"]
        solved_mean_text = "n/a" if solved_mean is None else f"{float(solved_mean):.2f}"
        lines.append(
            f"| {str(row['opening_word']).upper()} | {row['strategy']} | {row['solved']} | {row['failed']} | "
            f"{float(row['solve_rate_percent']):.2f}% | {float(row['mean_guesses_all_games']):.3f} | {solved_mean_text} |"
        )
    lines.extend([
        "",
        f"The best tested opener/strategy pair by solve rate in this run was **{str(best_pair['opening_word']).upper()} + {best_pair['strategy']}** "
        f"({float(best_pair['solve_rate_percent']):.2f}%). This describes this fixed answer-list benchmark; it is not a guarantee about future NYT answers.",
        "",
        "## How to read the opening metrics",
        "",
        "Entropy rewards a guess that tends to divide answers into many balanced feedback groups. "
        "Expected candidates left is the average size of the group the answer falls into. Worst-case group is the largest such group.",
        "These are one-turn heuristics. The full-game solve rate is a separate result because the later guesses and six-turn limit matter too.",
        "",
        "## Strategy definitions and limitations",
        "",
        "- `random` picks a random remaining possible answer after the opener.",
        "- `common` picks the remaining answer with the highest count in the English corpus; it does not use probe guesses.",
        "- `entropy` picks the legal guess with the greatest next-turn feedback entropy.",
        "- `minimax` picks the legal guess with the smallest largest feedback group.",
        "- Entropy and minimax may choose a legal guess that cannot itself be the answer; random is restricted to remaining answers.",
        "- The benchmark treats listed answers as equally likely and uses a fixed historical answer list. Corpus counts are used only for the common-word policy and opener ranking.",
        "- The opening word is selected and evaluated on the same fixed list, so the ranking is exact for that list but may not generalize to a different answer distribution.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_saved_games(
    all_answers: list[str],
    legal_guesses: list[str],
    word_frequencies: dict[str, int],
    seed: int,
) -> None:
    """Repair and summarize an already completed games.csv without resimulation.

    Older runs may have blank opening_word values on failed games. The first
    word in guess_sequence is the opener, so it can be recovered safely.
    """
    games_path = RESULTS_DIR / "games.csv"
    if not games_path.exists():
        raise FileNotFoundError(
            f"Could not find {games_path}; run the full benchmark before using this option."
        )

    answers = all_answers
    matrix = build_feedback_matrix(answers, legal_guesses, MATRIX_CACHE_FILE)
    with games_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError(f"{games_path} contains no game rows.")

    for row in rows:
        if not row.get("opening_word"):
            sequence = row.get("guess_sequence", "").split()
            if not sequence:
                raise ValueError("A saved game row has neither an opener nor a guess sequence.")
            row["opening_word"] = sequence[0].lower()
        row["opening_word"] = str(row["opening_word"]).lower()
        row["strategy"] = str(row["strategy"]).lower()
        row["solved"] = str(row["solved"]).strip().lower() == "true"
        row["guesses_used"] = int(row["guesses_used"])

    openers = sorted({str(row["opening_word"]) for row in rows})
    unknown = [word for word in openers if word not in legal_guesses]
    if unknown:
        raise ValueError(f"Saved game rows contain unknown openers: {unknown}")

    # Rewrite the file with the recovered opener and normalized data types.
    write_csv(games_path, rows)
    opening_scores = opening_analysis(answers, legal_guesses, matrix, word_frequencies)
    opening_scores.sort(
        key=lambda row: (
            -float(row["entropy_bits"]),
            float(row["expected_candidates_remaining"]),
            str(row["opening_word"]),
        )
    )
    summaries = [
        summarize(rows, opener, strategy)
        for opener in openers
        for strategy in STRATEGIES
    ]
    write_csv(RESULTS_DIR / "opening_scores.csv", opening_scores)
    write_csv(RESULTS_DIR / "benchmark_summary.csv", summaries)
    for strategy in STRATEGIES:
        make_solve_rate_chart(
            summaries, strategy, RESULTS_DIR / f"solve_rate_by_opening_{strategy}.svg"
        )
    make_analysis_charts(opening_scores, summaries, RESULTS_DIR)
    write_readable_summary(
        RESULTS_DIR / "summary.md", summaries, opening_scores,
        len(all_answers), seed, False
    )
    print(f"Recovered and summarized {len(rows):,} saved games across {len(openers)} openers.")
    print(f"Updated summary files in: {RESULTS_DIR}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="use a random sample of this many answers (quick check; omit for all answers)",
    )
    parser.add_argument("--seed", type=int, default=20304000, help="seed for reproducible random guesses")
    parser.add_argument(
        "--top-openers", type=int, default=TOP_OPENERS_PER_METRIC,
        help="number of opener candidates retained from each ranking (default: 3)",
    )
    parser.add_argument(
        "--summarize-existing", action="store_true",
        help="repair and summarize results/games.csv without simulating games again",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be a positive number.")
    if args.top_openers <= 0:
        raise ValueError("--top-openers must be a positive number.")

    all_answers = load_words(ANSWERS_FILE)
    extra_guesses = load_words(EXTRA_GUESSES_FILE)
    word_frequencies = load_word_frequencies(FREQUENCY_FILE)
    legal_guesses = sorted(set(all_answers) | set(extra_guesses))

    if args.summarize_existing:
        summarize_saved_games(all_answers, legal_guesses, word_frequencies, args.seed)
        return

    missing_baselines = [word for word in BASELINE_OPENERS if word not in legal_guesses]
    if missing_baselines:
        raise ValueError(f"Baseline opener(s) missing from legal guesses: {missing_baselines}")

    is_sample = args.limit is not None and args.limit < len(all_answers)
    if is_sample:
        sample_rng = random.Random(args.seed)
        answers = sorted(sample_rng.sample(all_answers, args.limit))
    else:
        answers = all_answers

    print(f"Possible answers in this run: {len(answers):,}")
    print(f"Legal guesses considered as openers: {len(legal_guesses):,}")
    print(f"ADIEU and OUIJA will be included as baselines.")
    matrix = build_feedback_matrix(answers, legal_guesses, MATRIX_CACHE_FILE)
    started = time.time()
    opening_scores = opening_analysis(answers, legal_guesses, matrix, word_frequencies)
    opening_scores.sort(
        key=lambda row: (
            -float(row["entropy_bits"]),
            float(row["expected_candidates_remaining"]),
            str(row["opening_word"]),
        )
    )
    finalists = select_finalists(opening_scores, args.top_openers)
    print("\nTop openers by immediate entropy:")
    for row in opening_scores[: min(10, len(opening_scores))]:
        print(
            f"  {str(row['opening_word']).upper():5}  entropy={float(row['entropy_bits']):.4f} bits  "
            f"expected remaining={float(row['expected_candidates_remaining']):.2f}  "
            f"worst group={row['worst_case_candidates_remaining']}"
        )
    print("\nOpeners selected for full-game benchmarks:", ", ".join(word.upper() for word in finalists))

    results: list[dict[str, object]] = []
    decision_cache: dict[tuple[str, tuple[int, ...], tuple[str, ...]], str] = {}
    for opening_word in finalists:
        print(f"\nBenchmarking {opening_word.upper()} as the fixed opener...")
        for answer_id in range(len(answers)):
            for strategy in STRATEGIES:
                results.append(
                    simulate_answer(
                        answer_id, strategy, opening_word, answers, legal_guesses,
                        matrix, word_frequencies, decision_cache, args.seed,
                    )
                )
            if (answer_id + 1) % 250 == 0 or answer_id + 1 == len(answers):
                print(f"  Simulated {answer_id + 1:,}/{len(answers):,} answers")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS_DIR / "games.csv", results)
    summaries = [
        summarize(results, opener, strategy)
        for opener in finalists
        for strategy in STRATEGIES
    ]
    write_csv(RESULTS_DIR / "opening_scores.csv", opening_scores)
    write_csv(RESULTS_DIR / "benchmark_summary.csv", summaries)
    for strategy in STRATEGIES:
        make_solve_rate_chart(
            summaries, strategy, RESULTS_DIR / f"solve_rate_by_opening_{strategy}.svg"
        )
    make_analysis_charts(opening_scores, summaries, RESULTS_DIR)
    write_readable_summary(
        RESULTS_DIR / "summary.md", summaries, opening_scores,
        len(answers), args.seed, is_sample
    )

    print("\nFULL-GAME RESULTS")
    print("Opener | Strategy | Solve rate | Mean turns (all) | Mean turns (solved)")
    for row in summaries:
        solved_mean = row["mean_guesses_when_solved"]
        solved_mean_text = "n/a" if solved_mean is None else f"{float(solved_mean):.3f}"
        print(
            f"{str(row['opening_word']).upper():6} | {str(row['strategy']):8} | "
            f"{float(row['solve_rate_percent']):8.2f}% | "
            f"{float(row['mean_guesses_all_games']):15.3f} | {solved_mean_text}"
        )
    print(f"\nFinished in {time.time() - started:.1f} seconds.")
    print(f"Results saved in: {RESULTS_DIR}")
    if is_sample:
        print("This was a sample run. Omit --limit to rank and benchmark the full answer list.")


if __name__ == "__main__":
    main()
