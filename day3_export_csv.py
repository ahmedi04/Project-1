#!/usr/bin/env python3
"""
Export Day 3 Advanced Analytics Results to CSV Files

Purpose:
    Execute Day 3 advanced analytics queries from day3_advanced_analytics.sql
    against the retail_db MySQL database and export:
    - RFM segment-level summary (aggregated customer counts and metrics by segment)
    - Cohort retention rates (customer retention by signup cohort and activity month)

These queries use CTEs and window functions (NTILE, LAG, ROW_NUMBER, SUM OVER)
to provide actionable business insights on customer value and retention.

Requirements:
    - sqlalchemy
    - pymysql
    - pandas
    - python-dotenv

Usage:
    python3 day3_export_csv.py

Output:
    CSV files in the current project folder:
    - rfm_segment_summary.csv (RFM aggregation by customer segment)
    - cohort_retention.csv (retention rates by cohort and activity month)
"""

import os
import sys
from pathlib import Path

# Import required modules with graceful error handling
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL
except ImportError:
    print("ERROR: sqlalchemy is not installed.")
    print("Install it with: pip3 install sqlalchemy")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is not installed.")
    print("Install it with: pip3 install pandas")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv is not installed.")
    print("Install it with: pip3 install python-dotenv")
    sys.exit(1)


# Load environment variables from .env file
# dotenv will search for .env in the current directory and parent directories.
# All environment variables are loaded into os.environ.
load_dotenv()

# Read database credentials from environment variables.
# These should be set in the .env file:
#   MYSQL_HOST=localhost
#   MYSQL_PORT=3306
#   MYSQL_USER=<username>
#   MYSQL_PASSWORD=<password>
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = "retail_db"


def validate_credentials():
    """
    Validate that all required database credentials are present.
    
    Raises:
        SystemExit if any required credential is missing.
    """
    missing = []
    if not DB_USER:
        missing.append("MYSQL_USER")
    if not DB_PASSWORD:
        missing.append("MYSQL_PASSWORD")
    
    if missing:
        print("ERROR: Missing required environment variables:")
        for var_name in missing:
            print(f"  - {var_name}")
        print("\nPlease set these in your .env file:")
        print("  MYSQL_USER=<your_username>")
        print("  MYSQL_PASSWORD=<your_password>")
        sys.exit(1)


def build_engine():
    """
    Build a SQLAlchemy engine using URL.create() for safe connection string construction.
    
    URL.create() ensures that special characters in passwords are properly escaped,
    preventing SQL injection and connection errors.
    
    Uses mysql+pymysql driver for better compatibility across systems.
    
    Returns:
        SQLAlchemy Engine connected to retail_db
    """
    connection_url = URL.create(
        drivername="mysql+pymysql",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )
    engine = create_engine(connection_url)
    return engine


def test_connection(engine):
    """
    Verify the engine can open a connection to the database.
    
    Args:
        engine: SQLAlchemy Engine
        
    Raises:
        SystemExit if connection fails
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✓ Connected to {DB_NAME}")
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        sys.exit(1)


def export_rfm_segment_summary(engine):
    """
    Execute the RFM customer segmentation query and export a segment-level summary.
    
    The summary aggregates individual customer RFM scores by customer_segment,
    providing count, averages, and totals per segment.
    
    This reuses the exact RFM logic from Task 1 (day3_advanced_analytics.sql),
    but aggregates at the segment level instead of per-customer.
    
    Returns:
        DataFrame with columns: customer_segment, customer_count, 
        average_recency_days, average_frequency, average_monetary, total_monetary
    """
    query = """
    WITH
    max_sales_anchor AS (
        SELECT DATE_ADD(MAX(s.`date`), INTERVAL 1 DAY) AS anchor_date
        FROM sales s
    ),
    customer_rfm_base AS (
        SELECT
            c.cust_id AS customer_id,
            MAX(s.`date`) AS last_purchase_date,
            COALESCE(
                DATEDIFF(a.anchor_date, MAX(s.`date`)),
                99999
            ) AS recency_days,
            COALESCE(COUNT(DISTINCT s.`date`), 0) AS frequency,
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
    rfm_scored AS (
        SELECT
            b.customer_id,
            b.last_purchase_date,
            b.recency_days,
            b.frequency,
            b.monetary,
            5 - NTILE(4) OVER (ORDER BY b.recency_days ASC) AS r_score,
            NTILE(4) OVER (ORDER BY b.frequency ASC) AS f_score,
            NTILE(4) OVER (ORDER BY b.monetary ASC) AS m_score
        FROM customer_rfm_base b
    ),
    rfm_with_segment AS (
        SELECT
            customer_id,
            recency_days,
            frequency,
            monetary,
            CASE
                WHEN last_purchase_date IS NULL THEN 'Lost'
                WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
                WHEN r_score >= 2 AND f_score >= 3 AND m_score >= 2 THEN 'Loyal'
                WHEN r_score <= 2 AND (f_score >= 3 OR m_score >= 3) THEN 'At Risk'
                ELSE 'Lost'
            END AS customer_segment
        FROM rfm_scored
    )
    SELECT
        customer_segment,
        COUNT(*) AS customer_count,
        ROUND(AVG(recency_days), 2) AS average_recency_days,
        ROUND(AVG(frequency), 2) AS average_frequency,
        ROUND(AVG(monetary), 2) AS average_monetary,
        ROUND(SUM(monetary), 2) AS total_monetary
    FROM rfm_with_segment
    GROUP BY customer_segment
    ORDER BY customer_count DESC
    """
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        print(f"✓ RFM segment summary: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        print(f"ERROR: Failed to execute RFM segment summary query: {e}")
        sys.exit(1)


def export_cohort_retention(engine):
    """
    Execute the cohort retention query and export results.
    
    The cohort retention analysis tracks which customers from each signup cohort
    make purchases in subsequent months, calculating retention rates.
    
    This reuses the exact cohort logic from Task 2 (day3_advanced_analytics.sql),
    providing the full cohort-month-level retention insights.
    
    Returns:
        DataFrame with columns: cohort_month, activity_month, month_number,
        cohort_size, retained_customers, retention_rate
    """
    query = """
    WITH
    customer_cohorts AS (
        SELECT
            c.cust_id AS customer_id,
            DATE(DATE_FORMAT(c.registration_date, '%Y-%m-01')) AS cohort_month
        FROM customers c
        WHERE c.registration_date IS NOT NULL
    ),
    cohort_sizes AS (
        SELECT
            cc.cohort_month,
            COUNT(*) AS cohort_size
        FROM customer_cohorts cc
        GROUP BY cc.cohort_month
    ),
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
        cr.month_number
    """
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        print(f"✓ Cohort retention: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        print(f"ERROR: Failed to execute cohort retention query: {e}")
        sys.exit(1)


def save_csv(df, filename, output_dir):
    """
    Export a DataFrame to CSV without the pandas index.
    
    Args:
        df: pandas DataFrame to export
        filename: target CSV filename (without path)
        output_dir: parent directory Path object
        
    Raises:
        SystemExit if export fails
    """
    filepath = output_dir / filename
    try:
        df.to_csv(filepath, index=False)
        print(f"✓ Exported: {filename}")
    except Exception as e:
        print(f"ERROR: Failed to export {filename}: {e}")
        sys.exit(1)


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Day 3 Advanced Analytics CSV Export")
    print("=" * 60)
    print()
    
    # Determine output directory for CSV files
    output_dir = Path(__file__).resolve().parent
    
    # Step 1: Validate environment variables
    print("1. Validating credentials...")
    validate_credentials()
    print()
    
    # Step 2: Build SQLAlchemy engine
    print("2. Building database engine...")
    engine = build_engine()
    print()
    
    # Step 3: Initialize tracking variables
    rfm_df = None
    cohort_df = None
    
    try:
        # Step 4: Test connection
        print("3. Testing connection...")
        test_connection(engine)
        print()
        
        # Step 5: Export RFM segment summary
        print("4. Exporting RFM segment summary...")
        rfm_df = export_rfm_segment_summary(engine)
        save_csv(rfm_df, "rfm_segment_summary.csv", output_dir)
        print()
        
        # Step 6: Export cohort retention
        print("5. Exporting cohort retention...")
        cohort_df = export_cohort_retention(engine)
        save_csv(cohort_df, "cohort_retention.csv", output_dir)
        print()
        
        # Summary
        print("=" * 60)
        print("✓ SUCCESS: All Day 3 deliverables exported")
        print(f"  - rfm_segment_summary.csv ({len(rfm_df)} rows, {len(rfm_df.columns)} columns)")
        print(f"  - cohort_retention.csv ({len(cohort_df)} rows, {len(cohort_df.columns)} columns)")
        print("=" * 60)
    
    finally:
        # Always dispose of engine, even if an error occurs
        try:
            engine.dispose()
        except Exception:
            pass


if __name__ == "__main__":
    main()
