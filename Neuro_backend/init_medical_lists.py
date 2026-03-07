"""
Script to initialize medical lists in the database
Run this script to populate the medical_lists table with AMY codes
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from database import AsyncSessionLocal
from api.models import MedicalList
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Medical list data from the provided images
MEDICAL_LISTS_DATA = [
    # BILANS ORTHOPTIQUES
    {"code": "AMY 30", "category": "BILANS ORTHOPTIQUES", "label": "Bilan orthoptique des déficiences visuelles d'origine périphérique ou neuro-ophtalmologique (basse vision)", "price": 78.00},
    {"code": "AMY 30,5", "category": "BILANS ORTHOPTIQUES", "label": "Bilan des conséquences neuro-ophtalmologiques des pathologies générales et des déficiences neuro-visuelles", "price": 79.30},
    {"code": "AMY 10", "category": "BILANS ORTHOPTIQUES", "label": "Bilan des déséquilibres de la vision binoculaire lié à un trouble des capacités fusionnelles", "price": 26.00},
    {"code": "AMY 14,5", "category": "BILANS ORTHOPTIQUES", "label": "Bilan des déséquilibres de la vision binoculaire avec trouble neurosensoriel/accommodatif", "price": 37.70},
    {"code": "AMY 15", "category": "BILANS ORTHOPTIQUES", "label": "Bilan des troubles oculomoteurs : hétérophories, strabismes, paralysies oculomotrices", "price": 39.00},
    {"code": "AMY 15,5", "category": "BILANS ORTHOPTIQUES", "label": "Bilan d'une amblyopie", "price": 40.30},
    
    # RÉÉDUCATION
    {"code": "AMY 19,2", "category": "RÉÉDUCATION", "label": "Rééducation déficience visuelle - Plus de 16 ans (45 mn)", "price": 49.92},
    {"code": "AMY 13,2", "category": "RÉÉDUCATION", "label": "Rééducation déficience visuelle - 16 ans et moins (30 mn)", "price": 34.32},
    {"code": "AMY 7", "category": "RÉÉDUCATION", "label": "Traitement de l'amblyopie par série de vingt séances (20 min/séance)", "price": 18.20},
    {"code": "AMY 7,7", "category": "RÉÉDUCATION", "label": "Traitement du strabisme par série de vingt séances (20 min/séance)", "price": 20.02},
    {"code": "AMY 4", "category": "RÉÉDUCATION", "label": "Traitement des hétérophories et déséquilibres binoculaires par série de vingt séances", "price": 10.40},
    
    # ACTES AVEC ENREGISTREMENTS
    {"code": "AMY 11,5", "category": "ACTES AVEC ENREGISTREMENTS", "label": "Périmétrie ou campimétrie sans mesure de seuil", "price": 29.90},
    {"code": "AMY 12,3", "category": "ACTES AVEC ENREGISTREMENTS", "label": "Périmétrie ou campimétrie avec mesure de seuil", "price": 31.98},
    {"code": "AMY 9", "category": "ACTES AVEC ENREGISTREMENTS", "label": "Courbe d'adaptation à l'obscurité", "price": 23.40},
    {"code": "AMY 6", "category": "ACTES AVEC ENREGISTREMENTS", "label": "Exploration du sens chromatique", "price": 15.60},
    {"code": "AMY 6,7", "category": "ACTES AVEC ENREGISTREMENTS", "label": "Dépistage rétinopathie diabétique par rétinographie avec télétransmission", "price": 17.42},
    {"code": "AMY 6,1", "category": "ACTES AVEC ENREGISTREMENTS", "label": "Dépistage rétinopathie diabétique par rétinographie sans télétransmission", "price": 15.86},
    
    # RÉFRACTION
    {"code": "AMY 8,7", "category": "RÉFRACTION", "label": "Mesure acuité visuelle et réfraction - Primo-prescription", "price": 22.62},
    {"code": "AMY 8", "category": "RÉFRACTION", "label": "Mesure acuité visuelle et réfraction - Renouvellement", "price": 20.80},
    
    # DÉPISTAGE ENFANTS
    {"code": "AMY 8,4", "category": "DÉPISTAGE ENFANTS", "label": "Dépistage troubles réfraction enfants 30 mois-5 ans", "price": 21.84},
]

async def init_medical_lists():
    """Initialize medical lists in the database"""
    async with AsyncSessionLocal() as session:
        try:
            # Check if data already exists
            result = await session.execute(select(MedicalList))
            existing_count = len(result.scalars().all())
            
            if existing_count > 0:
                print(f"Database already contains {existing_count} medical list items.")
                response = input("Do you want to add/update the data? (y/n): ")
                if response.lower() != 'y':
                    print("Aborted.")
                    return
            
            # Add medical lists
            added_count = 0
            updated_count = 0
            
            for item_data in MEDICAL_LISTS_DATA:
                # Check if code already exists
                result = await session.execute(
                    select(MedicalList).filter(MedicalList.code == item_data["code"])
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing
                    for key, value in item_data.items():
                        setattr(existing, key, value)
                    updated_count += 1
                    print(f"Updated: {item_data['code']}")
                else:
                    # Create new
                    medical_list = MedicalList(**item_data)
                    session.add(medical_list)
                    added_count += 1
                    print(f"Added: {item_data['code']}")
            
            await session.commit()
            print(f"\n✓ Successfully initialized medical lists:")
            print(f"  - Added: {added_count} items")
            print(f"  - Updated: {updated_count} items")
            print(f"  - Total: {added_count + updated_count} items")
            
        except Exception as e:
            await session.rollback()
            print(f"Error initializing medical lists: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(init_medical_lists())

