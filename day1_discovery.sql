USE retail_db;

-- 1) 3 SELECT + WHERE
-- Query 1: Find Gold loyalty customers in Dubai
SELECT *
FROM customers
WHERE city = 'Dubai' AND loyalty_segment = 'Gold'
LIMIT 10;
-- Query 2: Find Electronics products priced above 100
SELECT *
FROM skus
WHERE category = 'Electronics' AND unit_price > 100
ORDER BY unit_price DESC;
-- Query 3: Find MobileApp sales with quantity 3 or more
SELECT *
FROM sales
WHERE channel = 'MobileApp' AND quantity >= 3
ORDER BY total_value DESC
LIMIT 20;

-- 2) 3 INNER JOIN with 2 tables
-- Query 4: Join sales with store details for January 1, 2021
SELECT s.`date`, st.store_name, s.total_value
FROM sales s
INNER JOIN stores st ON s.store_id = st.store_id
WHERE s.`date` = '2021-01-01';
-- Query 5: Join Website sales with product details
SELECT s.sku_id, sk.sku_name, s.total_value
FROM sales s
INNER JOIN skus sk ON s.sku_id = sk.sku_id
WHERE s.channel = 'Website';
-- Query 6: Join Gold customer sales with customer details
SELECT c.cust_id, c.city, s.total_value
FROM sales s
INNER JOIN customers c ON s.customer_id = c.cust_id
WHERE c.loyalty_segment = 'Gold';

-- 3) 3 joins with 3 or more tables
-- Query 7: Join sales, stores, and customers to find revenue by store and customer city
SELECT st.store_name, c.city, SUM(s.total_value) AS revenue
FROM sales s
INNER JOIN stores st ON s.store_id = st.store_id
INNER JOIN customers c ON s.customer_id = c.cust_id
GROUP BY st.store_name, c.city
ORDER BY revenue DESC
LIMIT 10;
-- Query 8: Join sales, products, and stores to find units sold by category and city
SELECT sk.category, st.city, SUM(s.quantity) AS units_sold
FROM sales s
INNER JOIN skus sk ON s.sku_id = sk.sku_id
INNER JOIN stores st ON s.store_id = st.store_id
WHERE s.`date` BETWEEN '2021-01-01' AND '2021-01-31'
GROUP BY sk.category, st.city
ORDER BY units_sold DESC;
-- Query 9: Join sales, customers, and products to find average unit price by city and categorySELECT c.city, sk.category, AVG(s.unit_price) AS avg_unit_price
FROM sales s
INNER JOIN customers c ON s.customer_id = c.cust_id
INNER JOIN skus sk ON s.sku_id = sk.sku_id
WHERE s.channel = 'Store'
GROUP BY c.city, sk.category
ORDER BY avg_unit_price DESC
LIMIT 20;

-- 4) 3 LEFT JOIN
-- Query 10: Show Dubai customers with their sales using LEFT JOIN
SELECT c.cust_id, c.city, s.`date`, s.total_value
FROM customers c
LEFT JOIN sales s ON c.cust_id = s.customer_id
WHERE c.city = 'Dubai'
ORDER BY s.`date` DESC
LIMIT 20;
-- Query 11: Show Dubai stores with their inventory using LEFT JOIN
SELECT st.store_id, st.store_name, i.sku_id, i.stock_on_hand
FROM stores st
LEFT JOIN inventory i ON st.store_id = i.store_id
WHERE st.city = 'Dubai'
ORDER BY st.store_id, i.sku_id;
-- Query 12: Show Electronics products with their sales using LEFT JOIN
SELECT sk.sku_id, sk.sku_name, s.`date`, s.quantity
FROM skus sk
LEFT JOIN sales s ON sk.sku_id = s.sku_id
WHERE sk.category = 'Electronics'
ORDER BY sk.sku_id, s.`date`
LIMIT 30;

-- 5) 3 ORDER BY + LIMIT
-- Query 13: Find the 10 oldest customers
SELECT *
FROM customers
ORDER BY age DESC
LIMIT 10;
-- Query 14: Find the 10 most expensive products
SELECT *
FROM skus
ORDER BY unit_price DESC
LIMIT 10;
-- Query 15: Find the top 10 highest-value sales
SELECT *
FROM sales
ORDER BY total_value DESC
LIMIT 10;
