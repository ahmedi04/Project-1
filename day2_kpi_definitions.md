# Day 2 KPI Definitions

## 1. Revenue

**Formula:** `quantity × unit_price × (1 - discount_pct / 100)`

Total monetary value of sales after applying discounts. The core metric for business performance across all queries.

---

## 2. AOV (Average Order Value)

**Formula:** `Total Revenue / Number of Orders`

**Note:** This dataset has no order_id column. Each sales row is treated as a transaction/order. Exact AOV requires grouping by transaction-level identifiers if multiple rows represent a single order.

Average monetary value per order. Useful for understanding customer spending patterns and transaction size.

---

## 3. Units Sold

**Formula:** `SUM(quantity)`

Total number of units sold across all transactions. Tracks volume of sales independent of price.

---

## 4. Discount Rate

**Formula:** `Total Discount Amount / Total Revenue`

Percentage share of revenue represented by discounts. Helps assess promotional intensity and price optimization strategy.

---

## 5. Repeat Purchase Rate

**Formula:** `(Repeat Customers / Total Identified Customers) × 100`

Percentage of non-NULL customers with more than one purchase. Measures customer retention and loyalty.

---

## 6. Category Mix %

**Formula:** `(Category Revenue / City Total Revenue) × 100`

Percentage of city revenue contributed by each product category. Shows which categories drive sales in each location.

---

## 7. Average Revenue per Transaction

**Formula:** `Total Revenue / Number of Transactions`

Average revenue value per sales transaction. Indicates transaction scale and customer purchase size.

---

## 8. Customer Spend

**Formula:** `SUM(discounted revenue per customer)`

Where discounted revenue = `quantity × unit_price × (1 - discount_pct / 100)`

Total lifetime spend per customer after discounts. Used to segment customers into spending tiers (High/Medium/Low).

---

**Data Quality Note:** The sales table contains 159,821 NULL customer_id rows, representing guest/anonymous purchases. These are excluded from customer-level calculations.
