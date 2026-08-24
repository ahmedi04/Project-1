USE retail_db;
SHOW TABLES;
DESCRIBE sales;
DESCRIBE stores;
DESCRIBE skus;
DESCRIBE customers;

-- Query 1: Revenue by city and store type
SELECT 
    st.city,
    st.store_type,
    ROUND(
        SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
        2
    ) AS revenue
FROM sales s
JOIN stores st
    ON s.store_id = st.store_id
GROUP BY 
    st.city,
    st.store_type
ORDER BY 
    revenue DESC;
    -- Query 2: Top 5 product categories by revenue

SELECT
    sk.category,
    ROUND(
        SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
        2
    ) AS revenue
FROM sales s
JOIN skus sk
    ON s.sku_id = sk.sku_id
GROUP BY
    sk.category
ORDER BY
  revenue DESC
LIMIT 5;
    -- Query 3: Customer Spend Tiers (High, Medium, Low)
-- Uses a CTE to calculate total spend per customer once,
-- then assigns tiers using NTILE(3) for equal distribution.

WITH customer_spend AS (
    SELECT
        s.customer_id,
        ROUND(
            SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
            2
        ) AS total_spend
    FROM sales s
    WHERE s.customer_id IS NOT NULL
    GROUP BY s.customer_id
)
SELECT
    customer_id,
    total_spend,
    CASE
        WHEN NTILE(3) OVER (ORDER BY total_spend DESC) = 1 THEN 'High'
        WHEN NTILE(3) OVER (ORDER BY total_spend DESC) = 2 THEN 'Medium'
        ELSE 'Low'
    END AS spend_tier
FROM customer_spend
ORDER BY total_spend DESC;

-- Query 4: Promotion Impact on Sales
--
-- Join Logic (Revised):
-- Uses EXISTS to avoid double-counting from overlapping promotion periods.
-- - EXISTS checks if a sale date falls within ANY promotion date range
-- - If EXISTS returns TRUE for at least one promotion, sale is "During Promotion"
-- - If EXISTS returns FALSE (no matching promotions), sale is "Outside Promotion"
-- - Each sale is classified exactly once, eliminating duplicate rows from overlapping promos
--
-- Promotion Period Identification:
-- A sale is "During Promotion" if its date falls within [start_date, end_date] of at least one promotion.
-- A sale is "Outside Promotion" if its date does not overlap with any promotion period.

WITH sales_with_promo_flag AS (
    SELECT
        s.`date`,
        s.quantity,
        s.unit_price,
        s.discount_pct,
        ROUND(s.quantity * s.unit_price * (1 - s.discount_pct / 100), 2) AS revenue,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM promotions p
                WHERE s.`date` >= p.start_date
                  AND s.`date` <= p.end_date
            ) THEN 'During Promotion'
            ELSE 'Outside Promotion'
        END AS period_type
    FROM sales s
)
SELECT
    period_type,
    COUNT(*) AS transaction_count,
    ROUND(SUM(revenue), 2) AS total_revenue,
    ROUND(AVG(revenue), 2) AS avg_revenue_per_transaction,
    ROUND(AVG(quantity), 2) AS avg_quantity_per_transaction
FROM sales_with_promo_flag
GROUP BY period_type
ORDER BY CASE WHEN period_type = 'During Promotion' THEN 1 ELSE 2 END;

-- Query 5: Customers Above Average Spending
--
-- Approach:
-- 1. CTE customer_spend: Calculate total spend per customer using revenue formula
-- 2. CTE avg_spend: Calculate the average total spend across all customers
-- 3. Main query: Use CROSS JOIN to compare each customer's total against the average
-- 4. Filter: WHERE total_spend > avg_total_spend
-- 5. Result: Only customers whose lifetime spending exceeds the average
--
-- This identifies high-value customers for targeting and retention strategies.

WITH customer_spend AS (
    SELECT
        s.customer_id,
        ROUND(
            SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
            2
        ) AS total_spend
    FROM sales s
    WHERE s.customer_id IS NOT NULL
    GROUP BY s.customer_id
),
avg_spend AS (
    SELECT AVG(total_spend) AS avg_total_spend
    FROM customer_spend
)
SELECT
    cs.customer_id,
    cs.total_spend
FROM customer_spend cs
CROSS JOIN avg_spend a
WHERE cs.total_spend > a.avg_total_spend
ORDER BY cs.total_spend DESC;

-- Query 6: Products with Falling Sales Month Over Month
--
-- Logic:
-- 1. Compute monthly revenue per SKU: quantity * unit_price * (1 - discount_pct / 100)
-- 2. Use LAG() to access the previous month's revenue for the same SKU
-- 3. Only compare when the previous record is exactly one calendar month earlier
-- 4. Return rows where revenue fell compared with the immediately previous month

WITH monthly_sku_revenue AS (
    SELECT
        s.sku_id,
        sk.sku_name,
        DATE_FORMAT(s.`date`, '%Y-%m') AS month,
        DATE_FORMAT(s.`date`, '%Y-%m-01') AS month_start,
        ROUND(
            SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
            2
        ) AS current_month_revenue
    FROM sales s
    JOIN skus sk
        ON s.sku_id = sk.sku_id
    GROUP BY
        s.sku_id,
        sk.sku_name,
        DATE_FORMAT(s.`date`, '%Y-%m'),
        DATE_FORMAT(s.`date`, '%Y-%m-01')
),
monthly_comparison AS (
    SELECT
        sku_id,
        sku_name,
        month,
        month_start,
        current_month_revenue,
        LAG(current_month_revenue) OVER (
            PARTITION BY sku_id
            ORDER BY month_start
        ) AS previous_month_revenue,
        LAG(month_start) OVER (
            PARTITION BY sku_id
            ORDER BY month_start
        ) AS previous_month_start
    FROM monthly_sku_revenue
)
SELECT
    sku_id,
    sku_name,
    month,
    current_month_revenue,
    previous_month_revenue,
    ROUND(current_month_revenue - previous_month_revenue, 2) AS revenue_change
FROM monthly_comparison
WHERE previous_month_revenue IS NOT NULL
  AND DATE_ADD(previous_month_start, INTERVAL 1 MONTH) = month_start
  AND current_month_revenue < previous_month_revenue
ORDER BY revenue_change ASC;

-- Query 7: Rank Stores Within Each City by Revenue
--
-- Purpose:
-- Rank stores relative to other stores in the same city based on total revenue.
-- Highest revenue store in each city gets rank 1.

WITH store_revenue AS (
    SELECT
        st.city,
        st.store_id,
        st.store_name,
        ROUND(
            SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
            2
        ) AS total_revenue
    FROM sales s
    JOIN stores st
        ON s.store_id = st.store_id
    GROUP BY
        st.city,
        st.store_id,
        st.store_name
)
SELECT
    city,
    store_id,
    store_name,
    total_revenue,
    RANK() OVER (
        PARTITION BY city
        ORDER BY total_revenue DESC
    ) AS store_rank
FROM store_revenue
ORDER BY city, store_rank, total_revenue DESC;
SELECT 'NULL customer_id' AS issue_type, COUNT(*) AS issue_count
FROM sales
WHERE customer_id IS NULL

UNION ALL

SELECT 'NULL date', COUNT(*)
FROM sales
WHERE `date` IS NULL

UNION ALL

SELECT 'NULL store_id', COUNT(*)
FROM sales
WHERE store_id IS NULL

UNION ALL

SELECT 'NULL sku_id', COUNT(*)
FROM sales
WHERE sku_id IS NULL

UNION ALL

SELECT 'NULL quantity', COUNT(*)
FROM sales
WHERE quantity IS NULL

UNION ALL

SELECT 'NULL unit_price', COUNT(*)
FROM sales
WHERE unit_price IS NULL

UNION ALL

SELECT 'NULL discount_pct', COUNT(*)
FROM sales
WHERE discount_pct IS NULL

UNION ALL

SELECT 'NULL total_value', COUNT(*)
FROM sales
WHERE total_value IS NULL

UNION ALL

SELECT 'NULL channel', COUNT(*)
FROM sales
WHERE channel IS NULL

UNION ALL

SELECT 'quantity <= 0', COUNT(*)
FROM sales
WHERE quantity IS NOT NULL
  AND quantity <= 0

UNION ALL

SELECT 'unit_price <= 0', COUNT(*)
FROM sales
WHERE unit_price IS NOT NULL
  AND unit_price <= 0

UNION ALL

SELECT 'discount_pct outside 0-100', COUNT(*)
FROM sales
WHERE discount_pct IS NOT NULL
  AND (discount_pct < 0 OR discount_pct > 100)

UNION ALL

SELECT 'negative total_value', COUNT(*)
FROM sales
WHERE total_value IS NOT NULL
  AND total_value < 0

ORDER BY issue_count DESC;
-- Query 9: Repeat Purchase Rate

WITH customer_purchase_counts AS (
    SELECT
        customer_id,
        COUNT(*) AS purchase_count
    FROM sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
customer_summary AS (
    SELECT
        COUNT(*) AS total_customers,
        SUM(CASE WHEN purchase_count > 1 THEN 1 ELSE 0 END) AS repeat_customers
    FROM customer_purchase_counts
)
SELECT
    total_customers,
    repeat_customers,
    ROUND(
        repeat_customers * 100.0 / total_customers,
        2
    ) AS repeat_purchase_rate_pct
FROM customer_summary;
-- Query 10: Category Mix for Each City

WITH category_revenue AS (
    SELECT
        st.city,
        sk.category,
        ROUND(
            SUM(s.quantity * s.unit_price * (1 - s.discount_pct / 100)),
            2
        ) AS category_revenue
    FROM sales s
    JOIN stores st
        ON s.store_id = st.store_id
    JOIN skus sk
        ON s.sku_id = sk.sku_id
    GROUP BY
        st.city,
        sk.category
),
city_revenue AS (
    SELECT
        city,
        SUM(category_revenue) AS city_total_revenue
    FROM category_revenue
    GROUP BY city
)
SELECT
    cr.city,
    cr.category,
    cr.category_revenue,
    ROUND(ct.city_total_revenue, 2) AS city_total_revenue,
    ROUND(
        (cr.category_revenue / ct.city_total_revenue) * 100,
        2
    ) AS category_mix_pct
FROM category_revenue cr
JOIN city_revenue ct
    ON cr.city = ct.city
ORDER BY
    cr.city,
    category_mix_pct DESC;