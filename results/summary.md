# Wordle opening-word and strategy benchmark

This full fixed-answer-list benchmark tested 2,315 possible answers. The random baseline used seed 20304000.
The common-word proxy uses word counts from Peter Norvig's `count_1w.txt`, derived from the Google Web Trillion Word Corpus (see https://www.norvig.com/ngrams/). This corpus measures general web-text frequency, not Wordle answer frequency or human decision performance.
Opening candidates were ranked by immediate feedback statistics and corpus frequency. The top words under entropy, expected remaining candidates, worst-case remaining candidates, and word frequency were then played through six turns, along with ADIEU and OUIJA as baselines.

## Top opening words by entropy

| Rank | Word | Entropy (bits) | Expected candidates left | Worst-case group |
|---:|---|---:|---:|---:|
| 1 | SOARE | 5.8860 | 62.30 | 183 |
| 2 | ROATE | 5.8828 | 60.42 | 195 |
| 3 | RAISE | 5.8779 | 61.00 | 168 |
| 4 | RAILE | 5.8657 | 61.33 | 173 |
| 5 | REAST | 5.8655 | 71.77 | 227 |
| 6 | SLATE | 5.8558 | 71.57 | 221 |
| 7 | CRATE | 5.8349 | 72.90 | 246 |
| 8 | SALET | 5.8346 | 71.27 | 221 |
| 9 | IRATE | 5.8314 | 63.78 | 194 |
| 10 | TRACE | 5.8305 | 74.02 | 246 |

## Top opening words by corpus frequency

These are common five-letter words in the general English corpus. Corpus frequency is only a proxy for familiarity; it is not a measured Wordle-answer probability.

| Rank | Word | Corpus count | Entropy (bits) | Expected candidates left |
|---:|---|---:|---:|---:|
| 1 | ABOUT | 1,226,734,006 | 4.6849 | 167.02 |
| 2 | OTHER | 978,481,319 | 5.0457 | 114.98 |
| 3 | WHICH | 810,514,085 | 3.3090 | 520.88 |
| 4 | THEIR | 782,849,411 | 5.3275 | 106.82 |
| 5 | THERE | 701,170,205 | 4.8898 | 163.28 |
| 6 | FIRST | 578,161,543 | 4.9247 | 160.11 |
| 7 | WOULD | 572,644,147 | 4.2975 | 258.29 |
| 8 | THESE | 541,003,982 | 4.7339 | 194.28 |
| 9 | CLICK | 536,746,424 | 3.6936 | 396.63 |
| 10 | PRICE | 501,651,226 | 5.3190 | 114.27 |

## Full-game results

| Opening | Continuation strategy | Solved | Failed | Solve rate | Mean turns (all games) | Mean turns (solved only) |
|---|---|---:|---:|---:|---:|---:|
| ABOUT | random | 2265 | 50 | 97.84% | 4.048 | 4.00 |
| ABOUT | common | 2271 | 44 | 98.10% | 4.021 | 3.98 |
| ABOUT | entropy | 2315 | 0 | 100.00% | 3.790 | 3.79 |
| ABOUT | minimax | 2315 | 0 | 100.00% | 3.854 | 3.85 |
| ADIEU | random | 2238 | 77 | 96.67% | 4.073 | 4.01 |
| ADIEU | common | 2272 | 43 | 98.14% | 4.028 | 3.99 |
| ADIEU | entropy | 2315 | 0 | 100.00% | 3.786 | 3.79 |
| ADIEU | minimax | 2315 | 0 | 100.00% | 3.834 | 3.83 |
| OUIJA | random | 2232 | 83 | 96.41% | 4.296 | 4.23 |
| OUIJA | common | 2247 | 68 | 97.06% | 4.261 | 4.21 |
| OUIJA | entropy | 2315 | 0 | 100.00% | 3.993 | 3.99 |
| OUIJA | minimax | 2315 | 0 | 100.00% | 4.038 | 4.04 |
| RAISE | random | 2270 | 45 | 98.06% | 3.930 | 3.89 |
| RAISE | common | 2284 | 31 | 98.66% | 3.873 | 3.84 |
| RAISE | entropy | 2315 | 0 | 100.00% | 3.639 | 3.64 |
| RAISE | minimax | 2315 | 0 | 100.00% | 3.696 | 3.70 |
| ROATE | random | 2271 | 44 | 98.10% | 3.861 | 3.82 |
| ROATE | common | 2279 | 36 | 98.44% | 3.902 | 3.87 |
| ROATE | entropy | 2315 | 0 | 100.00% | 3.638 | 3.64 |
| ROATE | minimax | 2315 | 0 | 100.00% | 3.682 | 3.68 |
| SOARE | random | 2275 | 40 | 98.27% | 3.919 | 3.88 |
| SOARE | common | 2279 | 36 | 98.44% | 3.912 | 3.88 |
| SOARE | entropy | 2315 | 0 | 100.00% | 3.638 | 3.64 |
| SOARE | minimax | 2315 | 0 | 100.00% | 3.679 | 3.68 |

The best tested opener/strategy pair by solve rate in this run was **ROATE + entropy** (100.00%). This describes this fixed answer-list benchmark; it is not a guarantee about future NYT answers.

## How to read the opening metrics

Entropy rewards a guess that tends to divide answers into many balanced feedback groups. Expected candidates left is the average size of the group the answer falls into. Worst-case group is the largest such group.
These are one-turn heuristics. The full-game solve rate is a separate result because the later guesses and six-turn limit matter too.

## Strategy definitions and limitations

- `random` picks a random remaining possible answer after the opener.
- `common` picks the remaining answer with the highest count in the English corpus; it does not use probe guesses.
- `entropy` picks the legal guess with the greatest next-turn feedback entropy.
- `minimax` picks the legal guess with the smallest largest feedback group.
- Entropy and minimax may choose a legal guess that cannot itself be the answer; random is restricted to remaining answers.
- The benchmark treats listed answers as equally likely and uses a fixed historical answer list. Corpus counts are used only for the common-word policy and opener ranking.
- The opening word is selected and evaluated on the same fixed list, so the ranking is exact for that list but may not generalize to a different answer distribution.
