import psycopg2

# Configuration avec vos paramètres
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "user": "postgres",
    "password": "admin123",
    "database": "electron_app"
}

print("📡 Connexion à PostgreSQL sur le port 55432...")

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    print("✅ Connecté avec succès!")

    # Ajouter les nouvelles tables
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
    print("✅ Table 'centers' crée")

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
    print("✅ Table 'practitioners' crée")

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
    print("✅ Table 'templates' crée")

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
    print("✅ Table 'prescriptions' crée")

    conn.commit()

    # Afficher toutes les tables
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📋 Toutes les tables dans PostgreSQL ({len(tables)}):")
    for table in tables:
        print(f"   - {table}")

    cursor.close()
    conn.close()
    print("\n🎉 Migration terminée! Toutes les tables sont dans PostgreSQL.")

except Exception as e:
    print(f"❌ Erreur: {e}")