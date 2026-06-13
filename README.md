# POD Opportunity Intelligence Platform — Source of Truth v4

This is the clean v4 reset. The project is no longer Apify-first.

## New Thesis
Use multiple intelligence layers to find Etsy POD opportunities:

```text
eRank keyword intelligence
+ EverBee / Alura product intelligence
+ optional Apify live Etsy verification
+ manual review
+ later Etsy performance data
= better opportunity decisions
```

## Why v4 Exists
The previous Apify-first plan proved that scraping can work technically, but also showed that basic Etsy page data is too weak to identify winners.

Store reviews, listing titles, prices, and badges are not enough.

## First Milestone
Do not build automation first.

First design the data intake structure for:
1. eRank keyword data.
2. EverBee / Alura listing/product data.
3. Manual review fields.
4. Optional Apify verification fields.

Then build the smallest manual/CSV intake before connecting external tools.
