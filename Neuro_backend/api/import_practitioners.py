# scripts/import_practitioners.py

#!/usr/bin/env python3
"""
Import practitioners from Excel file to PostgreSQL
python scripts/import_practitioners.py --file "Praticiens CDSOV.xlsx"
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Ajouter le backend au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sqlalchemy import select
from loguru import logger
from database import AsyncSessionLocal, sync_engine
from api import models, schemas, crud


def clean_rpps(value):
    """Nettoyer le numéro RPPS"""
    if pd.isna(value):
        return None
    if value == '-' or value == '':
        return None
    return str(value).strip()


def import_practitioners_sync(excel_path: str):
    """Import synchronisé (pour script simple)"""
    logger.info(f"📂 Lecture du fichier: {excel_path}")
    
    # Lecture Excel
    df = pd.read_excel(excel_path)
    
    # Renommage des colonnes
    df = df.rename(columns={
        'P.Centre': 'centre',
        'P.Code': 'pcode',
        'P.Nom Praticien': 'nom',
        'P.Prenom Praticien': 'prenom',
        'P.RPPS': 'rpps',
        'P.TARIF': 'tarif',
        'P.CODE_CONVENTIONNEL': 'code_conventionnel',
        'P.IK': 'ik',
        'P.PARCOURS': 'parcours',
        'P.HISTO_DENT': 'histo_dent',
        'P.CONDITION_EXERCICE': 'condition_exercice'
    })
    
    # Nettoyage
    df['pcode'] = df['pcode'].astype(str).str.strip().str.upper()
    df['rpps'] = df['rpps'].apply(clean_rpps)
    df['tarif'] = pd.to_numeric(df['tarif'], errors='coerce').fillna(10.0)
    df['type'] = 'prescripteur'  # valeur par défaut
    df['is_active'] = True
    
    # Supprimer les lignes sans P.Code
    df = df[df['pcode'].notna() & (df['pcode'] != 'nan')]
    
    logger.info(f"📊 {len(df)} praticiens trouvés dans le fichier")
    
    # Import via SQLAlchemy (sync)
    df.to_sql('practitioners', sync_engine, if_exists='replace', index=False)
    
    logger.info(f"✅ Importé {len(df)} praticiens dans la base")
    return len(df)


async def import_practitioners_async(excel_path: str):
    """Import asynchrone avec vérification des doublons"""
    logger.info(f"📂 Lecture du fichier: {excel_path}")
    
    df = pd.read_excel(excel_path)
    
    df = df.rename(columns={
        'P.Centre': 'centre',
        'P.Code': 'pcode',
        'P.Nom Praticien': 'nom',
        'P.Prenom Praticien': 'prenom',
        'P.RPPS': 'rpps',
        'P.TARIF': 'tarif',
        'P.CODE_CONVENTIONNEL': 'code_conventionnel',
        'P.IK': 'ik',
        'P.PARCOURS': 'parcours',
        'P.HISTO_DENT': 'histo_dent',
        'P.CONDITION_EXERCICE': 'condition_exercice'
    })
    
    df['pcode'] = df['pcode'].astype(str).str.strip().str.upper()
    df['rpps'] = df['rpps'].apply(clean_rpps)
    df['tarif'] = pd.to_numeric(df['tarif'], errors='coerce').fillna(10.0)
    df = df[df['pcode'].notna() & (df['pcode'] != 'nan')]
    
    async with AsyncSessionLocal() as db:
        # Vérifier les existants
        existing_result = await db.execute(select(models.Practitioner.pcode))
        existing_pcodes = set([r[0] for r in existing_result.all()])
        
        new_practitioners = []
        for _, row in df.iterrows():
            if row['pcode'] not in existing_pcodes:
                pract = schemas.PractitionerCreate(
                    centre=row['centre'],
                    pcode=row['pcode'],
                    nom=row['nom'],
                    prenom=row['prenom'],
                    rpps=row['rpps'],
                    tarif=row['tarif'],
                    code_conventionnel=row['code_conventionnel'] if pd.notna(row['code_conventionnel']) else None,
                    ik=row['ik'] if pd.notna(row['ik']) else None,
                    parcours=row['parcours'] if pd.notna(row['parcours']) else None,
                    histo_dent=row['histo_dent'] if pd.notna(row['histo_dent']) else None,
                    condition_exercice=row['condition_exercice'] if pd.notna(row['condition_exercice']) else None
                )
                new_practitioners.append(pract)
        
        if new_practitioners:
            await crud.bulk_create_practitioners(db, new_practitioners)
            logger.info(f"✅ Importé {len(new_practitioners)} nouveaux praticiens")
        else:
            logger.info("ℹ️ Aucun nouveau praticien à importer")
        
        return len(new_practitioners)


def main():
    parser = argparse.ArgumentParser(description="Import practitioners from Excel")
    parser.add_argument("--file", required=True, help="Path to Excel file")
    parser.add_argument("--async", dest="async_mode", action="store_true", help="Use async mode")
    args = parser.parse_args()
    
    if args.async_mode:
        count = asyncio.run(import_practitioners_async(args.file))
    else:
        count = import_practitioners_sync(args.file)
    
    print(f"\n✅ Import terminé: {count} praticiens")


if __name__ == "__main__":
    main()