import psycopg2

print("=" * 50)
print("Check PostgreSQL tables")
print("=" * 50)

# Test PostgreSQL 16
print("\n[1] Testing PostgreSQL 16 on port 5432...")
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='admin123',
        database='postgres'
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'electron_app'")
    exists = cursor.fetchone()
    
    if exists:
        print("    -> Database 'electron_app' exists")
        conn2 = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='admin123',
            database='electron_app'
        )
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor2.fetchall()]
        print(f"    -> Tables found: {tables}")
        conn2.close()
    else:
        print("    -> Database 'electron_app' does NOT exist")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"    -> ERROR: {e}")

# Test PostgreSQL 17
print("\n[2] Testing PostgreSQL 17 on port 55433...")
try:
    conn = psycopg2.connect(
        host='localhost',
        port=55433,
        user='postgres',
        password='admin123',
        database='postgres'
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'electron_app'")
    exists = cursor.fetchone()
    
    if exists:
        print("    -> Database 'electron_app' exists")
        conn2 = psycopg2.connect(
            host='localhost',
            port=55433,
            user='postgres',
            password='admin123',
            database='electron_app'
        )
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor2.fetchall()]
        print(f"    -> Tables found: {tables}")
        conn2.close()
    else:
        print("    -> Database 'electron_app' does NOT exist")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"    -> ERROR: {e}")

print("\n" + "=" * 50)