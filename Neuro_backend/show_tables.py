import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    user='postgres',
    password='JOJOhamouch123',
    database='electron_app'
)

cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
tables = cur.fetchall()

print("=" * 50)
print(f"Tables dans PostgreSQL ({len(tables)}):")
print("=" * 50)

for table in tables:
    print(f"  ✅ {table[0]}")

conn.close()