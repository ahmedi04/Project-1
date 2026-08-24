#!/usr/bin/env python3
"""
Export Day 2 SQL Query Results to CSV Files

Purpose:
    Execute all queries from day2_aggregations.sql against the retail_db MySQL database
    and export each result set to a separate CSV file in the day2_results/ folder.

Requirements:
    - mysql-connector-python
    - pandas
    - python-dotenv

Usage:
    python3 export_day2_results.py

Output:
    CSV files in day2_results/ folder:
    - day2_query1.csv
    - day2_query2.csv
    - ... (one file per query)
"""

import os
import sys
import re
from pathlib import Path

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("ERROR: mysql-connector-python is not installed.")
    print("Install it with: pip3 install mysql-connector-python")
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
load_dotenv()

# Database configuration from .env
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_USER = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME = "retail_db"
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))

# Output folder for CSV files
OUTPUT_FOLDER = "day2_results"


def create_output_folder():
    """Create the day2_results folder if it does not exist."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"✓ Created folder: {OUTPUT_FOLDER}")
    else:
        print(f"✓ Using existing folder: {OUTPUT_FOLDER}")


def validate_credentials():
    """Validate that required database credentials are available."""
    if not DB_USER or not DB_PASSWORD:
        print("ERROR: Database credentials not found in .env file.")
        print("Please set DB_USER and DB_PASSWORD in .env")
        sys.exit(1)


def read_sql_file(filename="day2_aggregations.sql"):
    """
    Read SQL file and extract individual queries.
    
    Query Format Expected:
    - Each query is identified by: -- Query N: Description
    - Queries may be numbered 1-10 (not necessarily consecutive)
    - Comment markers can appear anywhere (start of line, end of line, same line as semicolon)
    - CTEs (WITH ... SELECT) are captured as a complete query
    - Setup statements (USE, SHOW TABLES, DESCRIBE) are ignored
    - Special case: Query 8 may have no comment marker (extracted as orphaned SELECT/WITH)
    
    Args:
        filename: Path to SQL file containing exactly 10 queries
        
    Returns:
        Dictionary with query_number as key and SQL string as value
        
    Raises:
        SystemExit: If file not found, queries not found, or count != 10
    """
    if not os.path.exists(filename):
        print(f"ERROR: SQL file not found: {filename}")
        sys.exit(1)
    
    with open(filename, "r") as f:
        content = f.read()
    
    queries = {}
    
    # Step 1: Find all -- Query N: markers and their positions
    # This handles markers anywhere in the line (start, middle, end)
    query_markers = {}
    for match in re.finditer(r"-- Query (\d+):", content):
        query_num = int(match.group(1))
        query_markers[query_num] = match.start()
    
    # Step 2: Extract text for each marked query
    sorted_queries = sorted(query_markers.keys())
    for i, query_num in enumerate(sorted_queries):
        start_pos = query_markers[query_num]
        
        # Find end position: start of next query marker OR end of file
        if i < len(sorted_queries) - 1:
            end_pos = query_markers[sorted_queries[i + 1]]
        else:
            end_pos = len(content)
        
        # Extract text starting after the comment marker
        # Find the end of the comment line
        comment_end = content.find("\n", start_pos)
        if comment_end == -1:
            comment_end = start_pos
        
        # Extract from after the comment line to next marker/end
        sql_text = content[comment_end + 1:end_pos].strip()
        sql_text = sql_text.rstrip("; \n\t")
        
        # Skip empty or setup statement queries
        if sql_text and not re.match(r"^\s*(USE|SHOW|DESCRIBE)", sql_text, re.IGNORECASE):
            queries[query_num] = sql_text
    
    # Step 3: Handle Query 8 if missing (orphaned SQL between Query 7 and 9)
    # Query 8 might not have a -- Query 8: marker
    if 7 in queries and 9 in queries and 8 not in queries:
        # Find the position after Query 7 marker and before Query 9 marker
        query_7_pos = query_markers.get(7)
        query_9_pos = query_markers.get(9)
        
        if query_7_pos and query_9_pos:
            # Move past Query 7's comment line
            after_query_7_comment = content.find("\n", query_7_pos) + 1
            
            # Find the next query marker position after Query 7
            # (This would be the Query 9 marker)
            between_text = content[after_query_7_comment:query_9_pos]
            
            # Extract the last statement before Query 9 (Query 8)
            # It could be after the previous query's semicolon
            sql_text = between_text.strip()
            sql_text = sql_text.rstrip("; \n\t")
            
            if sql_text and not re.match(r"^\s*(USE|SHOW|DESCRIBE)", sql_text, re.IGNORECASE):
                queries[8] = sql_text
    
    # Step 4: Validate exactly 10 queries
    if not queries:
        print("ERROR: No SQL queries found in SQL file.")
        print(f"File: {filename}")
        print("Ensure queries are formatted as: -- Query 1: Description")
        sys.exit(1)
    
    query_count = len(queries)
    print(f"Found {query_count} queries: {sorted(queries.keys())}")
    
    if query_count != 10:
        print(f"ERROR: Expected exactly 10 queries, but found {query_count}")
        print(f"File: {filename}")
        print(f"Found query numbers: {sorted(queries.keys())}")
        sys.exit(1)
    
    return queries


def connect_to_database():
    """
    Establish connection to MySQL database.
    
    Returns:
        MySQL connection object
    """
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print(f"✓ Connected to {DB_NAME} at {DB_HOST}:{DB_PORT}")
        return connection
    except Error as e:
        print(f"ERROR: Failed to connect to database: {e}")
        sys.exit(1)


def execute_query(connection, query_num, sql_text):
    """
    Execute a single SQL query and return results as a pandas DataFrame.
    Reconnects to database if connection is lost.
    
    Args:
        connection: MySQL connection object (may be reconnected)
        query_num: Query number (for logging)
        sql_text: SQL query text
        
    Returns:
        Tuple of (connection, DataFrame) where DataFrame is query results or None if fails
    """
    try:
        # Check if connection is still alive
        if not connection.is_connected():
            print(f"  ⚠ Reconnecting to database (connection lost)...")
            connection = connect_to_database()
        
        df = pd.read_sql(sql_text, connection)
        print(f"  ✓ Query {query_num}: {len(df)} rows retrieved")
        return connection, df
    except Exception as e:
        print(f"  ✗ Query {query_num} FAILED: {e}")
        # Try to reconnect for next query
        try:
            connection.close()
        except:
            pass
        return connection, None


def export_query_result(query_num, df):
    """
    Export query result DataFrame to CSV file.
    
    Args:
        query_num: Query number (for filename)
        df: pandas DataFrame to export
        
    Returns:
        True if successful, False otherwise
    """
    if df is None or df.empty:
        print(f"  ✗ Skipping empty result for Query {query_num}")
        return False
    
    filename = os.path.join(OUTPUT_FOLDER, f"day2_query{query_num}.csv")
    try:
        df.to_csv(filename, index=False)
        print(f"  ✓ Exported to: {filename}")
        return True
    except Exception as e:
        print(f"  ✗ Export FAILED for Query {query_num}: {e}")
        return False


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Day 2 Query Results Exporter")
    print("=" * 60)
    print()
    
    # Validate setup
    print("1. Validating credentials...")
    validate_credentials()
    print()
    
    # Create output folder
    print("2. Setting up output folder...")
    create_output_folder()
    print()
    
    # Read SQL file
    print("3. Reading SQL queries from day2_aggregations.sql...")
    queries = read_sql_file()
    print(f"✓ Found {len(queries)} queries (expected 10)")
    
    # Verify exactly 10 queries
    if len(queries) != 10:
        print(f"ERROR: Expected exactly 10 queries, found {len(queries)}")
        print(f"Query numbers found: {sorted(queries.keys())}")
        sys.exit(1)
    
    print(f"✓ Query validation passed")
    print(f"✓ Will create files: day2_query1.csv through day2_query10.csv")
    print()
    
    # Connect to database
    print("4. Connecting to database...")
    connection = connect_to_database()
    print()
    
    # Execute queries and export results
    print("5. Executing queries and exporting results...")
    success_count = 0
    failed_count = 0
    
    for query_num in sorted(queries.keys()):
        sql_text = queries[query_num]
        print(f"\nProcessing Query {query_num}...")
        
        # Execute query (may reconnect internally if needed)
        connection, df = execute_query(connection, query_num, sql_text)
        
        # Export to CSV if successful
        if df is not None and not df.empty:
            if export_query_result(query_num, df):
                success_count += 1
        else:
            failed_count += 1
    
    # Close database connection
    try:
        connection.close()
    except:
        pass
    print()
    
    # Summary
    print("=" * 60)
    total_queries = len(queries)
    if success_count == total_queries:
        print(f"✓ SUCCESS: {success_count}/{total_queries} queries exported")
    else:
        print(f"✗ INCOMPLETE: {success_count}/{total_queries} queries exported successfully")
        if failed_count > 0:
            print(f"  {failed_count} queries failed")
    print(f"Results saved to: {os.path.abspath(OUTPUT_FOLDER)}/")
    print("=" * 60)
    
    if success_count < total_queries:
        sys.exit(1)


if __name__ == "__main__":
    main()
