# Project Source of Truth v4

## Mission
Build a POD opportunity intelligence platform for Etsy that uses multiple data sources to decide what to test.

## Core Data Sources

### eRank
Primary role: keyword intelligence.

Data:
- keyword
- search volume / demand estimate
- competition
- trend direction
- seasonality
- related keywords
- competitor/keyword notes

### EverBee / Alura
Primary role: listing/product traction intelligence.

Data:
- listing URL / listing ID
- title
- shop
- estimated monthly sales
- estimated monthly revenue
- conversion estimate
- listing age
- favorites / reviews
- trend/growth data
- tags
- product category

### Apify
Secondary role: live Etsy snapshot verification.

Data:
- current search result appearance
- current price/title/shop context
- page one competition
- visual/position context if available

### Manual Review
Primary role: business judgment.

Data:
- originality assessment
- IP/trademark risk
- design feasibility
- margin fit
- competition quality
- approved/rejected status
- notes

### Own Etsy Stats Later
Primary role: ground truth.

Data:
- impressions
- clicks
- favorites
- sales
- conversion rate
- revenue
- profit

## v4 Rule
Do not let Apify be the backbone. Apify is optional verification, not proof of sales.

## Current Active Milestone
Design v4 intake and review model. Do not implement workflows yet unless approved.
