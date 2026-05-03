# create_new_tables.py - Script indépendant
import psycopg2

# Configuration PostgreSQL
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
    "database": "electron_app"
}

print("📡 Connexion à PostgreSQL...")

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Vérifier la connexion
    cursor.execute("SELECT version()")
    version = cursor.fetchone()[0]
    print(f"✅ Connecté: {version[:50]}...")
    
    # Lister les tables existantes
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    print(f"📋 Tables existantes: {', '.join(tables)}")
    
    # Créer les nouvelles tables
    tables_created = []
    
    # Table centers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS centers (
            id SERIAL PRIMARY KEY,
            nom VARCHAR UNIQUE NOT NULL,
            finess VARCHAR UNIQUE NOT NULL,
            adresse VARCHAR NOT NULL,
            ville VARCHAR NOT NULL,
            code_postal VARCHAR NOT NULL,
            telephone VARCHAR,
            email VARCHAR,
            tampon_path VARCHAR,
            signature_path VARCHAR,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    tables_created.append("centers")
    
    # Table practitioners
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS practitioners (
            id SERIAL PRIMARY KEY,
            centre VARCHAR NOT NULL,
            pcode VARCHAR UNIQUE NOT NULL,
            nom VARCHAR NOT NULL,
            prenom VARCHAR NOT NULL,
            rpps VARCHAR,
            type VARCHAR DEFAULT 'prescripteur',
            tarif FLOAT DEFAULT 10.0,
            code_conventionnel VARCHAR,
            ik VARCHAR,
            parcours VARCHAR,
            histo_dent VARCHAR,
            condition_exercice VARCHAR,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    tables_created.append("practitioners")
    
    # Table templates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id SERIAL PRIMARY KEY,
            center_id INTEGER NOT NULL,
            nom VARCHAR NOT NULL,
            type VARCHAR NOT NULL,
            contenu_html TEXT,
            contenu_path VARCHAR,
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    tables_created.append("templates")
    
    # Table prescriptions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id SERIAL PRIMARY KEY,
            ordonnance_id VARCHAR UNIQUE NOT NULL,
            fse_number VARCHAR,
            ipp_number VARCHAR,
            patient_nom VARCHAR NOT NULL,
            patient_prenom VARCHAR NOT NULL,
            patient_nir VARCHAR,
            patient_ipp VARCHAR,
            prescripteur_pcode VARCHAR,
            acte_code VARCHAR,
            center_finess VARCHAR,
            date_soin TIMESTAMP,
            mode_generation VARCHAR DEFAULT 'auto_fse',
            pdf_path VARCHAR,
            thumbnail_path VARCHAR,
            status VARCHAR DEFAULT 'generated',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    tables_created.append("prescriptions")
    
    conn.commit()
    
    for table in tables_created:
        print(f"✅ Table créée/vérifiée: {table}")
    
    # Lister toutes les tables après création
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📋 Tables maintenant ({len(tables)}): {', '.join(tables)}")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 Migration terminée avec succès !")
    print("\n⚠️ Note: Les clés étrangères (Foreign Keys) n'ont pas été ajoutées pour éviter les erreurs.")
    print("   Vous pourrez les ajouter plus tard si nécessaire.")
    
except Exception as e:
    print(f"❌ Erreur: {e}")