"""
Seed script for NAPPI (National Pharmaceutical Product Interface) codes.
Contains 120 commonly prescribed medicines in South Africa.
Run: python seed_nappi.py
"""
import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models.billing import NappiCode

# Removed hardcoded engine and AsyncSessionLocal

# Format: (nappi_code, product_name, generic_name, dosage_form, strength, schedule)
NAPPI_CODES = [
    # ── Cardiovascular ──────────────────────────────────────────────────────
    ("700127001", "Atenolol 50 Pharmaco", "Atenolol", "Tablet", "50mg", "S3"),
    ("700127002", "Atenolol 100 Pharmaco", "Atenolol", "Tablet", "100mg", "S3"),
    ("700221001", "Amlodipine 5 Hexal", "Amlodipine besylate", "Tablet", "5mg", "S3"),
    ("700221002", "Amlodipine 10 Hexal", "Amlodipine besylate", "Tablet", "10mg", "S3"),
    ("707345001", "Enalapril 5 Mylan", "Enalapril maleate", "Tablet", "5mg", "S3"),
    ("707345002", "Enalapril 10 Mylan", "Enalapril maleate", "Tablet", "10mg", "S3"),
    ("707345003", "Enalapril 20 Mylan", "Enalapril maleate", "Tablet", "20mg", "S3"),
    ("708912001", "Ramipril 5 Cipla", "Ramipril", "Capsule", "5mg", "S3"),
    ("708912002", "Ramipril 10 Cipla", "Ramipril", "Capsule", "10mg", "S3"),
    ("712440001", "Perindopril 4 Servier", "Perindopril arginine", "Tablet", "4mg", "S3"),
    ("712440002", "Perindopril 8 Servier", "Perindopril arginine", "Tablet", "8mg", "S3"),
    ("715678001", "Losartan 50 Pharmaplan", "Losartan potassium", "Tablet", "50mg", "S3"),
    ("715678002", "Losartan 100 Pharmaplan", "Losartan potassium", "Tablet", "100mg", "S3"),
    ("719234001", "Furosemide 40 Hexal", "Furosemide", "Tablet", "40mg", "S3"),
    ("722891001", "Spironolactone 25 Cipla", "Spironolactone", "Tablet", "25mg", "S3"),
    ("722891002", "Spironolactone 50 Cipla", "Spironolactone", "Tablet", "50mg", "S3"),
    ("725567001", "Bisoprolol 5 Mylan", "Bisoprolol fumarate", "Tablet", "5mg", "S3"),
    ("725567002", "Bisoprolol 10 Mylan", "Bisoprolol fumarate", "Tablet", "10mg", "S3"),
    ("728123001", "Carvedilol 12.5 Hexal", "Carvedilol", "Tablet", "12.5mg", "S3"),
    ("728123002", "Carvedilol 25 Hexal", "Carvedilol", "Tablet", "25mg", "S3"),

    # ── Statins / Lipid lowering ────────────────────────────────────────────
    ("731890001", "Simvastatin 10 Aspen", "Simvastatin", "Tablet", "10mg", "S3"),
    ("731890002", "Simvastatin 20 Aspen", "Simvastatin", "Tablet", "20mg", "S3"),
    ("731890003", "Simvastatin 40 Aspen", "Simvastatin", "Tablet", "40mg", "S3"),
    ("734567001", "Atorvastatin 10 Cipla", "Atorvastatin calcium", "Tablet", "10mg", "S3"),
    ("734567002", "Atorvastatin 20 Cipla", "Atorvastatin calcium", "Tablet", "20mg", "S3"),
    ("734567003", "Atorvastatin 40 Cipla", "Atorvastatin calcium", "Tablet", "40mg", "S3"),
    ("734567004", "Atorvastatin 80 Cipla", "Atorvastatin calcium", "Tablet", "80mg", "S3"),
    ("738234001", "Rosuvastatin 10 Pharmaplan", "Rosuvastatin calcium", "Tablet", "10mg", "S3"),
    ("738234002", "Rosuvastatin 20 Pharmaplan", "Rosuvastatin calcium", "Tablet", "20mg", "S3"),
    ("741890001", "Fenofibrate 145 Mylan", "Fenofibrate", "Tablet", "145mg", "S3"),
    ("741890002", "Ezetimibe 10 Hexal", "Ezetimibe", "Tablet", "10mg", "S3"),

    # ── Diabetes ─────────────────────────────────────────────────────────────
    ("745678001", "Metformin 500 Aspen", "Metformin hydrochloride", "Tablet", "500mg", "S3"),
    ("745678002", "Metformin 850 Aspen", "Metformin hydrochloride", "Tablet", "850mg", "S3"),
    ("745678003", "Metformin 1000 Aspen", "Metformin hydrochloride", "Tablet", "1000mg", "S3"),
    ("748234001", "Glibenclamide 5 Cipla", "Glibenclamide", "Tablet", "5mg", "S3"),
    ("751890001", "Glimepiride 2 Hexal", "Glimepiride", "Tablet", "2mg", "S3"),
    ("751890002", "Glimepiride 4 Hexal", "Glimepiride", "Tablet", "4mg", "S3"),
    ("754567001", "Sitagliptin 100 MSD", "Sitagliptin phosphate", "Tablet", "100mg", "S3"),
    ("757234001", "Empagliflozin 10 BI", "Empagliflozin", "Tablet", "10mg", "S3"),
    ("757234002", "Empagliflozin 25 BI", "Empagliflozin", "Tablet", "25mg", "S3"),
    ("760890001", "Insulin Glargine 100IU/ml Sanofi", "Insulin glargine", "Injection", "100IU/ml", "S4"),
    ("760890002", "Insulin Aspart 100IU/ml NovoNordisk", "Insulin aspart", "Injection", "100IU/ml", "S4"),
    ("763567001", "Insulin Human 100IU/ml Novo", "Human insulin", "Injection", "100IU/ml", "S4"),

    # ── Respiratory ───────────────────────────────────────────────────────────
    ("766234001", "Salbutamol 100mcg Cipla", "Salbutamol sulphate", "Inhaler", "100mcg/dose", "S3"),
    ("769890001", "Beclometasone 100 Cipla", "Beclometasone dipropionate", "Inhaler", "100mcg/dose", "S3"),
    ("769890002", "Beclometasone 250 Cipla", "Beclometasone dipropionate", "Inhaler", "250mcg/dose", "S3"),
    ("772567001", "Fluticasone 125 Aspen", "Fluticasone propionate", "Inhaler", "125mcg/dose", "S3"),
    ("772567002", "Fluticasone 250 Aspen", "Fluticasone propionate", "Inhaler", "250mcg/dose", "S3"),
    ("775234001", "Salmeterol/Fluticasone 25/125 GSK", "Salmeterol/Fluticasone", "Inhaler", "25/125mcg", "S3"),
    ("775234002", "Salmeterol/Fluticasone 25/250 GSK", "Salmeterol/Fluticasone", "Inhaler", "25/250mcg", "S3"),
    ("778890001", "Tiotropium 18mcg Boehringer", "Tiotropium bromide", "Capsule for inhalation", "18mcg", "S3"),
    ("781567001", "Montelukast 10 Cipla", "Montelukast sodium", "Tablet", "10mg", "S3"),
    ("781567002", "Montelukast 5 Cipla Chew", "Montelukast sodium", "Chewable tablet", "5mg", "S3"),
    ("784234001", "Budesonide/Formoterol 160/4.5 AZ", "Budesonide/Formoterol", "Inhaler", "160/4.5mcg", "S3"),

    # ── Analgesics / Antipyretics ─────────────────────────────────────────────
    ("787890001", "Paracetamol 500 Aspen", "Paracetamol", "Tablet", "500mg", "S0"),
    ("787890002", "Paracetamol 1000 Aspen", "Paracetamol", "Tablet", "1000mg", "S0"),
    ("790567001", "Ibuprofen 200 Cipla", "Ibuprofen", "Tablet", "200mg", "S0"),
    ("790567002", "Ibuprofen 400 Cipla", "Ibuprofen", "Tablet", "400mg", "S1"),
    ("793234001", "Diclofenac 50 Hexal", "Diclofenac sodium", "Tablet", "50mg", "S3"),
    ("793234002", "Diclofenac 75 Hexal SR", "Diclofenac sodium", "Sustained release tablet", "75mg", "S3"),
    ("796890001", "Codeine 30/Paracetamol 500 Aspen", "Codeine/Paracetamol", "Tablet", "30/500mg", "S3"),
    ("799567001", "Tramadol 50 Cipla", "Tramadol hydrochloride", "Capsule", "50mg", "S5"),
    ("802234001", "Tramadol 100 SR Cipla", "Tramadol hydrochloride", "Sustained release tablet", "100mg", "S5"),
    ("804890001", "Morphine 10 Aspen IR", "Morphine sulphate", "Tablet", "10mg", "S6"),
    ("804890002", "Morphine 30 Aspen SR", "Morphine sulphate", "Sustained release tablet", "30mg", "S6"),

    # ── Antibiotics ───────────────────────────────────────────────────────────
    ("807567001", "Amoxicillin 500 Cipla", "Amoxicillin trihydrate", "Capsule", "500mg", "S3"),
    ("810234001", "Amoxicillin/Clavulanate 875/125 Mylan", "Amoxicillin/Clavulanate", "Tablet", "875/125mg", "S3"),
    ("812890001", "Azithromycin 500 Aspen", "Azithromycin dihydrate", "Tablet", "500mg", "S3"),
    ("815567001", "Clarithromycin 500 Hexal", "Clarithromycin", "Tablet", "500mg", "S3"),
    ("818234001", "Doxycycline 100 Cipla", "Doxycycline hyclate", "Capsule", "100mg", "S3"),
    ("820890001", "Ciprofloxacin 500 Mylan", "Ciprofloxacin hydrochloride", "Tablet", "500mg", "S3"),
    ("823567001", "Trimethoprim/Sulfamethoxazole 160/800 Aspen", "Cotrimoxazole", "Tablet", "160/800mg", "S3"),
    ("826234001", "Metronidazole 400 Cipla", "Metronidazole", "Tablet", "400mg", "S3"),
    ("828890001", "Fluconazole 150 Hexal", "Fluconazole", "Capsule", "150mg", "S3"),

    # ── HIV / ARVs ───────────────────────────────────────────────────────────
    ("831567001", "Efavirenz 600 Aspen", "Efavirenz", "Tablet", "600mg", "S4"),
    ("834234001", "Lamivudine/Tenofovir/Efavirenz 300/300/600 Cipla", "3TC/TDF/EFV", "Tablet", "300/300/600mg", "S4"),
    ("836890001", "Atazanavir/Ritonavir 300/100 MSD", "Atazanavir/Ritonavir", "Capsule", "300/100mg", "S4"),
    ("839567001", "Dolutegravir 50 ViiV", "Dolutegravir sodium", "Tablet", "50mg", "S4"),
    ("842234001", "Abacavir/Lamivudine 600/300 GSK", "Abacavir/Lamivudine", "Tablet", "600/300mg", "S4"),
    ("844890001", "Emtricitabine/Tenofovir 200/245 Gilead", "FTC/TDF", "Tablet", "200/245mg", "S4"),

    # ── Gastrointestinal ─────────────────────────────────────────────────────
    ("847567001", "Omeprazole 20 Cipla", "Omeprazole", "Capsule", "20mg", "S1"),
    ("847567002", "Omeprazole 40 Cipla", "Omeprazole", "Capsule", "40mg", "S3"),
    ("850234001", "Pantoprazole 40 Hexal", "Pantoprazole sodium", "Tablet", "40mg", "S3"),
    ("852890001", "Esomeprazole 20 AZ", "Esomeprazole magnesium", "Capsule", "20mg", "S1"),
    ("852890002", "Esomeprazole 40 AZ", "Esomeprazole magnesium", "Capsule", "40mg", "S3"),
    ("855567001", "Domperidone 10 Cipla", "Domperidone maleate", "Tablet", "10mg", "S2"),
    ("858234001", "Metoclopramide 10 Aspen", "Metoclopramide hydrochloride", "Tablet", "10mg", "S3"),
    ("860890001", "Loperamide 2 Cipla", "Loperamide hydrochloride", "Capsule", "2mg", "S0"),
    ("863567001", "Lactulose 3.35g/5ml Aspen", "Lactulose", "Syrup", "3.35g/5ml", "S0"),

    # ── Psychiatry / Neurology ───────────────────────────────────────────────
    ("866234001", "Sertraline 50 Mylan", "Sertraline hydrochloride", "Tablet", "50mg", "S5"),
    ("866234002", "Sertraline 100 Mylan", "Sertraline hydrochloride", "Tablet", "100mg", "S5"),
    ("868890001", "Fluoxetine 20 Cipla", "Fluoxetine hydrochloride", "Capsule", "20mg", "S5"),
    ("871567001", "Escitalopram 10 Hexal", "Escitalopram oxalate", "Tablet", "10mg", "S5"),
    ("871567002", "Escitalopram 20 Hexal", "Escitalopram oxalate", "Tablet", "20mg", "S5"),
    ("874234001", "Amitriptyline 25 Aspen", "Amitriptyline hydrochloride", "Tablet", "25mg", "S5"),
    ("876890001", "Clonazepam 0.5 Cipla", "Clonazepam", "Tablet", "0.5mg", "S6"),
    ("876890002", "Clonazepam 2 Cipla", "Clonazepam", "Tablet", "2mg", "S6"),
    ("879567001", "Haloperidol 5 Aspen", "Haloperidol", "Tablet", "5mg", "S5"),
    ("882234001", "Risperidone 2 Mylan", "Risperidone", "Tablet", "2mg", "S5"),
    ("884890001", "Carbamazepine 200 Cipla", "Carbamazepine", "Tablet", "200mg", "S3"),
    ("887567001", "Sodium Valproate 200 Aspen", "Sodium valproate", "Tablet", "200mg", "S3"),
    ("887567002", "Sodium Valproate 500 Aspen CR", "Sodium valproate", "Controlled release tablet", "500mg", "S3"),

    # ── Thyroid / Hormones ───────────────────────────────────────────────────
    ("890234001", "Levothyroxine 50mcg Hexal", "Levothyroxine sodium", "Tablet", "50mcg", "S3"),
    ("890234002", "Levothyroxine 100mcg Hexal", "Levothyroxine sodium", "Tablet", "100mcg", "S3"),
    ("892890001", "Carbimazole 5 Aspen", "Carbimazole", "Tablet", "5mg", "S3"),
    ("895567001", "Prednisone 5 Cipla", "Prednisone", "Tablet", "5mg", "S3"),
    ("895567002", "Prednisone 20 Cipla", "Prednisone", "Tablet", "20mg", "S3"),

    # ── Vitamins / Supplements ───────────────────────────────────────────────
    ("898234001", "Folic Acid 5mg Aspen", "Folic acid", "Tablet", "5mg", "S0"),
    ("900890001", "Ferrous Sulphate 200mg Cipla", "Ferrous sulphate", "Tablet", "200mg", "S0"),
    ("903567001", "Vitamin B12 1000mcg Hexal", "Cyanocobalamin", "Tablet", "1000mcg", "S0"),
    ("906234001", "Calcium+Vitamin D3 600mg/400IU Aspen", "Calcium/Colecalciferol", "Tablet", "600mg/400IU", "S0"),
    ("908890001", "Vitamin D3 1000IU Mylan", "Colecalciferol", "Capsule", "1000IU", "S0"),

    # ── Anticoagulants / Antiplatelets ───────────────────────────────────────
    ("911567001", "Warfarin 1 Aspen", "Warfarin sodium", "Tablet", "1mg", "S3"),
    ("911567002", "Warfarin 2 Aspen", "Warfarin sodium", "Tablet", "2mg", "S3"),
    ("911567003", "Warfarin 5 Aspen", "Warfarin sodium", "Tablet", "5mg", "S3"),
    ("914234001", "Aspirin 75 Cipla Low Dose", "Acetylsalicylic acid", "Tablet", "75mg", "S0"),
    ("916890001", "Clopidogrel 75 Mylan", "Clopidogrel bisulphate", "Tablet", "75mg", "S3"),
    ("919567001", "Rivaroxaban 20 Bayer", "Rivaroxaban", "Tablet", "20mg", "S4"),
    ("919567002", "Apixaban 5 Pfizer", "Apixaban", "Tablet", "5mg", "S4"),

    # ── Contraceptives ───────────────────────────────────────────────────────
    ("922234001", "Norethisteron/Ethinylestradiol 0.35/0.035mg Cipla", "Norethisterone/EE", "Tablet", "0.35/0.035mg", "S3"),
    ("924890001", "Levonorgestrel/Ethinylestradiol 0.15/0.03mg Aspen", "Levonorgestrel/EE", "Tablet", "0.15/0.03mg", "S3"),
    ("927567001", "Medroxyprogesterone 150mg Pfizer Depo", "Medroxyprogesterone acetate", "Injection", "150mg/ml", "S4"),
]


async def seed_nappi():
    from sqlalchemy import select, func as sa_func
    async with AsyncSessionLocal() as db:
        added = 0
        for nappi_code, product_name, generic_name, dosage_form, strength, schedule in NAPPI_CODES:
            exists = (await db.execute(
                select(NappiCode).where(NappiCode.nappi_code == nappi_code)
            )).scalar_one_or_none()
            if not exists:
                db.add(NappiCode(
                    nappi_code=nappi_code,
                    product_name=product_name,
                    generic_name=generic_name,
                    dosage_form=dosage_form,
                    strength=strength,
                    schedule=schedule,
                    is_active=True,
                ))
                added += 1

        await db.commit()
        print(f"  NAPPI codes: {added} seeded ({len(NAPPI_CODES)} total in dataset)")


if __name__ == "__main__":
    asyncio.run(seed_nappi())
