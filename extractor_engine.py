import os, re, json
from datetime import datetime
from typing import Dict, Optional, Tuple, Any, List
from dataclasses import dataclass
from collections import defaultdict
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

load_dotenv(find_dotenv(), override=False)

# Konfigurasi Moonshot/Kimi API
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
MODEL = os.getenv("LLM_MODEL", "moonshot-v1-32k")

@dataclass
class ExtractionResult:
    value: Any
    confidence: float
    source: str

class BaseExtractor:
    def __init__(
        self,
        text: str,
        template_path: str,
        verbose: bool = True,
        llm_fields: Optional[List[str]] = None,
    ):
        self.raw_text = text
        self.text = self._preprocess_text(text)
        self.data = self._init_structure()

        self.sections = self._split_sections(self.text)
        self.verbose = verbose
        # Jika diisi, hanya field LLM di daftar ini yang akan diekstrak via LLM
        self.llm_fields = llm_fields

        # Placeholder: Inisialisasi model IndoBERT jika ada
        # self.ner_model = IndoBERT_NER_Model()

        self.rules = {}
        if template_path:
            with open(template_path, 'r', encoding='utf-8') as f:
                self.rules =  json.load(f)

    def _preprocess_text(self, text: str) -> str:
        """
        Improved text preprocessing that preserves context
        
        v1.0 problem: Aggressive cleaning removed important context
        v2.0 fix: Smarter cleaning that keeps structure
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Keep lines with substance
            if len(line) > 2:
                cleaned_lines.append(line)
            # Keep single chars if surrounded by meaningful content
            elif len(line) == 1 and i > 0 and i < len(lines) - 1:
                if len(lines[i-1].strip()) > 3 and len(lines[i+1].strip()) > 3:
                    cleaned_lines.append(line)
        
        # Join with newlines to preserve structure
        text = '\n'.join(cleaned_lines)
        
        # Normalize whitespace but keep newlines
        text = re.sub(r' +', ' ', text)
        
        return text
    
    def _init_structure(self) -> Dict:
        """Initialize enhanced data structure with confidence tracking"""
        return {
            "case_id": None,
            "what": {},
            "when": {},
            "where": {},
            "who": {},
            "why": {},
            "how_much": {},
            "how_many": {},
            "metadata": {
                "extraction_version": "2.0",
                "extraction_date": datetime.now().isoformat(),
                "confidence_scores": {}
            }
        }
    
    def _split_sections(self, text) -> dict:
        """
        Bagi dokumen menjadi beberapa bagian besar:
        - header   : pembukaan + identitas + penahanan
        - body     : duduk perkara & pertimbangan
        - footer   : amar putusan (MENGADILI/MEMUTUSKAN)
        - dakwaan  : jika ada bagian DAKWAAN yang eksplisit

        Heuristik dibuat lebih fleksibel agar tahan terhadap variasi format,
        dengan fallback berbasis persentase panjang dokumen jika marker tidak ditemukan.
        """
        text_len = len(text)

        # -----------------------------------------
        # 1. Tentukan awal BODY (duduk perkara / menimbang)
        # -----------------------------------------
        body_markers = [
            r"\n\s*TENTANG\s+DUDUK\s+PERKARA",
            r"\n\s*DUDUK\s+PERKARA",
            r"\n\s*PERTIMBANGAN\s+HUKUM",
            r"\n\s*PERTIMBANGAN\s+HUKUM\s+MAJELIS\s+HAKIM",
            r"\n\s*Menimbang\s*,",
            r"\n\s*MENIMBANG\s*,",
        ]

        body_start_idx = None
        for pat in body_markers:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                idx = m.start()
                if body_start_idx is None or idx < body_start_idx:
                    body_start_idx = idx

        # Fallback: jika tidak ada marker, pakai ~25% panjang teks sebagai awal body
        if body_start_idx is None:
            body_start_idx = int(text_len * 0.25)

        # -----------------------------------------
        # 2. Tentukan awal FOOTER (amar putusan)
        # -----------------------------------------
        footer_markers = [
            r"\n\s*AMAR\s+PUTUSAN",
            r"\n\s*MENGADILI\s*:",
            r"\n\s*MENGADILI\s*,",
            r"\n\s*MENGADILI\s*\n",
            r"\n\s*MEMUTUSKAN\s*,",
            r"\n\s*MEMUTUSKAN\s*\n",
            r"\n\s*M\s*E\s*N\s*G\s*A\s*D\s*I\s*L\s*I\s*:",
            r"\n\s*M\s*E\s*N\s*G\s*A\s*D\s*I\s*L\s*I\s*,",
        ]

        footer_start_idx = None
        search_region = text[body_start_idx:]
        for pat in footer_markers:
            m = re.search(pat, search_region, re.IGNORECASE)
            if m:
                idx = body_start_idx + m.start()
                if footer_start_idx is None or idx < footer_start_idx:
                    footer_start_idx = idx

        # Fallback: jika tidak ada marker footer, pakai ~70% panjang teks
        if footer_start_idx is None:
            footer_start_idx = int(text_len * 0.7)

        # Pastikan indeks terurut dan dalam rentang
        body_start_idx = max(0, min(body_start_idx, text_len))
        footer_start_idx = max(body_start_idx, min(footer_start_idx, text_len))

        header_text = text[:body_start_idx]
        body_text = text[body_start_idx:footer_start_idx]
        footer_text = text[footer_start_idx:]

        # -----------------------------------------
        # 3. Potong HEADER menjadi identitas & penahanan (jika memungkinkan)
        # -----------------------------------------
        identitas_start = re.search(
            r"(?:perkara\s+Terdakwa|perkara\s+Para\s+Terdakwa|perkara\s+Terdakwa\s*:|:)\s*",
            header_text,
            re.IGNORECASE,
        )
        penahanan_start = re.search(
            r"(Terdakwa\s+ditahan|Para\s+Terdakwa\s+ditahan|Terdakwa\s+ditangkap|Terdakwa\s+berada\s+dalam\s+tahanan)",
            header_text,
            re.IGNORECASE,
        )

        identitas_text = ""
        penahanan_text = ""

        if identitas_start:
            start_idx = identitas_start.end()
            end_idx = penahanan_start.start() if penahanan_start else len(header_text)
            identitas_text = header_text[start_idx:end_idx].strip()

        if penahanan_start:
            penahanan_text = header_text[penahanan_start.start():].strip()
        else:
            # Jika tidak ada blok penahanan eksplisit, treat seluruh header sebagai identitas
            identitas_text = header_text

        # -----------------------------------------
        # 4. Coba ekstrak bagian DAKWAAN jika tertulis eksplisit
        # -----------------------------------------
        dakwaan_match = re.search(
            r"(DAKWAAN\s*:?.*?)(?=\n\s*Menimbang\s*,|\n\s*MENGADILI\b|\n\s*AMAR\s+PUTUSAN\b)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        dakwaan_section = dakwaan_match.group(1).strip() if dakwaan_match else ""

        # -----------------------------------------
        # 5. Coba ekstrak bagian BARANG BUKTI (Hemat Token)
        # -----------------------------------------
        # Mencari blok barang bukti di dalam body untuk mengurangi token saat ekstraksi evidence_items
        evidence_match = re.search(
            r"(?:menetapkan\s+)?barang\s+bukti\s*(?:berupa|adalah|yang\s+diajukan)?\s*[:\.]?.*?(?=\n\s*(?:MENGADILI|Mengingat|Menimbang|Membebankan|Demikianlah))",
            body_text,
            re.DOTALL | re.IGNORECASE
        )
        evidence_section = evidence_match.group(0).strip() if evidence_match else ""

        # -----------------------------------------
        # 6. Coba ekstrak bagian FACTORS (Memberatkan/Meringankan)
        # -----------------------------------------
        # Bagian ini selalu ada di akhir body, sebelum Mengingat/Memutuskan.
        # Kita cari dengan regex, jika gagal, ambil 4000 karakter TERAKHIR dari body.
        factors_match = re.search(
            r"(?:Keadaan|Hal-hal)\s+yang\s+(?:memberatkan|meringankan)[\s\S]*?(?=\n\s*(?:Mengingat|MENGADILI|MEMUTUSKAN|Menetapkan|Demikianlah))",
            body_text,
            re.IGNORECASE
        )
        
        if factors_match:
            factors_section = factors_match.group(0).strip()
        else:
            # Fallback: ambil 4000 karakter terakhir dari body (safe zone untuk putusan panjang)
            factors_section = body_text[-4000:] if len(body_text) > 4000 else body_text

        return {
            "header": header_text,
            "identitas": identitas_text,
            "penahanan": penahanan_text,
            "body": body_text,
            "footer": footer_text,
            "full": text,
            "dakwaan": dakwaan_section,
            "evidence": evidence_section,
            "factors": factors_section,
        }

    
    def _add_field(self, category: str, field: str, value: Any, 
                   confidence: float = 1.0, source: str = "regex"):
        """Add field with confidence tracking, auto-create category if missing"""
        if category not in self.data:
            self.data[category] = {}
            
        if value is not None:
            self.data[category][field] = value
            self.data["metadata"]["confidence_scores"][f"{category}.{field}"] = {
                "confidence": confidence,
                "source": source
            }
    
    def log(self, message: str):
        """Log extraction progress"""
        if self.verbose:
            print(message)

    def _standardize_date(self, date_str: str) -> str:
        """Helper untuk mengubah format '15 Januari 2019' jadi '2019-01-15'"""
        months = {
            'januari': '01', 'februari': '02', 'maret': '03', 'april': '04',
            'mei': '05', 'juni': '06', 'juli': '07', 'agustus': '08',
            'september': '09', 'oktober': '10', 'november': '11', 'desember': '12'
        }
        match = re.search(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})', str(date_str), re.IGNORECASE)
        if match:
            day = match.group(1).zfill(2)
            month_name = match.group(2).lower()
            year = match.group(3)
            month = months.get(month_name, "01")
            return f"{year}-{month}-{day}"
        return date_str
    
    def _apply_dynamic_anchor(self, text: str, start_pattern: str, end_pattern: str=None) -> str:
        if not start_pattern:
            return text
        
        start_match = re.search(start_pattern, text, re.IGNORECASE | re.DOTALL)
        if not start_match:
            return text
        
        start_idx = start_match.start()

        if end_pattern:
            end_match = re.search(end_pattern, text[start_idx:], re.IGNORECASE | re.DOTALL)
            if end_match:
                end_idx = start_idx + end_match.end()
                return text[start_idx:end_idx].strip()
        
        return text[start_idx:].strip()

    def _call_llm_api(self, prompt: str) -> Optional[str]:
        try:
            if not MOONSHOT_API_KEY:
                self.log(" ⚠️ MOONSHOT_API_KEY belum di-set. Lewati panggilan LLM.")
                return None

            self.log(f" [LLM-DEBUG] Mengirim permintaan ke Model: {MODEL}")
            self.log(f" [LLM-DEBUG] Cuplikan Prompt {prompt[:150]}... [truncated]")

            client = OpenAI(api_key=MOONSHOT_API_KEY, base_url="https://api.moonshot.cn/v1")

            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Anda adalah asisten hukum ahli dan data engineer. "
                            "Tugas Anda mengekstrak informasi spesifik dari putusan pengadilan Indonesia. "
                            "WAJIB kembalikan output DALAM FORMAT JSON YANG VALID. " # <-- Wajib ada untuk Kimi API
                            "Jawab secara singkat, padat, dan persis sesuai instruksi tanpa penjelasan tambahan. "
                            "Ekstrak hanya informasi yang secara eksplisit tertulis dalam teks. "
                            "Jangan melakukan inferensi, generalisasi, atau interpretasi. "
                            "Untuk field berbasis teks, gunakan kutipan langsung dari teks asli."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.1, # Disarankan naikkan ke 0.1 dari 0.0 agar Kimi tidak tersendat saat membuat JSON bersarang
                max_tokens=4096,
                response_format={"type": "json_object"},
            )

            res_text = response.choices[0].message.content.strip()
            self.log(f"      [LLM-DEBUG] Respons Diterima: {res_text[:100]}")
            return res_text

        except Exception as e:
            # Ubah log error agar lebih jelas saat debugging
            self.log(f" ⚠️ Error saat memanggil Moonshot API: {str(e)}")
            return None

    # -------------------------------
    # Helper untuk Regex & LLM
    # -------------------------------

    def _cleanup_value(self, field_name: str, val: Any) -> Any:
        """Normalisasi nilai string & tanggal supaya lebih rapi/deterministik."""
        if isinstance(val, str):
            val = val.replace("\n", " ")
            val = re.sub(r"\s+", " ", val).strip()
            val = val.rstrip(".,;- ")

            if "date" in field_name or "dob" in field_name:
                val = re.sub(r"^tanggal\s+", "", val, flags=re.IGNORECASE)
                val = self._standardize_date(val)
        return val

    def _extract_with_regex(
        self, field_name: str, rule: Dict[str, Any], text_to_process: str
    ) -> Tuple[Optional[Any], float]:
        """Ekstraksi satu field dengan regex + simple confidence scoring."""
        val: Optional[Any] = None
        confidence = 0.0

        is_count_field = "count" in field_name.lower()

        for pattern in rule.get("patterns", []):
            if is_count_field:
                matches = re.findall(pattern, text_to_process, re.IGNORECASE | re.MULTILINE)
                if matches:
                    # Use set to count unique matches, works for strings and tuples
                    val = len(set(matches))
                    confidence = 0.85
                    break
                continue # try next pattern

            match = re.search(pattern, text_to_process, re.IGNORECASE | re.MULTILINE)
            if not match:
                continue
            elif field_name == "detention_credit":
                val = True
                confidence = 0.9
                break
            elif field_name == "prison_term":
                try:
                    years = int(match.group(1)) if match.group(1) else 0
                except (IndexError, ValueError):
                    years = 0
                    
                months = 0
                if len(match.groups()) >= 2 and match.group(2):
                    try:
                        months = int(match.group(2))
                    except ValueError:
                        months = 0
                        
                val = {"years": years, "months": months}
                confidence = 0.95
                break
            else:
                try:
                    val = match.group(1).strip()
                except IndexError:
                    val = match.group(0).strip()

            for sw in rule.get("stop_words", []):
                if isinstance(val, str) and sw in val:
                    val = val.split(sw)[0].strip()

            if isinstance(val, str):
                length = len(val)
                if length < 3:
                    confidence = 0.4
                elif length < 10:
                    confidence = 0.6
                else:
                    confidence = 0.8
            else:
                confidence = 0.7

            break

        return val, confidence

    def _build_llm_batch_prompt(
        self, scope_name: str, scope_text: str, fields_spec: List[Dict[str, Any]]
    ) -> str:
        if len(scope_text) > 60000:
            self.log(f"   ⚠️ [TOKEN-SAVER] Scope '{scope_name}' terlalu panjang ({len(scope_text)} chars). Dipotong ke 60k chars.")
            scope_text = scope_text[:60000] + "\n...[TRUNCATED]..."

        fields_desc_lines: List[str] = []
        json_template_lines: List[str] = ["{"]

        for i, spec in enumerate(fields_spec, start=1):
            fname = spec["name"]
            ftype = spec.get("type", "string")
            desc = spec.get("description", "")
            out_fmt = spec.get("output_format", "text") # Ambil parameter output_format

            fields_desc_lines.append(f"{i}. {fname} ({ftype}): {desc}".strip())

            if ftype == "array":
                if out_fmt == "json":
                    # Petunjuk visual eksplisit agar LLM mengisi array dengan object
                    json_template_lines.append(f'  "{fname}": [ {{ "key": "value" }} ],')
                else:
                    json_template_lines.append(f'  "{fname}": [],')
            elif ftype == "boolean":
                json_template_lines.append(f'  "{fname}": false,')
            else:
                json_template_lines.append(f'  "{fname}": "",')

        if json_template_lines[-1].endswith(","):
            json_template_lines[-1] = json_template_lines[-1].rstrip(",")
        json_template_lines.append("}")

        fields_desc = "\n".join(fields_desc_lines)
        json_template = "\n".join(json_template_lines)

        prompt = f"""
Konteks:
Anda adalah asisten hukum dan data engineer. Tugas Anda mengekstrak informasi terstruktur dari putusan pengadilan Indonesia.
Jawab SELALU dalam bentuk JSON VALID, tanpa teks lain di luar JSON.

Bagian dokumen yang dianalisis (scope = {scope_name}):
\"\"\"{scope_text}\"\"\"

Field yang harus diekstrak:
{fields_desc}

Aturan:
- Jika suatu informasi tidak ditemukan di teks, isi dengan:
  - string  : "" (string kosong)
  - array   : [] (array kosong)
  - boolean : false
- Jangan menambahkan field lain di luar daftar.
- Gunakan bahasa Indonesia apa adanya dari dokumen, jangan parafrase kecuali diperlukan untuk meringkas.

Output:
Kembalikan SATU objek JSON dengan field tepat seperti contoh struktur di bawah ini dan TIDAK ADA teks lain:

{json_template}
"""
        return prompt

    def _coerce_llm_type(self, raw_val: Any, expected_type: str) -> Any:
        """Sesuaikan tipe nilai dari LLM ke tipe yang diharapkan template."""
        if expected_type == "array":
            if raw_val is None:
                return []
            if isinstance(raw_val, list):
                return raw_val
            if isinstance(raw_val, str):
                parts = re.split(r"[;\n]", raw_val)
                cleaned = [p.strip() for p in parts if p.strip()]
                return cleaned
            return [raw_val]

        if expected_type == "boolean":
            if isinstance(raw_val, bool):
                return raw_val
            if isinstance(raw_val, str):
                v = raw_val.strip().lower()
                if v in {"ya", "y", "true", "1"}:
                    return True
                if v in {"tidak", "t", "false", "0"}:
                    return False
            return bool(raw_val)

        if expected_type == "integer":
            if raw_val is None or raw_val == "":
                return 0
            try:
                return int(re.sub(r'[^0-9]', '', str(raw_val)))
            except (ValueError, TypeError):
                return 0

        if raw_val is None:
            return ""
        if isinstance(raw_val, str):
            return raw_val
        return str(raw_val)

    def _parse_llm_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Coba parse string LLM menjadi JSON dengan fallback cari blok {...} pertama."""
        if text is None:
            return None
        
        # Bersihkan markdown backticks dari Kimi API jika ada
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except Exception:
            pass

        # Fallback jika masih ada teks aneh di luar JSON
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None

    def save_sections_to_files(self, base_path_without_ext: str):
        """Menyimpan setiap bagian dokumen ke file .txt terpisah untuk debugging."""
        self.log(f"\n   💾 Menyimpan hasil split dokumen ke file untuk debug...")
        # Dapatkan direktori dari base_path
        output_dir = os.path.dirname(base_path_without_ext)
        file_base_name = os.path.basename(base_path_without_ext)

        for section_name, section_text in self.sections.items():
            output_filename = f"{file_base_name}_section_{section_name}.txt"
            output_path = os.path.join(output_dir, output_filename)
            
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"===== SECTION: {section_name.upper()} =====\n\n")
                    f.write(section_text if section_text.strip() else "[BAGIAN INI KOSONG]")
                self.log(f"      -> Disimpan: {output_filename}")
            except Exception as e:
                self.log(f"      -> ❌ Gagal menyimpan {section_name}: {e}")

    def _extract_with_llm_batch(
        self,
        scope_name: str,
        scope_text: str,
        fields_spec: List[Dict[str, Any]],
    ) -> Dict[str, Tuple[Any, float]]:
        """Panggil LLM sekali untuk beberapa field sekaligus. Return value + confidence per field."""
        if not fields_spec:
            return {}

        prompt = self._build_llm_batch_prompt(scope_name, scope_text, fields_spec)
        raw_response = self._call_llm_api(prompt)
        if raw_response is None:
            self.log("   ⚠️ LLM mengembalikan None untuk batch, lewati semua field batch ini.")
            return {}

        parsed = self._parse_llm_json(raw_response)
        if parsed is None or not isinstance(parsed, dict):
            self.log("   ⚠️ Gagal parse JSON dari respons LLM, lewati batch.")
            return {}

        results: Dict[str, Tuple[Any, float]] = {}
        for spec in fields_spec:
            fname = spec["name"]
            expected_type = spec.get("type", "string")
            raw_val = parsed.get(fname, None)

            coerced = self._coerce_llm_type(raw_val, expected_type)

            if expected_type == "array":
                conf = 0.4 if coerced else 0.1
            elif expected_type == "boolean":
                conf = 0.7
            else:
                conf = 0.7 if coerced not in ("", None) else 0.2

            results[fname] = (coerced, conf)

        return results

    def run_extraction(self):
        """Orkestrasi utama hybrid (regex dulu, lalu LLM batched per-scope)."""

        # 1) Jalankan field berbasis regex
        for field_name, rule in self.rules.items():
            source_type = rule.get("method", "regex")
            if source_type != "regex":
                continue

            category = rule.get("category", "what")
            target_scope = rule.get("scope", "full")
            text_to_process = self.sections.get(target_scope, self.text)

            val, conf = self._extract_with_regex(field_name, rule, text_to_process)
            if val is None:
                self.log(f"   ❌ [REGEX] {field_name}: Tidak ditemukan")
                continue

            val = self._cleanup_value(field_name, val)
            self._add_field(category, field_name, val, confidence=conf, source="regex")
            self.log(f"   ✅ [REGEX] {field_name}: {val} (conf={conf:.2f})")

        llm_by_group: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)

        for field_name, rule in self.rules.items():
            if rule.get("method") != "llm":
                continue

            if self.llm_fields is not None and field_name not in self.llm_fields:
                continue

            target_scope = rule.get("scope", "full")
            anchor_start = rule.get("anchor_start", "")
            anchor_end = rule.get("anchor_end", "")

            group_key = (target_scope, anchor_start, anchor_end)
            llm_by_group[group_key].append(
                {
                    "name": field_name,
                    "type": rule.get("type", "string"),
                    "description": rule.get("description", ""),
                    "category": rule.get("category", "what"),
                    "output_format": rule.get("output_format", "text"),
                    "anchor_start": anchor_start,
                    "anchor_end": anchor_end
                }
            )

        for (scope_name, anchor_start, anchor_end), fields_spec in llm_by_group.items():
            base_text = self.sections.get(scope_name, self.text)
            text_to_process = self._apply_dynamic_anchor(base_text, anchor_start, anchor_end)

            anchor_log = f" | Anchor: '{anchor_start[:20]}...'" if anchor_start else ""
            self.log(
                f"\n Menjalankan LLM batch untuk scope '{scope_name}'{anchor_log} ({len(fields_spec)} field)..."
            )

            llm_input_spec = [
                {
                    "name": f["name"],
                    "type": f["type"],
                    "description": f["description"],
                    "output_format": f.get("output_format", "text")
                }
                for f in fields_spec
            ]

            batch_results = self._extract_with_llm_batch(
                scope_name=scope_name,
                scope_text=text_to_process,
                fields_spec=llm_input_spec,
            )

            for field in fields_spec:
                fname = field["name"]
                category = field["category"]
                if fname not in batch_results:
                    self.log(f" [LLM] {fname}: Tidak ada di respon JSON")
                    continue

                val, conf = batch_results[fname]
                val = self._cleanup_value(fname, val)
                self._add_field(category, fname, val, confidence=conf, source="llm")
                self.log(f" [LLM] {fname}: {val} (conf={conf:.2f})")

        return self.data