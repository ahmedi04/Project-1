# Project-1
Retail Intelligence - SQL, Python EDA, and Business Reporting

---

## Day 1 - SQL and ER Diagram

Initial database exploration using `day1_discovery.sql` against the `retail_db` MySQL database.

---

## Day 2 - SQL Aggregations and KPI Queries

Business KPI queries written in `day2_aggregations.sql` and exported to `day2_results/` using `export_day2_results.py`.

---

## Day 3 - Advanced Analytics

Advanced SQL analytics in `day3_advanced_analytics.sql` (RFM segmentation, cohort retention, product pairs, year-over-year revenue, running totals). Results exported using `day3_export_csv.py`.

---

## Day 4 - Python EDA, Visualizations, and Executive Report

Full exploratory data analysis, business visualizations, a Power BI-ready metrics export, and a one-page executive summary PDF — all in a single Jupyter notebook.

### What was done

- Loaded all Day 2 (`day2_results/*.csv`) and Day 3 (`rfm_segment_summary.csv`, `cohort_retention.csv`) exports into pandas DataFrames
- Performed EDA covering missing values, duplicate row counts, data types, and descriptive statistics for every dataset
- Created five publication-ready charts saved to `charts/`:
  1. **Monthly Revenue Trend - Comparable SKUs** — monthly revenue from the Query 6 SKU-month comparison output
  2. **Revenue by City** — total revenue per city from the Query 1 city/store aggregation
  3. **Top 10 Products by Revenue** — highest-revenue SKUs from the comparable-month output
  4. **RFM Customer Segments** — pie chart showing Champions, Loyal, At Risk, and Lost customer shares
  5. **Cohort Retention Heatmap** — retention rate by signup cohort and months since acquisition
- Exported `summary_metrics.csv` containing 44 Power BI-ready metrics in long format (metric_category, metric_name, dimension_value, metric_value, unit)
- Generated `executive_summary.pdf` — a one-page landscape report answering three business questions with embedded charts, KPI cards, and recommended actions

### Key data findings

- **Overall gross revenue: $69,102,366.14** — sourced from `day2_query1.csv` (Query 1 joins sales to stores with no filters and no LIMIT, making it the most complete revenue figure available)
- **Query 2 (revenue_by_category)** applies `LIMIT 5` and returns only the top five categories — it is a ranked leaderboard and must not be summed to represent overall gross revenue
- **Query 6 (product_monthly_revenue)** filters to SKU-months where a prior calendar month exists and revenue declined — results are directional comparable-SKU analysis, not the complete company gross-revenue total

### Day 4 deliverables

| File | Description |
|---|---|
| `retail_eda.ipynb` | Jupyter notebook — EDA, charts, metrics export, and PDF generation |
| `charts/` | Five PNG chart files used in the notebook and PDF |
| `summary_metrics.csv` | 44-row Power BI-ready metrics file in long format |
| `executive_summary.pdf` | One-page landscape executive summary PDF |

### How to run

1. Open `retail_eda.ipynb` in VS Code
2. Select a Python or Jupyter kernel
3. Install dependencies if needed:
   ```bash
   pip install pandas numpy matplotlib seaborn reportlab
   ```
4. Click **Run All** — cells execute sequentially from top to bottom

> **Note:** The notebook must be run from the `Project-1` root folder so that relative paths to `day2_results/`, `rfm_segment_summary.csv`, and `cohort_retention.csv` resolve correctly.
