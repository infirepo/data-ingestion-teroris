import os
import json
import pandas as pd

def convert_json_to_excel(input_folder: str, output_excel: str):
    print(f"🔄 Membaca semua file JSON dari folder: {input_folder}...")
    
    all_rows = []
    
    # Ambil semua file berakhiran .json di dalam folder
    json_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.json')]
    
    if not json_files:
        print("⚠️ Tidak ada file JSON ditemukan!")
        return

    for filename in json_files:
        filepath = os.path.join(input_folder, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Dictionary untuk menyimpan 1 baris (row) data excel
            flat_row = {}
            flat_row["File_Name"] = filename
            flat_row["case_id"] = data.get("case_id", "")
            
            # Kategori utama yang ingin kita ekstrak (Abaikan 'metadata' agar Excel tidak penuh)
            categories = ["what", "when", "where", "who", "why", "how_much", "how_many"]
            
            for category in categories:
                cat_data = data.get(category, {})
                for key, value in cat_data.items():
                    # Buat nama kolom Excel, contoh: "what_case_number" atau "who_witnesses"
                    col_name = f"{category}_{key}"
                    
                    if isinstance(value, list):
                        # Jika datanya List (contoh: saksi-saksi), gabungkan pakai titik koma + enter
                        # Agar di Excel bisa dibaca per baris di dalam satu sel
                        flat_row[col_name] = ";\n".join(str(v) for v in value) if value else ""
                    elif isinstance(value, dict):
                        # Jika ada dict di dalam dict (contoh: prison_term: {years: 3, months: 0})
                        # Ubah jadi string JSON
                        flat_row[col_name] = json.dumps(value, ensure_ascii=False)
                    else:
                        # Jika string/angka biasa, langsung masukkan
                        flat_row[col_name] = str(value) if value is not None else ""
            
            all_rows.append(flat_row)
            
        except Exception as e:
            print(f"❌ Error membaca {filename}: {e}")

    # Ubah list of dictionaries menjadi DataFrame Pandas
    df = pd.DataFrame(all_rows)
    
    # Simpan ke Excel
    print(f"💾 Menyimpan {len(df)} data ke {output_excel}...")
    
    # Engine xlsxwriter/openpyxl bisa menangani newline (\n) di dalam sel excel
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap Putusan')
    
    print("✅ Berhasil! File Excel sudah siap.")

if __name__ == "__main__":
    # SESUAIKAN DENGAN NAMA FOLDERMU
    INPUT_JSON_DIR = "data/output"  # Folder tempat 100 json mu tersimpan
    OUTPUT_EXCEL_FILE = "rekap_data_terorisme.xlsx"
    
    convert_json_to_excel(INPUT_JSON_DIR, OUTPUT_EXCEL_FILE)