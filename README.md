# Sistem Ekstraksi Informasi Putusan Pengadilan (Hybrid Regex + LLM)

Proyek ini adalah sebuah sistem cerdas untuk mengekstraksi informasi terstruktur dari dokumen putusan pengadilan Indonesia. Sistem ini menggunakan pendekatan *hybrid* yang menggabungkan kecepatan dan presisi **Regular Expressions (Regex)** untuk pola-pola sederhana dengan kemampuan pemahaman konteks dari **Large Language Models (LLM)** seperti model GPT dari OpenAI untuk data yang lebih kompleks.

## Fitur Utama

- **Ekstraksi Hybrid**: Menggunakan Regex untuk data terstruktur (seperti nomor putusan) dan LLM untuk data yang memerlukan pemahaman kontekstual (seperti nama-nama terdakwa dalam kasus multi-terdakwa atau ringkasan pertimbangan hukum).
- **Konfigurasi Fleksibel**: Aturan ekstraksi didefinisikan dalam file JSON (`templates/rules_pn.json`), memudahkan penambahan atau modifikasi field tanpa mengubah kode Python.
- **Segmentasi Dokumen Cerdas**: Secara otomatis membagi dokumen menjadi beberapa bagian logis (`header`, `body`, `footer`, `dakwaan`) untuk pencarian yang lebih fokus dan efisien.
- **Batch Processing LLM**: Mengelompokkan semua permintaan LLM untuk satu bagian dokumen (scope) ke dalam satu panggilan API, menghemat biaya dan waktu.
- **Penanganan Multi-Terdakwa**: Mampu mengekstrak data identitas (nama, gender, alamat, dll.) sebagai array jika terdapat lebih dari satu terdakwa.
- **Skor Kepercayaan**: Setiap data yang diekstrak disertai dengan skor kepercayaan (*confidence score*) dan sumber metodenya (`regex` atau `llm`).

## Prasyarat

- Python 3.8+
- `pip` (Python package installer)
- API Key dari OpenAI

## Instalasi

1.  **Clone repositori ini:**
    ```bash
    git clone <url-repositori-anda>
    cd ingestion-system-v2
    ```

2.  **(Opsional tapi direkomendasikan)** Buat dan aktifkan *virtual environment*:
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependensi yang dibutuhkan:**
    File `requirements.txt` sudah disediakan. Jalankan perintah berikut:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment Variable:**
    Buat file bernama `.env` di direktori utama proyek. Salin dan tempel konten di bawah ini ke dalam file tersebut, lalu ganti dengan API key Anda.
    ```env
    OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    LLM_MODEL="gpt-4.1-mini"
    ```

## Penggunaan

Gunakan skrip `main.py` dari terminal dengan menyediakan path file input dan output.

```bash
python main.py "path/ke/input.txt" "path/ke/output.json"
```

**Contoh:**

```bash
python main.py "data/output/303_PID~SUS_2019_PN_JKT~UTR.txt" "data/output/303_PID~SUS_2019_PN_JKT~UTR.json"
```

- `path/ke/input.txt`: Path ke file teks putusan yang ingin diekstrak.
- `path/ke/output.json`: Path untuk menyimpan hasil ekstraksi dalam format JSON.

## Konfigurasi Aturan (`templates/rules_pn.json`)

File ini adalah jantung dari sistem ekstraksi. Anda dapat mendefinisikan field baru atau memodifikasi yang sudah ada.

#### Struktur Aturan

```json
"nama_field": {
    "category": "kategori_5w1h", // who, what, when, where, why, how_much, how_many
    "method": "regex" | "llm",
    "scope": "header" | "body" | "footer" | "dakwaan" | "full",
    "patterns": ["..."], // Hanya untuk method: regex
    "type": "string" | "integer" | "array" | "boolean", // Hanya untuk method: llm
    "description": "Prompt untuk LLM..." // Hanya untuk method: llm
}
```

#### Contoh Aturan Regex
Mengekstrak nomor putusan dari bagian `header` dokumen.
```json
"case_number": {
    "category": "what",
    "method": "regex",
    "patterns": [
        "(?:PUTUSAN|Nomor|No)\\s*[:\\.]?\\s*(\\d+[\\s\\w\\.]*/[\\s\\w\\.\\-/]+)"
    ],
    "scope": "header"
}
```

#### Contoh Aturan LLM
Mengekstrak nama-nama terdakwa sebagai sebuah array dari bagian `header`.
```json
"defendant_names": {
    "category": "who",
    "method": "llm",
    "scope": "header",
    "type": "array",
    "description": "Ekstrak nama lengkap beserta alias untuk SETIAP terdakwa. Kembalikan sebagai sebuah list/array. Contoh: [\"Ahmad alias Abu Fulan\", \"Budi Santoso\"]"
}
```

## Struktur Proyek

```
.
├── .env                  # Konfigurasi environment (API Key, dll)
├── .gitignore            # File dan direktori yang diabaikan Git
├── extractor_engine.py   # Logika inti mesin ekstraksi
├── main.py               # Skrip utama untuk menjalankan ekstraksi
├── requirements.txt      # Daftar dependensi Python
├── README.md             # File ini
├── data/
│   └── output/           # Direktori untuk hasil ekstraksi (dan contoh input)
└── templates/
    └── rules_pn.json     # File konfigurasi aturan ekstraksi
```

## Contoh Hasil Ekstraksi

Berikut adalah cuplikan dari file JSON yang dihasilkan:

```json
{
    "what": {
        "case_number": "303/Pid. Sus. Teroris/2019/PN Jkt. Utr",
        "court_name": "Pengadilan Negeri Jakarta Utara"
    },
    "who": {
        "defendant_gender": [
            "Laki-laki",
            "Laki-laki"
        ],
        "defendant_names": [
            "Suhendrik Alias Hendrik Bin Samsuli",
            "Haris Alias Aris Bin Surman Alm"
        ]
    },
    "how_many": {
        "defendant_count": 5
    },
    "metadata": {
        "extraction_version": "2.0",
        "extraction_date": "2024-01-01T12:00:00.000000",
        "confidence_scores": {
            "what.case_number": {
                "confidence": 0.8,
                "source": "regex"
            },
            "who.defendant_names": {
                "confidence": 0.4,
                "source": "llm"
            }
        }
    }
}
```