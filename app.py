import gzip
import json
import os
import re
import time
from difflib import SequenceMatcher
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

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
    <p>Database 17.438 Soal • Pencarian Teks Instan & Scan Screenshot</p>
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
        item["an"] = norm(item["a"])
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

def match_best_option(bank_answer, screen_options):
    if not screen_options:
        return bank_answer
    ba = norm(bank_answer)
    best_opt = None
    best_sc = 0.0
    for opt in screen_options:
        on = norm(opt)
        if ba == on or ba in on or on in ba:
            return opt
        sc = SequenceMatcher(None, ba, on).ratio()
        if sc > best_sc:
            best_sc = sc
            best_opt = opt
    return best_opt if best_sc >= 0.55 else f"{bank_answer} *(kunci bank soal)*"

def optimize_image(file_obj, max_width=900):
    img = Image.open(file_obj).convert("RGB")
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_h = int(float(img.height) * ratio)
        img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
    return img

@st.cache_data(ttl=3600)
def get_available_models(key):
    client = genai.Client(api_key=key)
    preferred = ["gemini-3.8-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.0-flash"]
    found = []
    try:
        for m in client.models.list():
            name = getattr(m, "name", "").replace("models/", "")
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods and "gemini" in name:
                if not any(x in name for x in ["image", "audio", "tts", "embedding", "2.0", "2.5", "1.5", "pro"]):
                    found.append(name)
    except Exception:
        pass
    ordered = [p for p in preferred if p in found] + [f for f in found if f not in preferred]
    return ordered if ordered else ["gemini-3.8-flash"]

def fast_generate(api_key, contents):
    client = genai.Client(api_key=api_key)
    models_to_try = get_available_models(api_key)
    last_err = None

    for m in models_to_try:
        for attempt in range(2):
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
                return client.models.generate_content(
                    model=m,
                    contents=contents,
                    config=config
                ), m
            except Exception as e:
                err_msg = str(e)
                if "thinking" in err_msg.lower():
                    try:
                        return client.models.generate_content(
                            model=m,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                temperature=0.0
                            )
                        ), m
                    except Exception as e2:
                        last_err = e2
                        err_msg = str(e2)
                else:
                    last_err = e

                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg:
                    time.sleep(1.5)
                    continue
                break
    raise last_err

with st.sidebar:
    st.header("⚙️ Pengaturan Scan Gambar")
    default_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = st.text_input(
        "Gemini API Key (Opsional untuk Scan Screenshot)",
        value=default_key,
        type="password",
        help="Diset di Streamlit Secrets dengan nama GEMINI_API_KEY."
    )
    st.caption(f"Total Bank Soal Aktif: **{len(bank_soal):,}** soal unik.")
    st.divider()
    st.caption("© 2026 **Arshaka** • Alfa Learning Helper")

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
                st.error("Masukkan **Gemini API Key** terlebih dahulu di menu sebelah kiri (sidebar).")
            else:
                with st.spinner("Memindai gambar secara cepat..."):
                    try:
                        images = [optimize_image(f) for f in uploaded_files]

                        prompt = """
                        Baca semua soal pilihan ganda pada gambar ini secara berurutan dari nomor terkecil ke terbesar.
                        Kembalikan HANYA JSON array tanpa teks tambahan:
                        [{"no": 1, "soal": "teks soal", "opsi": ["opsi 1", "opsi 2"], "tebakan_ai": "opsi paling benar jika tidak ada di database"}]
                        """
                        resp, used_model = fast_generate(api_key, [prompt, *images])
                        items = json.loads(resp.text)
                        items.sort(key=lambda x: int(x.get("no", 0)))

                        st.success(f"Selesai! (`{used_model}`)")
                        for it in items:
                            no_q = it.get("no", "-")
                            q_text = it.get("soal", "")
                            opts = it.get("opsi", [])
                            ai_guess = it.get("tebakan_ai", "")

                            matches = search_database(q_text, top_k=1)
                            if matches and matches[0][0] >= 0.55:
                                sc, db_item = matches[0]
                                final_ans = match_best_option(db_item["a"], opts)
                                badge = f"Database {int(sc*100)}%"
                            else:
                                final_ans = ai_guess if ai_guess else "Tidak ditemukan di bank soal"
                                badge = "Analisis AI"

                            st.markdown(f"""
                            <div class="ans-card">
                                <span class="ans-badge">No. {no_q} • {badge}</span>
                                <div class="ans-q">{q_text}</div>
                                <div class="ans-a">✅ {final_ans}</div>
                            </div>
                            """, unsafe_allow_html=True)
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

st.markdown("""
<div class="footer-wm">
    Aplikasi Kunci Jawaban Alfa Learning • Dibuat oleh <b>Arshaka</b>
</div>
""", unsafe_allow_html=True)
