import os
import sys
import json
from pathlib import Path

# Tambahkan path direktori saat ini agar module bisa di-import dengan aman
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cleaner import PDFCleaner
from classifier import DocumentClassifier
from extractor_engine import BaseExtractor

def main():
    # ==========================================
    # KONFIGURASI PATH
    # ==========================================
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Folder input: tempat menaruh file PDF mentah
    input_dir = os.path.join(base_dir, "data", "input")
    
    # Folder output: tempat hasil text dan log
    output_dir = os.path.join(base_dir, "data", "output")

    template_dir = os.path.join(base_dir, "templates")

    # Pattern watermark default (untuk deteksi awal)
    watermark_patterns = [
        "Mahkamah Agung",
        "ahkamah",
        "Direktori Putusan",
        "Halaman",
        "Disclaimer",
    ]

    # ==========================================
    # INISIALISASI
    # ==========================================
    # 1. Buat folder jika belum ada
    Path(input_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(template_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" 🚀 INTEGRATION TEST: CLEANER -> CLASSIFIER -> EXTRACTOR")
    print("=" * 60)
    print(f"📂 Input  : {input_dir}")
    print(f"📂 Output : {output_dir}")
    print(f"📂 tEMPLATE : {template_dir}")

    # 2. Load Modules
    try:
        cleaner = PDFCleaner()
        classifier = DocumentClassifier()
        print("✅ Modules loaded successfully.")
    except Exception as e:
        print(f"❌ Gagal memuat module: {e}")
        return

    # 3. Cek File PDF
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
    if not files:
        print("\n⚠️  Tidak ada file PDF di folder input.")
        print(f"   👉 Silakan masukkan file .pdf ke folder: {input_dir}")
        return

    print(f"\n🔄 Memproses {len(files)} file...\n")

    # ==========================================
    # LOOP PROSES
    # ==========================================
    for idx, filename in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] 📄 {filename}")
        
        input_path = os.path.join(input_dir, filename)
        temp_pdf_path = os.path.join(output_dir, f"temp_{filename}")
        
        file_base_name = os.path.splitext(filename)[0]
        output_txt_path = os.path.join(output_dir, f"{file_base_name}.txt")
        output_json_path = os.path.join(output_dir, f"{file_base_name}.json")

        # --- STEP 1: CLEANING (PDF -> TXT) ---
        print("   ├─ 🧹 Cleaning...", end=" ", flush=True)
        cleaning_success = False
        
        try:
            # A. Deteksi watermark
            wm_text = cleaner.detect_watermark(input_path, watermark_patterns)
            
            # B. Hapus watermark & header (PDF Level)
            if cleaner.remove_watermark_and_headers(wm_text, input_path, temp_pdf_path):
                # C. Ekstrak & Bersihkan Teks (Text Level)
                if cleaner.extract_clean_text(temp_pdf_path, output_txt_path):
                    print("✅ Done")
                    cleaning_success = True
                else:
                    print("❌ Failed (Text Extraction)")
            else:
                print("❌ Failed (Watermark Removal)")

        except Exception as e:
            print(f"❌ Error: {e}")
        
        finally:
            # Hapus file temp PDF (opsional, agar tidak memenuhi disk)
            if os.path.exists(temp_pdf_path):
                try:
                    os.remove(temp_pdf_path)
                except:
                    pass

        if not cleaning_success or not os.path.exists(output_txt_path):
            print("   └─ ⏭️  Skip Classification & Extraction")
            print("-" * 50)
            continue

        with open(output_txt_path, "r", encoding="utf-8") as f:
            text_content = f.read()


        print("   ├─ 🏷️  Classifying...", end=" ", flush=True)
        doc_type = "UNKNOWN"
        try:
            doc_type, score = classifier.classify(text_content)
            print(f"✅ {doc_type} (Score: {score})")
        except Exception as e:
            print(f"❌ Error: {e}")

        print("   └─ 🧠 Extracting...", end=" ", flush=True)
        
        if doc_type == "PUTUSAN_PN":
            template_path = os.path.join(template_dir, "rules_pn.json")
        elif doc_type == "PUTUSAN_PK":
            template_path = os.path.join(template_dir, "rules_pk.json")
        elif doc_type == "PUTUSAN_PT":
            template_path = os.path.join(template_dir, "rules_pt.json")
        elif doc_type == "PUTUSAN KASASI":
            template_path = os.path.join(template_dir, "rules_k.json")
        elif doc_type == "PUTUSAN MILITER":
            template_path = os.path.join(template_dir, "rules_pm.json")
        else:
            template_path = os.path.join(template_dir, "rules_pn.json")

        if not os.path.exists(template_path):
            print(f"\n      ❌ Error: Template file {template_path} tidak ditemukan!")
            print("-" * 50)
            continue

        try:
            llm_fields_test = [
                "indictment_model",
                "charged_articles", 
                "proven_offense",   
                "defendants",       
                "co_defendants",    
                "evidence_items",   
                "district_court_date",
                "district_court",
                "defendant_count",
                "evidence_item_count",
                "verdict_per_charge",
                "aggravating_factors",
                "mitigating_factors",
                "defendant_ideology_affiliation",
                "defendant_local_network",
                "has_attack_plan",
                "attack_preparation_activities",
                "attack_plan_summary",
                "radicalization_sources",
                "activity_locations",
                "crime_time_range",
                "reasoning_evidence",
                "reasoning_appeal",
                "motivation_factors",
                "evidence_disposition",
                "appellate_outcome",
                "detention_timeline",
                "appeal_timeline",
                "judges",
                "clerk",
                "prosecutors",
                "defense_counsels",
                "witnesses",
                "arrest_date",
                "arrest_location",
                "investigators",
                "defense_plea",
                "defendant_local_network_joined_at",
                "injury_severity",
                "related_entities",
                "defendant_chat_platform",
            ]

            extractor = BaseExtractor(
                text=text_content,
                template_path=template_path,
                verbose=False, # Set False agar tidak spam log saat proses 100 file
                llm_fields=llm_fields_test,
            )

            # Simpan hasil split sections untuk debugging
            # debug_dir = os.path.join(output_dir, "debug_sections")
            # Path(debug_dir).mkdir(parents=True, exist_ok=True)
            # debug_base_path = os.path.join(debug_dir, file_base_name)
            # extractor.save_sections_to_files(debug_base_path)

            extracted_data = extractor.run_extraction()
            
            with open(output_json_path, "w", encoding="utf-8") as json_file:
                json.dump(extracted_data, json_file, indent=4, ensure_ascii=False)
                
            print(f"✅ Saved to {os.path.basename(output_json_path)}")
            
        except Exception as e:
            print(f"\n      ❌ Error Extracting: {e}")

        print("-" * 50)

    print("\n🏁 Seluruh Proses Selesai.")


if __name__ == "__main__":
    main()