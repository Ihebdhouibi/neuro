import sqlite3

conn = sqlite3.connect('neurox.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print('Tables dans neurox.db:')
for table in sorted(tables):
    print(f'  - {table}')
conn.close()