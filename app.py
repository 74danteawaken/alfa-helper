import gzip
import json
import os
import re
from difflib import SequenceMatcher
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Alfa Learning Helper - Arshaka",
    page_icon="🎯",
    layout="centered"
)

# Custom CSS untuk tampilan mobile-friendly
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #d32f2f 0%, #1565c0 100%);
        padding: 18px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 18px;
    }
    .main-header h2 { margin: 0; font-size: 1.4rem; }
    .main-header p { margin: 4px 0 0 0; font-size: 0.85rem; opacity: 0.9; }
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
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h2>🎯 Alfa Learning Quiz Helper</h2>
    <p>Database 17.438 Soal • Pencarian Teks Instan & Scan Screenshot</p>
</div>
""", unsafe_allow_html=True)

def norm(t):
    t = str(t).lower()
    t = re.sub(r'[_*`.,?!:;()\[\]"']', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

@st.cache_resource
def load_bank_soal():
    with gzip.open("bank_soal.json.gz", "rt", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        item["qn"] = norm(item["q"])
    return data

bank_soal = load_bank_soal()

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
            if token_ratio < 0.45:
                continue
            seq_ratio = SequenceMatcher(None, qn[:140], target[:140]).ratio()
            score = (token_ratio * 0.6) + (seq_ratio * 0.4)
            if score >= 0.50:
                scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

# Sidebar pengaturan API Key untuk fitur scan screenshot
with st.sidebar:
    st.header("⚙️ Pengaturan Scan Gambar")
    default_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "Gemini API Key (Opsional untuk Scan Screenshot)",
        value=default_key,
        type="password",
        help="Dapatkan gratis di aistudio.google.com. Bisa juga diset di Streamlit Secrets dengan nama GEMINI_API_KEY."
    )
    st.caption(f"Total Bank Soal Aktif: **{len(bank_soal):,}** soal unik.")

tab_img, tab_txt = st.tabs(["📸 Scan Screenshot Soal", "🔍 Cari Teks Soal (Offline)"])

with tab_img:
    st.write("Unggah satu atau beberapa screenshot soal ujian sekaligus:")
    uploaded_files = st.file_uploader(
        "Pilih Gambar Screenshot",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True
    )
    if uploaded_files:
        if st.button("🚀 Jawab Semua Soal di Gambar", type="primary", use_container_width=True):
            if not api_key:
                st.error("Masukkan **Gemini API Key** terlebih dahulu di menu sebelah kiri (sidebar) untuk mengaktifkan fitur baca screenshot.")
            else:
                with st.spinner("Membaca screenshot dan mencocokkan dengan 17.438 bank soal..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        images = [Image.open(f) for f in uploaded_files]
                        
                        # Tahap 1: Ekstrak daftar soal & opsi dari gambar
                        extract_prompt = """
                        Ekstrak seluruh soal ujian yang terlihat pada gambar-gambar ini secara berurutan dari nomor soal terkecil hingga terbesar.
                        Kembalikan HANYA JSON array murni tanpa markdown, dengan format:
                        [{"no": 1, "soal": "teks pertanyaan lengkap", "opsi": ["opsi A", "opsi B"]}]
                        """
                        resp_ext = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[extract_prompt, *images],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.1
                            )
                        )
                        extracted_items = json.loads(resp_ext.text)
                        extracted_items.sort(key=lambda x: int(x.get("no", 0)))
                        
                        # Tahap 2: Cari referensi dari database 17.438 soal untuk setiap item
                        context_lines = []
                        for it in extracted_items:
                            no_q = it.get("no")
                            q_text = it.get("soal", "")
                            opts = it.get("opsi", [])
                            matches = search_database(q_text, top_k=3)
                            ref_str = " | ".join([f"[Cocok {int(sc*100)}%] Q: {m['q']} => A: {m['a']}" for sc, m in matches])
                            context_lines.append(
                                f"Nomor {no_q}:\nSoal di layar: {q_text}\nOpsi di layar: {opts}\nReferensi Bank Soal: {ref_str if ref_str else 'Tidak ada kecocokan persis'}"
                            )
                        
                        # Tahap 3: Finalisasi jawaban sesuai opsi di layar
                        final_prompt = f"""
                        Kamu adalah asisten kunci jawaban Alfa Learning.
                        Berdasarkan Referensi Bank Soal di bawah ini, tentukan jawaban yang paling benar untuk setiap nomor soal sesuai opsi yang tersedia di layar.
                        
                        Aturan format keluaran:
                        - Langsung tampilkan daftar nomor urut dari terkecil ke terbesar.
                        - Format per baris: `1. **Teks Opsi Jawaban Benar**`
                        - Jika kunci jawaban di bank soal berlawanan dengan logika umum (soal jebakan), tambahkan catatan singkat dalam kurung di samping jawaban.
                        - Jangan tulis kata pengantar atau penutup.
                        
                        Data Soal & Referensi:
                        {chr(10).join(context_lines)}
                        """
                        resp_final = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=final_prompt,
                            config=types.GenerateContentConfig(temperature=0.1)
                        )
                        st.success("Selesai!")
                        st.markdown(resp_final.text)
                    except Exception as e:
                        st.error(f"Terjadi kesalahan: {e}")

with tab_txt:
    query = st.text_input("Ketik potongan kalimat soal (tanpa perlu API Key):", placeholder="Contoh: kategori beban toko / Close Supervisi / Odner 4")
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
