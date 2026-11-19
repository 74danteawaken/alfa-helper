import gzip
import json
import re
from difflib import SequenceMatcher
import numpy as np
import streamlit as st
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

st.set_page_config(
    page_title="Alfa Learning Helper - By Arshaka",
    page_icon="🎯",
    layout="centered"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #d32f2f 0%, #1565c0 100%);
        padding: 18px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 18px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .main-header h2 { margin: 0; font-size: 1.4rem; }
    .main-header p { margin: 4px 0 0 0; font-size: 0.85rem; opacity: 0.92; }
    .wm-tag {
        display: inline-block;
        background: rgba(255,255,255,0.2);
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        margin-top: 8px;
    }
    .ans-card {
        background-color: #f8f9fa;
        border-left: 5px solid #1565c0;
        padding: 12px 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .ans-badge {
        display: inline-block;
        background: #e3f2fd;
        color: #0d47a1;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        margin-bottom: 6px;
    }
    .ans-q { font-size: 0.9rem; color: #333; margin-bottom: 6px; }
    .ans-a { font-size: 1rem; font-weight: 700; color: #1b5e20; }
    .footer-wm {
        text-align: center;
        color: #777;
        font-size: 0.78rem;
        margin-top: 32px;
        padding-top: 12px;
        border-top: 1px solid #e0e0e0;
    }
    .floating-wm {
        position: fixed;
        bottom: 10px;
        right: 12px;
        background: rgba(21, 101, 192, 0.88);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.72rem;
        font-weight: 700;
        z-index: 9999;
        pointer-events: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }
</style>
<div class="floating-wm">⚡ By Arshaka</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h2>🎯 Alfa Learning Quiz Helper</h2>
    <p>Database 17.438 Soal • Pencarian Teks & Scan Screenshot Unlimited</p>
    <div class="wm-tag">Created by Arshaka</div>
</div>
""", unsafe_allow_html=True)

def norm(t):
    t = str(t).lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

@st.cache_resource
def load_bank_soal():
    with gzip.open("bank_soal.json.gz", "rt", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        item["qn"] = norm(item["q"])
    return data

@st.cache_resource
def load_ocr():
    return RapidOCR()

bank_soal = load_bank_soal()
ocr_engine = load_ocr()

def search_database(query_text, top_k=5):
    qn = norm(query_text)
    if not qn:
        return []
    tokens = [w for w in qn.split() if len(w) > 2]
    scored = []
    for item in bank_soal:
        target = item["qn"]
        if qn in target:
            score = 0.95 + (len(qn) / max(len(target), 1)) * 0.05
            scored.append((score, item))
            continue
        if tokens:
            hits = sum(1 for tok in tokens if tok in target)
            if hits == 0:
                continue
            token_ratio = hits / len(tokens)
            if token_ratio < 0.40:
                continue
            seq_ratio = SequenceMatcher(None, qn[:140], target[:140]).ratio()
            score = (token_ratio * 0.65) + (seq_ratio * 0.35)
            if score >= 0.48:
                scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

def extract_questions_from_ocr(lines):
    full_text = "\n".join(lines)
    # Pisahkan berdasarkan nomor soal (misal: "1.", "12.", "Soal 1", dsb.)
    blocks = re.split(r'(?:^|\n)\s*(?:soal\s*)?(\d{1,2})\s*[\.\)]\s+', full_text, flags=re.IGNORECASE)
    questions = []
    if len(blocks) >= 3:
        for i in range(1, len(blocks) - 1, 2):
            no_q = blocks[i]
            body = blocks[i + 1].strip()
            # Ambil bagian pertanyaan sebelum opsi a./b./bulatan
            q_part = re.split(r'\n\s*(?:[a-eA-E][\.\)]|[oO0•\-])\s+', body)[0]
            q_clean = re.sub(r'\s+', ' ', q_part).strip()
            if len(q_clean) >= 8:
                questions.append((int(no_q), q_clean))
    if not questions:
        # Fallback: gabungkan seluruh baris teks jika nomor soal terpotong di screenshot
        joined = re.sub(r'\s+', ' ', full_text).strip()
        if joined:
            questions.append((1, joined))
    return questions

tab_img, tab_txt = st.tabs(["📸 Scan Screenshot Soal (Unlimited)", "🔍 Cari Teks Soal"])

with tab_img:
    st.write("Unggah satu atau beberapa screenshot soal ujian sekaligus (tanpa batas kuota):")
    uploaded_files = st.file_uploader(
        "Pilih Gambar Screenshot",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )
    if uploaded_files:
        if st.button("🚀 Jawab Semua Soal di Gambar", type="primary", use_container_width=True):
            with st.spinner("Membaca teks screenshot & mencocokkan database..."):
                all_extracted = []
                for f in uploaded_files:
                    img = Image.open(f).convert("RGB")
                    if img.width > 1000:
                        ratio = 1000 / float(img.width)
                        img = img.resize((1000, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    result, _ = ocr_engine(np.array(img))
                    if result:
                        lines = [item[1] for item in result]
                        all_extracted.extend(extract_questions_from_ocr(lines))

                if not all_extracted:
                    st.warning("Teks pada gambar tidak terbaca. Pastikan gambar tidak terlalu buram.")
                else:
                    all_extracted.sort(key=lambda x: x[0])
                    st.success(f"Ditemukan {len(all_extracted)} soal dari screenshot!")
                    for no_q, q_text in all_extracted:
                        matches = search_database(q_text, top_k=1)
                        if matches:
                            sc, db_item = matches[0]
                            st.markdown(f"""
                            <div class="ans-card">
                                <span class="ans-badge">No. {no_q} • Kemiripan {int(sc*100)}% ({db_item['m']})</span>
                                <div class="ans-q">{db_item['q']}</div>
                                <div class="ans-a">✅ {db_item['a']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="ans-card">
                                <span class="ans-badge">No. {no_q} • Tidak Cocok</span>
                                <div class="ans-q">{q_text}</div>
                                <div class="ans-a">⚠️ Tidak ditemukan di bank soal, coba cari kata kuncinya di tab sebelah.</div>
                            </div>
                            """, unsafe_allow_html=True)

with tab_txt:
    query = st.text_input("Ketik potongan kalimat soal:", placeholder="Contoh: kategori beban toko / Close Supervisi / Odner 4")
    if query:
        results = search_database(query, top_k=8)
        if not results:
            st.warning("Soal tidak ditemukan. Coba gunakan kata kunci yang lebih singkat.")
        else:
            for score, item in results:
                pct = int(score * 100)
                st.markdown(f"""
                <div class="ans-card">
                    <span class="ans-badge">{item['m']} • Kemiripan {pct}%</span>
                    <div class="ans-q">{item['q']}</div>
                    <div class="ans-a">✅ {item['a']}</div>
                </div>
                """, unsafe_allow_html=True)

st.markdown("""
<div class="footer-wm">
    Aplikasi Kunci Jawaban Alfa Learning • Dibuat oleh <b>Arshaka</b>
</div>
""", unsafe_allow_html=True)
