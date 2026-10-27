# Wordle Probability and Strategy Benchmark

A simulation study comparing four Wordle guessing strategies across 2,315 possible answers.

The project compares random guessing, choosing the most common remaining word, maximum information (entropy), and minimax. In this fixed-answer-list benchmark, entropy and minimax solved every answer; the best average was 3.638 guesses with ROATE followed by entropy-based guesses.

**Full report:** [Wordle Probability and Strategy Benchmark](results/wordle_probability_project_report.md)  
**Code:** [wordle.py](wordle.py)

## Solve-rate comparison

![Solve rates by opener and strategy](results/solve_rate_comparison.png)
