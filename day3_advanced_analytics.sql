-- ============================================================
-- Day 3: Advanced Analytics
-- Database: retail_db
-- Tables: sales, customers, skus, stores, inventory, promotions
-- Goal: Advanced customer analysis using CTEs and window functions
--       to surface segmentation, retention, product affinity,
--       year-over-year growth, and cumulative revenue trends.
-- ============================================================

USE retail_db;

-- ------------------------------------------------------------
-- Task 1: RFM Customer Segmentation
-- Segment customers by Recency (days since last purchase),
-- Frequency (number of transactions), and Monetary value
-- (total revenue) using the sales and customers tables.
-- Key columns: sales.customer_id, sales.date, sales.quantity,
--              sales.unit_price, sales.discount_pct,
--              customers.cust_id, customers.loyalty_segment
-- ------------------------------------------------------------

-- We build the RFM model in small CTE steps so each part is easy to follow.
WITH
-- 1) Find the analysis anchor date.
--    Requirement: recency is relative to 1 day after the maximum sales date.
max_sales_anchor AS (
	SELECT DATE_ADD(MAX(s.`date`), INTERVAL 1 DAY) AS anchor_date
	FROM sales s
),

-- 2) Build customer-level base metrics.
--    Start from customers so every customer is included, even with no purchases.
customer_rfm_base AS (
	SELECT
		c.cust_id AS customer_id,
		MAX(s.`date`) AS last_purchase_date,

		-- Recency: days between anchor_date and each customer's last purchase.
		-- If no purchase exists, set a very large recency so they rank as least recent.
		COALESCE(
			DATEDIFF(a.anchor_date, MAX(s.`date`)),
			99999
		) AS recency_days,

		-- Frequency: number of distinct purchase dates.
		COALESCE(COUNT(DISTINCT s.`date`), 0) AS frequency,

		-- Monetary: total revenue using the confirmed project formula.
		-- quantity * unit_price * (1 - discount_pct / 100)
		ROUND(
			COALESCE(
				SUM(s.quantity * s.unit_price * (1 - COALESCE(s.discount_pct, 0) / 100)),
				0
			),
			2
		) AS monetary
	FROM customers c
	CROSS JOIN max_sales_anchor a
	LEFT JOIN sales s
		ON c.cust_id = s.customer_id
	GROUP BY
		c.cust_id,
		a.anchor_date
),

-- 3) Score each customer into quartiles with NTILE(4).
--    NTILE divides sorted rows into 4 groups (1 to 4).
--    We set scoring so better customers get higher scores.
rfm_scored AS (
	SELECT
		b.customer_id,
		b.last_purchase_date,
		b.recency_days,
		b.frequency,
		b.monetary,

		-- Lower recency_days is better, so invert the quartile score.
		5 - NTILE(4) OVER (ORDER BY b.recency_days ASC) AS r_score,

		-- Higher frequency is better.
		NTILE(4) OVER (ORDER BY b.frequency ASC) AS f_score,

		-- Higher monetary is better.
		NTILE(4) OVER (ORDER BY b.monetary ASC) AS m_score
	FROM customer_rfm_base b
)

-- 4) Final output with combined RFM score and business-friendly segment labels.
SELECT
	customer_id,
	last_purchase_date,
	recency_days,
	frequency,
	monetary,
	r_score,
	f_score,
	m_score,
	CONCAT(r_score, f_score, m_score) AS rfm_score,
	CASE
		WHEN last_purchase_date IS NULL THEN 'Lost'
		WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
		WHEN r_score >= 2 AND f_score >= 3 AND m_score >= 2 THEN 'Loyal'
		WHEN r_score <= 2 AND (f_score >= 3 OR m_score >= 3) THEN 'At Risk'
		ELSE 'Lost'
	END AS customer_segment
FROM rfm_scored
ORDER BY
	r_score DESC,
	f_score DESC,
	m_score DESC,
	monetary DESC;

-- ------------------------------------------------------------
-- Task 2: Cohort Retention by Customer Signup Month
-- Group customers into cohorts by their signup month using
-- customers.registration_date, then track what percentage of
-- each cohort made a purchase in each subsequent month.
-- Key columns: sales.customer_id, sales.date,
--              customers.cust_id, customers.registration_date
-- ------------------------------------------------------------

-- We build cohort retention in CTE steps so each transformation is easy to understand.
WITH
-- 1) Assign every registered customer to a signup cohort month.
--    Cohort month is the first day of the registration month.
customer_cohorts AS (
	SELECT
		c.cust_id AS customer_id,
		DATE(DATE_FORMAT(c.registration_date, '%Y-%m-01')) AS cohort_month
	FROM customers c
	WHERE c.registration_date IS NOT NULL
),

-- 2) Calculate cohort size: total registered customers in each signup cohort.
cohort_sizes AS (
	SELECT
		cc.cohort_month,
		COUNT(*) AS cohort_size
	FROM customer_cohorts cc
	GROUP BY cc.cohort_month
),

-- 3) Build one row per customer per activity month.
--    This ensures each customer is counted only once per month,
--    even if they made multiple purchases in that month.
--    Also exclude any activity before the registration cohort month.
monthly_customer_activity AS (
	SELECT
		cc.cohort_month,
		cc.customer_id,
		DATE(DATE_FORMAT(s.`date`, '%Y-%m-01')) AS activity_month
	FROM customer_cohorts cc
	JOIN sales s
		ON cc.customer_id = s.customer_id
	WHERE s.`date` IS NOT NULL
	  AND DATE(DATE_FORMAT(s.`date`, '%Y-%m-01')) >= cc.cohort_month
	GROUP BY
		cc.cohort_month,
		cc.customer_id,
		DATE(DATE_FORMAT(s.`date`, '%Y-%m-01'))
),

-- 4) Aggregate monthly retained customers per cohort and compute month_number.
--    month_number = months between cohort_month and activity_month.
--    The signup month itself is month_number 0.
cohort_retention AS (
	SELECT
		mca.cohort_month,
		mca.activity_month,
		TIMESTAMPDIFF(MONTH, mca.cohort_month, mca.activity_month) AS month_number,
		COUNT(DISTINCT mca.customer_id) AS retained_customers
	FROM monthly_customer_activity mca
	GROUP BY
		mca.cohort_month,
		mca.activity_month,
		TIMESTAMPDIFF(MONTH, mca.cohort_month, mca.activity_month)
)

-- 5) Final cohort retention output.
SELECT
	cr.cohort_month,
	cr.activity_month,
	cr.month_number,
	cs.cohort_size,
	cr.retained_customers,
	ROUND((cr.retained_customers / cs.cohort_size) * 100, 2) AS retention_rate
FROM cohort_retention cr
JOIN cohort_sizes cs
	ON cr.cohort_month = cs.cohort_month
ORDER BY
	cr.cohort_month,
	cr.month_number;

-- ------------------------------------------------------------
-- Task 3: Top Product Pairs Bought Together
-- Find pairs of SKUs that appear most frequently in the same
-- order (same customer_id on the same date) to identify
-- cross-sell opportunities.
-- Key columns: sales.customer_id, sales.date, sales.sku_id,
--              skus.sku_id, skus.sku_name, skus.category
-- ------------------------------------------------------------

-- IMPORTANT: The sales table has no order_id column.
-- We define a purchase basket as all products bought by the same customer
-- on the same date. This simplification allows us to analyze which products
-- are frequently purchased together.

WITH
-- 1) Extract distinct basket items.
--    Each row represents one unique product in a customer's daily basket.
--    This de-duplicates rows so pair counts reflect basket frequency,
--    not sale-row frequency.
basket_items AS (
	SELECT
		DISTINCT s.customer_id,
		s.`date`,
		s.sku_id
	FROM sales s
	WHERE s.customer_id IS NOT NULL
	  AND s.`date` IS NOT NULL
	  AND s.sku_id IS NOT NULL
),

-- 2) Self-join basket items to find product pairs.
--    The condition sku_id1 < sku_id2 ensures:
--    - No product pairs itself with itself
--    - No duplicate reversed pairs (A-B and B-A are only counted as A-B)
--    - Each valid pair (e.g., 5-10) is counted exactly once
product_pairs AS (
	SELECT
		b1.sku_id AS product_1_id,
		b2.sku_id AS product_2_id,
		COUNT(DISTINCT b1.customer_id, b1.`date`) AS times_bought_together
	FROM basket_items b1
	JOIN basket_items b2
		ON b1.customer_id = b2.customer_id
		AND b1.`date` = b2.`date`
		AND b1.sku_id < b2.sku_id
	GROUP BY
		b1.sku_id,
		b2.sku_id
),

-- 3) Rank pairs from most to least frequently purchased together.
--    RANK() gives the same rank to ties and skips numbers accordingly.
ranked_pairs AS (
	SELECT
		pp.product_1_id,
		pp.product_2_id,
		pp.times_bought_together,
		RANK() OVER (ORDER BY pp.times_bought_together DESC) AS pair_rank
	FROM product_pairs pp
)

-- 4) Final output: top 20 pairs with product details.
--    Join skus twice to get name and category for both products.
SELECT
	rp.pair_rank,
	rp.product_1_id,
	sk1.sku_name AS product_1_name,
	sk1.category AS product_1_category,
	rp.product_2_id,
	sk2.sku_name AS product_2_name,
	sk2.category AS product_2_category,
	rp.times_bought_together
FROM ranked_pairs rp
JOIN skus sk1
	ON rp.product_1_id = sk1.sku_id
JOIN skus sk2
	ON rp.product_2_id = sk2.sku_id
WHERE rp.pair_rank <= 20
ORDER BY
	rp.pair_rank,
	rp.product_1_id,
	rp.product_2_id;

-- ------------------------------------------------------------
-- Task 4: Year-over-Year Revenue Growth
-- Compare total revenue per month across calendar years to
-- calculate absolute and percentage growth using LAG().
-- Revenue formula: quantity * unit_price * (1 - discount_pct / 100)
-- Key columns: sales.date, sales.quantity, sales.unit_price,
--              sales.discount_pct
-- ------------------------------------------------------------

WITH
-- 1) Calculate total revenue for each calendar year and month.
--    Group by YEAR() and MONTH() to separate years and months.
--    The revenue formula: quantity * unit_price * (1 - discount_pct / 100)
--    treats NULL discount as 0 using COALESCE.
monthly_revenue AS (
	SELECT
		YEAR(s.`date`) AS sales_year,
		MONTH(s.`date`) AS month_number,
		MONTHNAME(s.`date`) AS month_name,
		ROUND(
			SUM(s.quantity * s.unit_price * (1 - COALESCE(s.discount_pct, 0) / 100)),
			2
		) AS current_year_revenue
	FROM sales s
	WHERE s.`date` IS NOT NULL
	GROUP BY
		YEAR(s.`date`),
		MONTH(s.`date`),
		MONTHNAME(s.`date`)
),

-- 2) Use LAG() to retrieve the previous year's revenue for the same month.
--    PARTITION BY month_number ensures we compare January to January,
--    February to February, etc., across different years.
--    ORDER BY sales_year ensures chronological ordering within each month.
revenue_with_lag AS (
	SELECT
		mr.sales_year,
		mr.month_number,
		mr.month_name,
		mr.current_year_revenue,
		LAG(mr.current_year_revenue) OVER (
			PARTITION BY mr.month_number
			ORDER BY mr.sales_year
		) AS previous_year_revenue
	FROM monthly_revenue mr
)

-- 3) Final output with year-over-year growth calculations.
--    absolute_revenue_growth = current_year_revenue - previous_year_revenue
--    yoy_growth_percentage = (growth / previous_year_revenue) * 100
--    NULLIF prevents division by zero; if previous_year_revenue is 0 or NULL, result is NULL.
SELECT
	rwl.sales_year,
	rwl.month_number,
	rwl.month_name,
	rwl.current_year_revenue,
	rwl.previous_year_revenue,
	ROUND(
		rwl.current_year_revenue - rwl.previous_year_revenue,
		2
	) AS absolute_revenue_growth,
	ROUND(
		(rwl.current_year_revenue - rwl.previous_year_revenue) /
		NULLIF(rwl.previous_year_revenue, 0) * 100,
		2
	) AS yoy_growth_percentage
FROM revenue_with_lag rwl
ORDER BY
	rwl.sales_year,
	rwl.month_number;

-- ------------------------------------------------------------
-- Task 5: Running Monthly Revenue Total
-- Compute a cumulative (running) sum of monthly revenue across
-- the full date range using a window function with
-- ORDER BY month and ROWS UNBOUNDED PRECEDING.
-- Revenue formula: quantity * unit_price * (1 - discount_pct / 100)
-- Key columns: sales.date, sales.quantity, sales.unit_price,
--              sales.discount_pct
-- ------------------------------------------------------------

WITH
-- 1) Aggregate revenue by calendar month.
--    Create month_start as the first day of each month.
--    Use the confirmed revenue formula with COALESCE for discount handling.
monthly_aggregation AS (
	SELECT
		DATE(DATE_FORMAT(s.`date`, '%Y-%m-01')) AS month_start,
		YEAR(s.`date`) AS sales_year,
		MONTH(s.`date`) AS month_number,
		MONTHNAME(s.`date`) AS month_name,
		ROUND(
			SUM(s.quantity * s.unit_price * (1 - COALESCE(s.discount_pct, 0) / 100)),
			2
		) AS monthly_revenue
	FROM sales s
	WHERE s.`date` IS NOT NULL
	GROUP BY
		DATE(DATE_FORMAT(s.`date`, '%Y-%m-01')),
		YEAR(s.`date`),
		MONTH(s.`date`),
		MONTHNAME(s.`date`)
),

-- 2) Assign a chronological sequence number to each month.
--    ROW_NUMBER() OVER (ORDER BY month_start) creates month_sequence
--    which starts at 1 for the first month and increments by 1 each month.
--    This demonstrates the ROW_NUMBER() window function.
with_sequence AS (
	SELECT
		ROW_NUMBER() OVER (ORDER BY ma.month_start) AS month_sequence,
		ma.month_start,
		ma.sales_year,
		ma.month_number,
		ma.month_name,
		ma.monthly_revenue
	FROM monthly_aggregation ma
)

-- 3) Final output: calculate cumulative (running) revenue using a window sum.
--    SUM(monthly_revenue) OVER (ORDER BY month_start ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
--    computes the total revenue from the first month up to and including the current month.
--    This running total demonstrates a window function ordered by rows.
SELECT
	ws.month_sequence,
	ws.month_start,
	ws.sales_year,
	ws.month_number,
	ws.month_name,
	ws.monthly_revenue,
	ROUND(
		SUM(ws.monthly_revenue) OVER (
			ORDER BY ws.month_start
			ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
		),
		2
	) AS running_total_revenue
FROM with_sequence ws
ORDER BY ws.month_start;
