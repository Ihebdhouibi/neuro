import psycopg2

# Configuration des deux bases
databases = [
    {"name": "PostgreSQL 16", "port": 5432, "user": "postgres", "password": "admin123"},
    {"name": "PostgreSQL 17", "port": 55433, "user": "postgres", "password": "admin123"}
]

print("=" * 60)
print("🔍 Recherche des tables originales (documents, users, medical_lists, processing_jobs)")
print("=" * 60)

for db in databases:
    print(f"\n📡 Vérification {db['name']} (port {db['port']})...")
    
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=db['port'],
            user=db['user'],
            password=db['password'],
            database='postgres'
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Vérifier si la base electron_app existe
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'electron_app'")
        db_exists = cursor.fetchone()
        
        if db_exists:
            print(f"   ✅ Base 'electron_app' existe")
            
            # Se connecter à electron_app
            conn2 = psycopg2.connect(
                host='localhost',
                port=db['port'],
                user=db['user'],
                password=db['password'],
                database='electron_app'
            )
            cursor2 = conn2.cursor()
            
            # Lister les tables
            cursor2.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor2.fetchall()]
            
            print(f"   📋 Tables trouvées ({len(tables)}):")
            for table in tables:
                print(f"      - {table}")
            
            # Vérifier spécifiquement les tables originales
            original_tables = ['documents', 'users', 'medical_lists', 'processing_jobs']
            found = [t for t in original_tables if t in tables]
            if found:
                print(f"   ✅ Tables originales trouvées: {', '.join(found)}")
            else:
                print(f"   ⚠️ Aucune table originale trouvée")
            
            conn2.close()
        else:
            print(f"   ❌ Base 'electron_app' n'existe pas")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")

print("\n" + "=" * 60)