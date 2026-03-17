import os
import json
import pandas as pd

def format_dict_value(d):
    """Mengubah dictionary menjadi string yang rapi: 'Key: Value, Key: Value'"""
    if isinstance(d, dict):
        # Mengambil semua key-value dan menggabungkannya dengan pemisah rapi
        return " | ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in d.items() if v)
    return str(d)

def convert_json_to_excel(input_folder: str, output_excel: str):
    print(f"🔄 Membaca semua file JSON dari folder: {input_folder}...")
    all_rows = []
    json_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.json')]
    
    if not json_files:
        print("⚠️ Tidak ada file JSON ditemukan!")
        return

    for filename in json_files:
        filepath = os.path.join(input_folder, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            flat_row = {"File_Name": filename, "case_id": data.get("case_id", "")}
            categories = ["what", "when", "where", "who", "why", "how_much", "how_many"]
            
            for category in categories:
                cat_data = data.get(category, {})
                for key, value in cat_data.items():
                    col_name = f"{category}_{key}"
                    
                    if isinstance(value, list):
                        # JIKA LIST: Kita cek isinya, jika berisi dict, kita rapikan satu-satu
                        formatted_list = []
                        for item in value:
                            if isinstance(item, dict):
                                formatted_list.append(format_dict_value(item))
                            else:
                                formatted_list.append(str(item))
                        # Gabungkan tiap item dengan line break agar rapi di Excel
                        flat_row[col_name] = "\n---\n".join(formatted_list)
                        
                    elif isinstance(value, dict):
                        # JIKA SINGLE DICT: Langsung rapikan
                        flat_row[col_name] = format_dict_value(value)
                    else:
                        flat_row[col_name] = str(value) if value is not None else ""
            
            all_rows.append(flat_row)
        except Exception as e:
            print(f"❌ Error membaca {filename}: {e}")

    df = pd.DataFrame(all_rows)
    print(f"💾 Menyimpan {len(df)} data ke {output_excel}...")
    
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap Putusan')
    
    print("✅ Berhasil! File Excel sudah jauh lebih rapi.")

if __name__ == "__main__":
    INPUT_JSON_DIR = "data/output"
    OUTPUT_EXCEL_FILE = "rekap_data_terorismeeee3.xlsx"
    convert_json_to_excel(INPUT_JSON_DIR, OUTPUT_EXCEL_FILE)