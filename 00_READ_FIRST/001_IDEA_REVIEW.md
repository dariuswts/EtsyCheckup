# Idea Review

## Verdict
The project is viable if rebuilt as a multi-source opportunity intelligence system.

It is not viable as an Apify-first winner detector.

## What Is Strong About The New Idea
The new idea uses the right source for each question:

| Question | Best Source |
|---|---|
| What are people searching for? | eRank |
| Which products seem to have traction? | EverBee / Alura |
| What currently appears on Etsy search? | Apify |
| Is the idea original and worth testing? | Manual review |
| Did our listing actually work? | Own Etsy stats |

## Why This Is Better
Instead of `reviews high = make product`, v4 uses:

```text
keyword demand
+ product traction estimate
+ live search context
+ competition quality
+ originality review
+ margin review
= opportunity candidate
```

## Main Risks
1. EverBee/eRank numbers may still be estimates, not ground truth.
2. Manual or CSV intake may be slower at first.
3. Automating paid dashboards may violate terms or be fragile.
4. Scoring can become fake precision if inputs are weak.
5. POD remains competitive.

## Risk Controls
Treat estimates as directional, preserve source/confidence, keep manual review in v1, do not publish automatically, start with manual/CSV intake, and add automation only after data proves useful.

## Business Conclusion
The moat is no longer scraping Etsy. The moat is multi-source opportunity intelligence + disciplined testing + original concepts + learning from outcomes.
