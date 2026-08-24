#!/usr/bin/env python3
"""
Export Day 2 SQL Query Results to CSV Files

Purpose:
    Execute all queries from day2_aggregations.sql against the retail_db MySQL database
    and export each result set to a separate CSV file in the day2_results/ folder.

Requirements:
    - sqlalchemy
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
        print("Please set MYSQL_USER and MYSQL_PASSWORD in .env")
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

    # Step 1: Find all -- Query N: markers and their positions.
    # Use the full comment line in the pattern so marker_end lands at end-of-line.
    marker_pattern = re.compile(r"-- Query (\d+):\s*[^\n]*", re.IGNORECASE)
    markers = [(int(m.group(1)), m.start(), m.end()) for m in marker_pattern.finditer(content)]

    # Build a plain dict of marker start positions for the Query-8 special case
    query_markers = {qn: sp for qn, sp, _me in markers}

    def split_statements(block):
        """
        Split a SQL block into individual statements by semicolons.
        Returns a list of non-empty, non-setup statement strings (no trailing semicolons).
        Strips comment-only lines before checking each part.
        """
        parts = block.split(";")
        stmts = []
        for part in parts:
            # Remove pure comment lines, then check if real SQL remains
            code = re.sub(r"--[^\n]*", "", part).strip()
            if not code:
                continue
            stmt = part.strip()
            if not stmt:
                continue
            first_kw = stmt.split()[0].upper() if stmt.split() else ""
            if first_kw in ("USE", "SHOW", "DESCRIBE", "DESC"):
                continue
            stmts.append(stmt)
        return stmts

    # Step 2: Extract text for each marked query
    for i, (query_num, start_pos, marker_end) in enumerate(markers):
        # SQL ends at start of next marker, or end of file
        sql_end = markers[i + 1][1] if i + 1 < len(markers) else len(content)

        # Detect a SQL keyword glued directly to the description text
        # e.g. "...categorySELECT c.city" — (?<=[a-zA-Z]) requires a preceding letter
        comment_line_end = content.find("\n", start_pos)
        if comment_line_end == -1:
            comment_line_end = marker_end
        comment_line = content[start_pos:comment_line_end]
        inline_sql = re.search(r'(?<=[a-zA-Z])(SELECT|WITH)\b', comment_line, re.IGNORECASE)
        if inline_sql:
            sql_start = start_pos + inline_sql.start()
        else:
            sql_start = marker_end

        block = content[sql_start:sql_end]
        stmts = split_statements(block)

        # A marker maps to the FIRST real statement in its block.
        # If multiple statements are present (e.g. Query 7's block also contains
        # the orphaned Query 8 UNION ALL), only the first is assigned here;
        # the second will be picked up by the Query-8 special case below.
        if stmts:
            queries[query_num] = stmts[0]

    # Step 3: Handle Query 8 if missing (orphaned SQL between Query 7 and 9).
    # Query 8 might not have a -- Query 8: marker; in that case it is the second
    # statement in the block that follows the -- Query 7: marker.
    if 7 in queries and 9 in queries and 8 not in queries:
        query_7_pos = query_markers.get(7)
        query_9_pos = query_markers.get(9)

        if query_7_pos is not None and query_9_pos is not None:
            after_query_7_comment = content.find("\n", query_7_pos) + 1
            between_block = content[after_query_7_comment:query_9_pos]
            stmts = split_statements(between_block)

            # stmts[0] is already assigned as Query 7; stmts[1] (if present) is Query 8
            if len(stmts) >= 2:
                queries[8] = stmts[1]
            elif len(stmts) == 1 and 7 not in queries:
                queries[8] = stmts[0]

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
    filename = os.path.join(OUTPUT_FOLDER, f"day2_query{query_num}.csv")
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql_text), conn)

        print(f"  ✓ Query {query_num}: {len(df)} rows retrieved")

        df.to_csv(filename, index=False)
        if not os.path.exists(filename):
            raise IOError(f"CSV file was not created: {filename}")

        print(f"  ✓ Exported to: {filename}")
        return True, None

    except Exception as e:
        error_lines = str(e).strip().splitlines()
        short_error = error_lines[0] if error_lines else str(e)
        print(f"  ✗ Query {query_num} FAILED: {short_error}")
        return False, short_error


def main():
    """Main execution flow."""
    print("=" * 60)
    print("Day 2 Query Results Exporter")
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
    print("3. Reading SQL queries from day2_aggregations.sql...")
    queries = read_sql_file()
    query_count = len(queries)
    print(f"✓ Found {query_count} Day 2 queries: {sorted(queries.keys())}")
    print(f"✓ Will create files: day2_query1.csv through day2_query10.csv")
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
