# scripts/import_amy_acts.py

#!/usr/bin/env python3
"""
Import AMY orthoptic acts to medical_lists table
python scripts/import_amy_acts.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from database import AsyncSessionLocal
from api import models, schemas, crud


# Données officielles des actes AMY (26 actes)
AMY_ACTS = [
    # BILANS ORTHOPTIQUES
    {"code": "AMY 30", "category": "BILANS ORTHOPTIQUES", 
     "label": "Bilan orthoptique des déficiences visuelles d'origine périphérique ou neuro-ophtalmologique (basse vision)", 
     "price": 78.00},
    {"code": "AMY 30,5", "category": "BILANS ORTHOPTIQUES", 
     "label": "Bilan des conséquences neuro-ophtalmologiques des pathologies générales et des déficiences neuro-visuelles", 
     "price": 79.30},
    {"code": "AMY 10", "category": "BILANS ORTHOPTIQUES", 
     "label": "Bilan des déséquilibres de la vision binoculaire lié à un trouble des capacités fusionnelles", 
     "price": 26.00},
    {"code": "AMY 14,5", "category": "BILANS ORTHOPTIQUES", 
     "label": "Bilan des déséquilibres de la vision binoculaire avec trouble neurosensoriel/accommodatif", 
     "price": 37.70},
    {"code": "AMY 15", "category": "BILANS ORTHOPTIQUES", 
     "label": "Bilan des troubles oculomoteurs : hétérophories, strabismes, paralysies oculomotrices", 
     "price": 39.00},
    {"code": "AMY 15,5", "category": "BILANS ORTHOPTIQUES", 
     "label": "Bilan d'une amblyopie", 
     "price": 40.30},
    
    # RÉÉDUCATION
    {"code": "AMY 19,2", "category": "RÉÉDUCATION", 
     "label": "Rééducation déficience visuelle - Plus de 16 ans (45 mn)", 
     "price": 49.92},
    {"code": "AMY 13,2", "category": "RÉÉDUCATION", 
     "label": "Rééducation déficience visuelle - 16 ans et moins (30 mn)", 
     "price": 34.32},
    {"code": "AMY 7", "category": "RÉÉDUCATION", 
     "label": "Traitement de l'amblyopie par série de vingt séances (20 min/séance)", 
     "price": 18.20},
    {"code": "AMY 7,7", "category": "RÉÉDUCATION", 
     "label": "Traitement du strabisme par série de vingt séances (20 min/séance)", 
     "price": 20.02},
    {"code": "AMY 4", "category": "RÉÉDUCATION", 
     "label": "Traitement des hétérophories et déséquilibres binoculaires par série de vingt séances", 
     "price": 10.40},
    
    # ACTES AVEC ENREGISTREMENTS
    {"code": "AMY 11,5", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Périmétrie ou campimétrie sans mesure de seuil", 
     "price": 29.90},
    {"code": "AMY 12,3", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Périmétrie ou campimétrie avec mesure de seuil", 
     "price": 31.98},
    {"code": "AMY 9", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Courbe d'adaptation à l'obscurité", 
     "price": 23.40},
    {"code": "AMY 6", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Exploration du sens chromatique", 
     "price": 15.60},
    {"code": "AMY 6,7", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Dépistage rétinopathie diabétique par rétinographie avec télétransmission", 
     "price": 17.42},
    {"code": "AMY 6,1", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Dépistage rétinopathie diabétique par rétinographie sans télétransmission", 
     "price": 15.86},
    
    # RÉFRACTION
    {"code": "AMY 8,7", "category": "RÉFRACTION", 
     "label": "Mesure acuité visuelle et réfraction - Primo-prescription", 
     "price": 22.62},
    {"code": "AMY 8", "category": "RÉFRACTION", 
     "label": "Mesure acuité visuelle et réfraction - Renouvellement", 
     "price": 20.80},
    
    # DÉPISTAGE ENFANTS
    {"code": "AMY 7,7", "category": "DÉPISTAGE ENFANTS", 
     "label": "Dépistage amblyopie nourrissons 9-15 mois", 
     "price": 20.02},
    {"code": "AMY 8,4", "category": "DÉPISTAGE ENFANTS", 
     "label": "Dépistage troubles réfraction enfants 30 mois-5 ans", 
     "price": 21.84},
    
    # Note: AMY 9 apparaît aussi pour le test Farnsworth
    {"code": "AMY 9", "category": "ACTES AVEC ENREGISTREMENTS", 
     "label": "Exploration du sens chromatique au test de Farnsworth 100 HUE", 
     "price": 23.40},
]


async def import_amy_acts():
    """Import AMY acts into medical_lists table"""
    logger.info("🚀 Début import des actes AMY")
    
    async with AsyncSessionLocal() as db:
        imported = 0
        updated = 0
        
        for act in AMY_ACTS:
            existing = await crud.get_medical_list_by_code(db, act["code"])
            
            if existing:
                # Mettre à jour si différent
                if existing.price != act["price"] or existing.label != act["label"]:
                    update_data = schemas.MedicalListUpdate(
                        label=act["label"],
                        price=act["price"],
                        category=act["category"],
                        is_active=True
                    )
                    await crud.update_medical_list(db, existing.id, update_data)
                    updated += 1
                    logger.debug(f"🔄 Mis à jour: {act['code']}")
            else:
                # Créer nouveau
                new_act = schemas.MedicalListCreate(
                    code=act["code"],
                    category=act["category"],
                    label=act["label"],
                    price=act["price"],
                    is_active=True
                )
                await crud.create_medical_list(db, new_act)
                imported += 1
                logger.debug(f"➕ Ajouté: {act['code']}")
        
        await db.commit()
        
    logger.info(f"✅ Import terminé: {imported} ajoutés, {updated} mis à jour sur {len(AMY_ACTS)} actes")


async def main():
    await import_amy_acts()


if __name__ == "__main__":
    asyncio.run(main())