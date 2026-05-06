import mysql.connector
import re

from config import DB_NAME, db_config


def run_sql_file(conn, filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # mysql-connector-python does not understand DELIMITER, so parse manually
    procedures = []
    clean = content

    delim_pattern = re.compile(
        r'DELIMITER\s+\$\$(.*?)DELIMITER\s+;',
        re.DOTALL | re.IGNORECASE
    )
    for match in delim_pattern.finditer(content):
        block = match.group(1)
        for stmt in block.split('$$'):
            stmt = stmt.strip()
            if stmt:
                procedures.append(stmt)

    clean = delim_pattern.sub('', content)

    cur = conn.cursor()

    for stmt in clean.split(';'):
        stmt = stmt.strip()
        if stmt:
            try:
                cur.execute(stmt)
                conn.commit()
            except mysql.connector.Error as e:
                # Suppress harmless errors (object already exists / doesn't exist)
                if e.errno not in (1007, 1008, 1050, 1051, 1060, 1061, 1062, 1091, 1359, 1304):
                    print(f'  [WARN] {filepath}: {e}')

    for proc in procedures:
        proc = proc.strip()
        if proc:
            try:
                cur.execute(proc)
                conn.commit()
            except mysql.connector.Error as e:
                if e.errno not in (1007, 1008, 1050, 1051, 1060, 1061, 1062, 1091, 1359, 1304):
                    print(f'  [WARN] procedure/trigger: {e}')

    cur.close()


def main():
    print('TransferDB Setup')
    print('================')

    # Connect without selecting a database; schema.sql handles DROP/CREATE DATABASE
    conn = mysql.connector.connect(
        **db_config(include_database=False),
        autocommit=True
    )
    print('Step 1: running schema.sql...')
    run_sql_file(conn, 'sql/schema.sql')
    conn.close()
    print('  Schema created.')

    conn = mysql.connector.connect(
        **db_config(database=DB_NAME),
        autocommit=True
    )
    print('Step 2: running triggers.sql...')
    run_sql_file(conn, 'sql/triggers.sql')
    conn.close()
    print('  Triggers and stored procedures created.')

    print()
    print('Setup complete.')
    print('Next:  python load_initial_data.py')


if __name__ == '__main__':
    main()
