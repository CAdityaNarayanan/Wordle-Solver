"""Create a readable PDF report from the saved Wordle benchmark outputs."""

from __future__ import annotations

import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PDF_PATH = RESULTS / "wordle_probability_project_report.pdf"


def read_csv(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def add_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
    canvas.line(0.7 * inch, 0.58 * inch, 7.8 * inch, 0.58 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52606D"))
    canvas.drawString(0.72 * inch, 0.4 * inch, "Wordle Probability and Strategy Benchmark")
    canvas.drawRightString(7.78 * inch, 0.4 * inch, f"{doc.page}")
    canvas.restoreState()


def build_report() -> None:
    summary = read_csv("benchmark_summary.csv")
    opening = read_csv("opening_scores.csv")
    games = read_csv("games.csv")
    opener_names = sorted({row["opening_word"].upper() for row in summary})
    answer_count = int(summary[0]["answers_tested"])
    entropy_rows = [row for row in summary if row["strategy"] == "entropy"]
    minimax_rows = [row for row in summary if row["strategy"] == "minimax"]
    common_rows = [row for row in summary if row["strategy"] == "common"]
    random_rows = [row for row in summary if row["strategy"] == "random"]
    best_entropy = min(entropy_rows, key=lambda row: float(row["mean_guesses_all_games"]))
    best_minimax = min(minimax_rows, key=lambda row: float(row["mean_guesses_all_games"]))
    best_common = max(common_rows, key=lambda row: float(row["solve_rate_percent"]))
    best_random = max(random_rows, key=lambda row: float(row["solve_rate_percent"]))
    entropy_opening_rank = sorted(opening, key=lambda row: -float(row["entropy_bits"]))
    soare = next(row for row in opening if row["opening_word"].lower() == "soare")
    roate = next(row for row in opening if row["opening_word"].lower() == "roate")
    about = next(row for row in opening if row["opening_word"].lower() == "about")
    soare_common = next(row for row in common_rows if row["opening_word"].lower() == "soare")
    about_common = next(row for row in common_rows if row["opening_word"].lower() == "about")
    adieu_entropy = next(row for row in entropy_rows if row["opening_word"].lower() == "adieu")
    ouija_entropy = next(row for row in entropy_rows if row["opening_word"].lower() == "ouija")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=25, leading=30, textColor=colors.HexColor("#102A43"),
        alignment=TA_LEFT, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Subtitle", parent=styles["Normal"], fontSize=11, leading=16,
        textColor=colors.HexColor("#486581"), spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="Section", parent=styles["Heading1"], fontSize=16, leading=20,
        textColor=colors.HexColor("#102A43"), spaceBefore=12, spaceAfter=7,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="Subsection", parent=styles["Heading2"], fontSize=11.5, leading=15,
        textColor=colors.HexColor("#243B53"), spaceBefore=8, spaceAfter=4,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyClean", parent=styles["BodyText"], fontSize=9.5, leading=14,
        textColor=colors.HexColor("#243B53"), spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Caption", parent=styles["BodyText"], fontSize=8.2, leading=11,
        textColor=colors.HexColor("#52606D"), spaceBefore=3, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Small", parent=styles["BodyText"], fontSize=8.3, leading=11,
        textColor=colors.HexColor("#334E68"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Callout", parent=styles["BodyText"], fontSize=10, leading=15,
        textColor=colors.HexColor("#102A43"), backColor=colors.HexColor("#EAF4F4"),
        borderColor=colors.HexColor("#168AAD"), borderWidth=0.8, borderPadding=9,
        spaceBefore=4, spaceAfter=10,
    ))

    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=letter, rightMargin=0.72 * inch,
        leftMargin=0.72 * inch, topMargin=0.67 * inch, bottomMargin=0.77 * inch,
        title="Wordle Probability and Strategy Benchmark",
        author="Project report",
    )
    story = []
    p = lambda text, style="BodyClean": Paragraph(text, styles[style])
    story += [
        Spacer(1, 0.25 * inch),
        p("Wordle Probability and<br/>Strategy Benchmark", "ReportTitle"),
        p("A simulation study of opening guesses, feedback, and decision rules", "Subtitle"),
        p("Project report | October 2026", "Small"),
        Spacer(1, 0.13 * inch),
        p("At a glance", "Section"),
        p(
            f"I evaluated {len(games):,} simulated games: every one of {answer_count:,} listed answers "
            f"was tested with each of {len(opener_names)} opening words and four continuation strategies. "
            f"The entropy and minimax policies solved every answer in this fixed list. The entropy "
            f"policy used the fewest guesses on average in the best tested pairing: "
            f"{best_entropy['opening_word'].upper()} followed by entropy-based guesses, at "
            f"{float(best_entropy['mean_guesses_all_games']):.3f} guesses per answer.", "Callout"),
        p("1. Context and question", "Section"),
        p(
            "I became interested in Wordle as a small setting where probability and decision-making "
            "interact. A guess does more than try to name the answer: its colored feedback divides "
            "the remaining possibilities into groups. I wanted to understand how to measure the "
            "usefulness of a guess, and whether a strong opening word still matters when the later "
            "guesses are chosen systematically."),
        p(
            "The project compares opening words and four ways of choosing later guesses. The main "
            "question is: <b>how do different feedback-based decision rules affect the chance of "
            "solving the puzzle and the number of guesses used, when each possible answer is tested "
            "under the same conditions?</b> I also included familiar vowel-heavy openers, ADIEU and "
            "OUIJA, as reference points against words selected using information-based metrics."),
        p("2. Data and simulation design", "Section"),
        p(
            f"The answer universe contained {answer_count:,} five-letter words. The legal guess "
            "dictionary combined those answers with additional allowed guesses. For each answer, "
            "the simulator played six possible fixed openers (ABOUT, ADIEU, OUIJA, RAISE, ROATE, "
            "and SOARE), and then used each of four continuation policies. This produces "
            f"{answer_count:,} x 6 x 4 = {len(games):,} game runs. An individual run, or episode, "
            "means one complete simulated Wordle game for one chosen answer, one fixed opener, and "
            "one continuation policy."),
        p(
            "At each turn, the simulator compares the guess with the hidden answer and returns the "
            "usual green, yellow, and grey pattern. It handles repeated letters by assigning green "
            "matches first and then allocating yellow matches only to remaining copies of a letter. "
            "The answer list is filtered to retain only words consistent with all feedback so far. "
            "A game ends when the answer is guessed or after six guesses."),
        p("How opening words were selected", "Subsection"),
        p(
            "Every legal guess was scored against the same answer list. The opening metrics were "
            "feedback entropy, expected number of answers left after feedback, and the largest "
            "possible feedback group. The benchmark then selected the top three words under each "
            "metric, added the most frequent corpus words, and retained ADIEU and OUIJA as baselines. "
            "The union of these rankings resulted in six distinct openers."),
        p("Continuation policies", "Subsection"),
        p(
            "<b>Random:</b> choose a random remaining possible answer. <b>Common:</b> choose the "
            "remaining possible answer with the highest general English corpus count. "
            "<b>Entropy:</b> choose the legal guess whose possible feedback patterns have the "
            "highest entropy. <b>Minimax:</b> choose the legal guess that minimizes the size of the "
            "largest possible feedback group. Entropy and minimax can use a probe word that is not "
            "itself a possible answer; random and common choose only from remaining answer candidates."),
        p("3. Results", "Section"),
        p("Opening-word information trade-off", "Subsection"),
        p(
            "Entropy measures the uncertainty removed by feedback, in bits; higher is better. "
            "Expected candidates remaining is the average size of the feedback group; lower is "
            "better. The plot includes every legal opener, while labeled points identify examples "
            "discussed in this report."),
    ]
    img = Image(str(RESULTS / "opening_tradeoff.png"), width=6.75 * inch, height=4.12 * inch)
    story += [img, p(
        f"Figure 1. SOARE produced {float(soare['entropy_bits']):.3f} bits of entropy and "
        f"{float(soare['expected_candidates_remaining']):.2f} expected remaining answers. ROATE "
        f"had {float(roate['entropy_bits']):.3f} bits and {float(roate['expected_candidates_remaining']):.2f} "
        f"expected remaining answers. ABOUT was much more common in general text, but its opening "
        f"feedback yielded {float(about['entropy_bits']):.3f} bits and {float(about['expected_candidates_remaining']):.2f} "
        "expected remaining answers. This illustrates the difference between familiarity and "
        "information value. Color encodes general corpus frequency, not Wordle answer likelihood.", "Caption")]

    story += [
        p("Full-game solve rates", "Subsection"),
        p(
            "The next graph compares the percentage of all listed answers solved within six guesses. "
            "The vertical axis is intentionally zoomed to 90-100% so the differences between the "
            "simpler policies remain visible; it does not start at zero."),
        Image(str(RESULTS / "solve_rate_comparison.png"), width=6.75 * inch, height=3.90 * inch),
        p(
            "Figure 2. Entropy and minimax solved all 2,315 listed answers for every tested opener. "
            f"The common-word policy's highest solve rate was {float(best_common['solve_rate_percent']):.2f}% "
            f"with {best_common['opening_word'].upper()}, while the random policy's highest was "
            f"{float(best_random['solve_rate_percent']):.2f}% with {best_random['opening_word'].upper()}. "
            "The common-word policy is a proxy for choosing a familiar answer, not a model of actual "
            "human behavior.", "Caption"),
        p("Mean guesses", "Subsection"),
        p(
            "Mean guesses counts every game; a failed game contributes six guesses. This combines "
            "efficiency and failures in one metric. Among entropy runs, the lowest mean was "
            f"{float(best_entropy['mean_guesses_all_games']):.3f} with {best_entropy['opening_word'].upper()}. "
            f"The best minimax mean was {float(best_minimax['mean_guesses_all_games']):.3f} with "
            f"{best_minimax['opening_word'].upper()}.", "BodyClean"),
        Image(str(RESULTS / "mean_guesses_comparison.png"), width=6.75 * inch, height=3.90 * inch),
        p(
            "Figure 3. The entropy policy used fewer guesses on average than minimax for each "
            "tested opener, although both had a 100% solve rate on this answer list. The distinction "
            "is that entropy optimizes average information, while minimax protects against the "
            "largest feedback group.", "Caption"),
        p("4. Interpreting the comparisons", "Section"),
        p("Information-based versus familiar openers", "Subsection"),
        p(
            f"The entropy results favor information-rich openers over vowel-heavy words when the "
            f"continuation policy can use the full legal-guess list. ADIEU plus entropy solved all "
            f"answers in {float(adieu_entropy['mean_guesses_all_games']):.3f} guesses on average; "
            f"OUIJA plus entropy required {float(ouija_entropy['mean_guesses_all_games']):.3f}. "
            "For a more familiar-answer policy, SOARE yielded "
            f"{float(soare_common['solve_rate_percent']):.2f}% solve rate and "
            f"{float(soare_common['mean_guesses_all_games']):.3f} mean guesses; ABOUT yielded "
            f"{float(about_common['solve_rate_percent']):.2f}% and "
            f"{float(about_common['mean_guesses_all_games']):.3f}, respectively. The opener's "
            "value depends on what the solver does with feedback afterward."),
        p("Best results in this benchmark", "Subsection"),
    ]

    result_table = [["Policy", "Best tested opener", "Solve rate", "Mean guesses"]]
    for label, row in (("Entropy", best_entropy), ("Minimax", best_minimax),
                       ("Common-word", best_common), ("Random", best_random)):
        result_table.append([
            label, row["opening_word"].upper(), f"{float(row['solve_rate_percent']):.2f}%",
            f"{float(row['mean_guesses_all_games']):.3f}",
        ])
    table = Table(result_table, colWidths=[1.45 * inch, 1.8 * inch, 1.35 * inch, 1.4 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102A43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F0F4F8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F0F4F8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BCCCDC")),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [table, Spacer(1, 9), p(
        f"Across all tested opener-policy pairs, ROATE plus entropy had the lowest mean "
        f"({float(best_entropy['mean_guesses_all_games']):.3f}); all entropy and minimax pairs "
        "solved every answer. These are results on the selected fixed answer set, not universal "
        "claims about the best way to play future Wordle puzzles."),
        p("5. Limitations", "Section"),
        p(
            "The answer words were treated as equally likely. Actual Wordle answer selection may "
            "not be uniform, and the list used here may not match a future answer list. Further, "
            "opening words were selected and evaluated using the same fixed answer universe; their "
            "rankings may therefore fit this list better than a different one."),
        p(
            "The common-word baseline uses five-letter counts from Peter Norvig's `count_1w.txt`, "
            "derived from the Google Web Trillion Word Corpus. General web frequency does not "
            "measure Wordle answer frequency or how a person chooses guesses. Even this baseline "
            "has access to the answer candidate list and filters it exactly using feedback; it "
            "does not represent a person playing from memory without a dictionary."),
        p(
            "The entropy and minimax policies are greedy: they optimize the next feedback step, "
            "rather than searching every possible full decision tree. Their perfect solve rates "
            "apply only to this benchmark's answer list, legal guesses, feedback rules, and six-turn "
            "limit. The random policy uses a fixed seed for repeatability; changing the seed could "
            "change its results."),
        p("6. Conclusion", "Section"),
        p(
            "This project turned Wordle into a controlled experiment in probability and sequential "
            "decision-making. The main finding is that using feedback to reduce uncertainty is "
            "more effective in this benchmark than simply selecting a likely-looking answer. "
            "Entropy and minimax each solved every tested answer, while entropy used slightly fewer "
            "guesses on average. The opener matters, but its effect is smaller when a strong "
            "feedback-based continuation policy is available. The human-style comparison is "
            "suggestive rather than definitive because the common-word baseline is only a proxy. "
            "The benchmark can be reproduced from `wordle.py` and the saved files in `data`, using "
            "seed 20,304,000; game-level records and aggregate tables are saved as CSV. General "
            "English word counts are from <link href='https://www.norvig.com/ngrams/' color='#168AAD'>" 
            "Peter Norvig's corpus files</link>."),
    ]

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"Created {PDF_PATH}")


if __name__ == "__main__":
    build_report()
