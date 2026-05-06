
from db import get_connection

conn = get_connection()
cur = conn.cursor()

tables = [
    'DatabaseManager', 'Person', 'Player', 'Manager', 'Referee',
    'Stadium', 'Club', 'Competition', '`Match`',
    'Contract', 'Transfer_Record', 'Match_Squad', 'Match_Stats'
]

for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    cur.execute(f"SELECT * FROM {t}")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"\n{'='*60}")
    print(f"  {t.replace('`','')}  ({count} satır)")
    print(f"{'='*60}")
    print("  " + " | ".join(cols))
    print("  " + "-" * 50)
    for row in rows:
        print("  " + " | ".join(str(v)[:20] for v in row))

cur.close()
conn.close()
