#!/usr/bin/env python3
"""
Export Day 1 SQL Query Results to CSV Files

Purpose:
    Execute all queries from day1_discovery.sql against the retail_db MySQL database
    and export each result set to a separate CSV file in the day1_results/ folder.

Requirements:
    - sqlalchemy
    - mysql-connector-python
    - pandas
    - python-dotenv

Usage:
    python3 export_day1_results.py

Output:
    CSV files in day1_results/ folder:
    - day1_query1.csv
    - day1_query2.csv
    - ... (one file per query)
"""

import os
import sys
import re

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL
    from sqlalchemy.pool import NullPool
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
load_dotenv()

# Database configuration from .env
DB_HOST     = os.getenv("MYSQL_HOST", "localhost")
DB_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER     = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME     = "retail_db"

# Output folder for CSV files
OUTPUT_FOLDER = "day1_results"


def create_output_folder():
    """Create the day1_results folder if it does not exist."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f"✓ Created folder: {OUTPUT_FOLDER}")
    else:
        print(f"✓ Using existing folder: {OUTPUT_FOLDER}")


def validate_credentials():
    """Validate that required database credentials are present."""
    if not DB_USER or not DB_PASSWORD:
        print("ERROR: Database credentials not found in .env file.")
        print("Please set MYSQL_USER and MYSQL_PASSWORD in .env")
        sys.exit(1)


def build_engine():
    """
    Build a SQLAlchemy engine using URL.create() for safe URL construction.

    Returns:
        SQLAlchemy Engine
    """
    connection_url = URL.create(
        drivername="mysql+mysqlconnector",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )
    # NullPool: every engine.connect() opens a brand-new physical connection
    # and closes it completely on exit — prevents "Commands out of sync" errors
    # that occur when mysql-connector reuses a connection with pending result state.
    engine = create_engine(connection_url, poolclass=NullPool)
    return engine


def test_connection(engine):
    """Verify the engine can open a connection."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✓ Connected to {DB_NAME} at {DB_HOST}:{DB_PORT}")
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        sys.exit(1)


def read_sql_file(filename="day1_discovery.sql"):
    """
    Read SQL file and extract individual executable queries.

    Rules:
    - Queries are identified by: -- Query N: <description>
    - The comment marker may appear at the start of a line OR directly
      concatenated with the SQL on the same line (e.g. -- Query 9: ...SELECT)
    - Setup / meta statements (USE, SHOW TABLES, DESCRIBE) are ignored.
    - Each extracted query has its trailing semicolons stripped.

    Args:
        filename: Path to the SQL file to parse

    Returns:
        dict mapping query_number (int) -> SQL string
    """
    if not os.path.exists(filename):
        print(f"ERROR: SQL file not found: {filename}")
        sys.exit(1)

    with open(filename, "r") as f:
        content = f.read()

    queries = {}

    # Locate every -- Query N: marker and its position in the file
    marker_pattern = re.compile(r"-- Query (\d+):\s*[^\n]*", re.IGNORECASE)
    markers = [(int(m.group(1)), m.start(), m.end()) for m in marker_pattern.finditer(content)]

    if not markers:
        print("ERROR: No '-- Query N:' markers found in the SQL file.")
        sys.exit(1)

    for i, (query_num, start_pos, marker_end) in enumerate(markers):
        # The SQL ends at the start of the next marker, or end of file
        sql_end = markers[i + 1][1] if i + 1 < len(markers) else len(content)

        # Check if a SQL keyword is embedded directly in the comment line
        # e.g. "-- Query 9: ...categorySELECT c.city" (no newline before SELECT)
        comment_line_end = content.find("\n", start_pos)
        if comment_line_end == -1:
            comment_line_end = marker_end
        comment_line = content[start_pos:comment_line_end]
        # Only match a SQL keyword that is directly glued to the preceding
        # description text, e.g. "...categorySELECT".  Using (?<=[a-zA-Z])
        # (preceded by a letter) catches the glued case while ignoring
        # "sales with quantity" where "with" follows a space.
        inline_sql = re.search(r'(?<=[a-zA-Z])(SELECT|WITH)\b', comment_line, re.IGNORECASE)
        if inline_sql:
            # SQL starts inside the comment line itself (attached to description)
            sql_start = start_pos + inline_sql.start()
        else:
            # SQL starts on the line after the comment marker
            sql_start = marker_end

        sql_text = content[sql_start:sql_end].strip()

        # If the SQL ends with a semicolon followed only by whitespace and/or
        # comment lines (section headers like "-- 2) 3 INNER JOIN..."), strip
        # everything from that semicolon onwards.  Leaving those comments in
        # makes mysql-connector send a phantom second statement to MySQL which
        # keeps the connection in "Commands out of sync" state.
        last_semi = sql_text.rfind(";")
        if last_semi != -1:
            trailing = sql_text[last_semi + 1:].strip()
            # Remove comment lines from the trailing text; if nothing real remains,
            # the semicolon (and comments) are safe to drop.
            trailing_code = re.sub(r"--[^\n]*", "", trailing).strip()
            if not trailing_code:
                sql_text = sql_text[:last_semi].strip()

        # Final strip of any remaining trailing semicolons/whitespace
        sql_text = re.sub(r"[;\s]+$", "", sql_text)

        # Skip setup / meta statements
        if not sql_text:
            continue
        first_keyword = sql_text.split()[0].upper() if sql_text.split() else ""
        if first_keyword in ("USE", "SHOW", "DESCRIBE", "DESC"):
            continue

        queries[query_num] = sql_text

    return queries


def execute_and_export(engine, query_num, sql_text):
    """
    Execute one SQL query via SQLAlchemy and export results to CSV.
    Uses NullPool (set on engine) so the physical connection is fully closed
    after each query — no stale result state can bleed into the next query.

    Args:
        engine:     SQLAlchemy Engine (must use NullPool)
        query_num:  Query number used for the output filename
        sql_text:   SQL string to execute

    Returns:
        (success: bool, error_msg: str|None)
        success is True only when the CSV was actually written to disk.
    """
    filename = os.path.join(OUTPUT_FOLDER, f"day1_query{query_num}.csv")
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql_text), conn)

        print(f"  ✓ Query {query_num}: {len(df)} rows retrieved")

        df.to_csv(filename, index=False)
        # Confirm the file was actually written
        if not os.path.exists(filename):
            raise IOError(f"CSV file was not created: {filename}")

        print(f"  ✓ Exported to: {filename}")
        return True, None

    except Exception as e:
        # Condense the error to the most useful single line
        error_lines = str(e).strip().splitlines()
        short_error = error_lines[0] if error_lines else str(e)
        print(f"  ✗ Query {query_num} FAILED: {short_error}")
        return False, short_error


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Day 1 Query Results Exporter")
    print("=" * 60)
    print()

    # Step 1: Validate credentials
    print("1. Validating credentials...")
    validate_credentials()
    print()

    # Step 2: Create output folder
    print("2. Setting up output folder...")
    create_output_folder()
    print()

    # Step 3: Parse SQL file
    print("3. Reading SQL queries from day1_discovery.sql...")
    queries = read_sql_file()
    query_count = len(queries)
    print(f"✓ Found {query_count} Day 1 queries: {sorted(queries.keys())}")
    print()

    # Step 4: Build engine and verify connection
    print("4. Connecting to database...")
    engine = build_engine()
    test_connection(engine)
    print()

    # Step 5: Execute each query and export
    print("5. Executing queries and exporting results...")
    succeeded = []   # query numbers that exported successfully
    failed    = {}   # query_num -> error message

    for query_num in sorted(queries.keys()):
        print(f"\nProcessing Query {query_num}...")
        ok, err = execute_and_export(engine, query_num, queries[query_num])
        if ok:
            succeeded.append(query_num)
        else:
            failed[query_num] = err

    # NullPool: dispose is a no-op but kept for explicitness
    engine.dispose()
    print()

    # Step 6: Summary
    print("=" * 60)
    print(f"Total queries found : {query_count}")
    print(f"Exported successfully: {len(succeeded)}")
    print(f"Failed              : {len(failed)}")
    print()

    if succeeded:
        print(f"✓ Successful queries : {succeeded}")
    if failed:
        print(f"✗ Failed queries     : {sorted(failed.keys())}")
        print()
        print("Failure details:")
        for qn in sorted(failed.keys()):
            print(f"  Query {qn}: {failed[qn]}")

    print()
    if len(succeeded) == query_count:
        print(f"✓ SUCCESS: {len(succeeded)}/{query_count} queries exported successfully")
    else:
        print(f"✗ INCOMPLETE: {len(succeeded)}/{query_count} queries exported successfully")
    print(f"Results saved to: {os.path.abspath(OUTPUT_FOLDER)}/")
    print("=" * 60)

    if len(succeeded) < query_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
