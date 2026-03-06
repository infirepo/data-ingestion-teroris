import re

class DocumentClassifier:
    def __init__(self):
        self.case_number_patterns = {
            "PUTUSAN_PN": r"Nomor[:\s.]*\d+[\s/]*Pid[\.\s-]*Sus[\.\s-]*Teroris[\s/]*\d{4}[\s/]*PN",
            "PUTUSAN_PT": r"Nomor[:\s.]*\d+[\s/]*Pid[\.\s-]*Sus[\s/]*\d{4}[\s/]*PT",
            "PUTUSAN_KASASI": r"Nomor[:\s.]*\d+[\s/]*K[\s/]*Pid[\.\s-]*Sus[\s/]*\d{4}",
            "PUTUSAN_PK": r"Nomor[:\s.]*\d+[\s/]*PK[\s/]*Pid[\.\s-]*Sus[\s/]*\d{4}",
            "PUTUSAN_MILITER": r"Nomor\s*[:\-]?\s*([0-9]+-[A-Z]/PM\s*[A-Z0-9\-]+/[A-Z]+/[IVX]+/[0-9]{4})"
        }

        self.header_phrases = {
            "PUTUSAN_PN": [
                r"Pengadilan\s+Negeri\s+.*?\s+mengadili",
                r"menjatuhkan\s+putusan\s+sebagai\s+berikut",
                r"tingkat\s+pertama"
            ],
            "PUTUSAN_PT": [
                r"Pengadilan\s+Tinggi\s+.*?\s+menerima\s+permintaan\s+banding",
                r"putusan\s+tingkat\s+banding"
            ],
            "PUTUSAN_KASASI": [
                r"Mahkamah\s+Agung\s+.*?\s+pemeriksaan\s+kasasi",
                r"mengadili\s+perkara\s+pidana\s+khusus\s+pada\s+tingkat\s+kasasi"
            ],
            "PUTUSAN_PK" : [
                r"pemeriksaan\s+peninjauan\s+kembali",
                r"memohon\s+pemeriksaan\s+peninjauan\s+kembali",
                r"Terpidana\s+mengajukan\s+permohonan\s+peninjauan\s+kembali"
            ],
            "PUTUSAN_MILITER": [
                r"Pengadilan\\s+Militer(?:\\s+Tinggi)?",
                r"Nomor\\s*[:\\-]?\\s*\\d+\\-[A-Z]/PM"
            ]
        }

    def classify(self, text):
        header_text = text[:4000]
        clean_header = re.sub(r'\s+', ' ', header_text).upper()
        scores = {doc_type: 0 for doc_type in self.case_number_patterns}

        for doc_type, pattern in self.case_number_patterns.items():
            if re.search(pattern, header_text, re.IGNORECASE):
                scores[doc_type] += 10 

        for doc_type, phrases in self.header_phrases.items():
            for phrase in phrases:
                if re.search(phrase, clean_header, re.IGNORECASE):
                    scores[doc_type] += 2

        best_match = max(scores, key=scores.get)
        if scores[best_match] < 2:
            return "UNKNOWN", 0
        
        return best_match, scores[best_match]