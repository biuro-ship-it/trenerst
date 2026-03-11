import streamlit as st
import sqlite3
import json
import math
import os
import cv2
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List
from PIL import Image

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="Asystent Strzelecki",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- STYLIZACJA ---
st.markdown("""
    <style>
    .main { background-color: #18181b; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #f59e0b; color: white; border: none; }
    .stButton>button:hover { background-color: #d97706; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- MODELE DANYCH ---
@dataclass
class Shot:
    x: float
    y: float

class ShootingAssistantDB:
    def __init__(self, db_name="shooting_assistant.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('CREATE TABLE IF NOT EXISTS firearms (id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, model TEXT, caliber TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, firearm_id INTEGER, date TEXT, range_fee REAL, total_shots INTEGER DEFAULT 0)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS targets (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, distance_m INTEGER, score INTEGER, group_size_mm REAL, moa REAL, analysis_result TEXT, shots_json TEXT, image_path TEXT)')
        self.conn.commit()

    def add_firearm(self, brand, model, caliber):
        self.cursor.execute("INSERT INTO firearms (brand, model, caliber) VALUES (?, ?, ?)", (brand, model, caliber))
        self.conn.commit()

    def get_firearms(self):
        self.cursor.execute("SELECT * FROM firearms")
        return self.cursor.fetchall()

    def create_session(self, firearm_id, range_fee):
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cursor.execute("INSERT INTO sessions (firearm_id, date, range_fee) VALUES (?, ?, ?)", (firearm_id, date_str, range_fee))
        self.conn.commit()
        return self.cursor.lastrowid

    def add_target(self, session_id, distance, score, group, moa, analysis, shots):
        shots_json = json.dumps([{"x": s.x, "y": s.y} for s in shots])
        self.cursor.execute('''INSERT INTO targets (session_id, distance_m, score, group_size_mm, moa, analysis_result, shots_json)
                               VALUES (?, ?, ?, ?, ?, ?, ?)''', (session_id, distance, score, group, moa, analysis, shots_json))
        self.cursor.execute("UPDATE sessions SET total_shots = total_shots + ? WHERE id = ?", (len(shots), session_id))
        self.conn.commit()

# --- ANALIZA OBRAZU ---
class TargetAnalyzer:
    @staticmethod
    def detect_shots(image_bytes):
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None: return [], None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        shots = []
        h, w = gray.shape
        cx_img, cy_img = w // 2, h // 2
        px_to_mm = 0.5
        
        output_img = img.copy()
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 10 < area < 50000:
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    cv2.circle(output_img, (cX, cY), 15, (0, 255, 0), 3)
                    shots.append(Shot((cX - cx_img) * px_to_mm, (cy_img - cY) * px_to_mm))
        
        return shots, output_img

    @staticmethod
    def analyze_group(shots, distance_m):
        if not shots: return None
        max_dist = 0
        sx, sy = 0, 0
        for i in range(len(shots)):
            sx += shots[i].x; sy += shots[i].y
            for j in range(i + 1, len(shots)):
                d = math.sqrt((shots[i].x - shots[j].x)**2 + (shots[i].y - shots[j].y)**2)
                max_dist = max(max_dist, d)
        
        avg_x, avg_y = sx / len(shots), sy / len(shots)
        moa = (max_dist / 29.08) / (distance_m / 100) if distance_m > 0 else 0
        
        advice = "DOBRA GRUPA!"
        if avg_y < -30: advice = "NISKO: Płynniej ściągaj spust."
        elif avg_y > 30: advice = "WYSOKO: Nie walcz z odrzutem."
        
        return {"group": round(max_dist, 2), "moa": round(moa, 2), "advice": advice}

# --- APLIKACJA ---
def main():
    db = ShootingAssistantDB()
    analyzer = TargetAnalyzer()

    st.sidebar.title("🎯 Asystent Strzelecki")
    menu = st.sidebar.radio("Nawigacja", ["Dashboard", "Moja Broń", "Nowa Sesja", "Historia"])

    if menu == "Dashboard":
        st.title("Witaj w Asystencie Strzeleckim")
        st.info("Wybierz 'Nowa Sesja' w menu po lewej, aby przeanalizować tarczę.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Zarejestrowana broń", len(db.get_firearms()))
        with col2:
            st.metric("Ostatni wynik", "96/100")

    elif menu == "Moja Broń":
        st.header("Zarządzanie Bronią")
        with st.form("add_gun"):
            brand = st.text_input("Marka")
            model = st.text_input("Model")
            caliber = st.text_input("Kaliber")
            if st.form_submit_button("Dodaj do bazy"):
                db.add_firearm(brand, model, caliber)
                st.success(f"Dodano: {brand} {model}")
        
        st.subheader("Twój arsenał")
        for f in db.get_firearms():
            st.text(f"ID: {f[0]} | {f[1]} {f[2]} | Kaliber: {f[3]}")

    elif menu == "Nowa Sesja":
        st.header("Nowa Sesja i Analiza Tarczy")
        firearms = db.get_firearms()
        if not firearms:
            st.warning("Najpierw dodaj broń w zakładce 'Moja Broń'.")
            return

        gun_options = {f"{f[1]} {f[2]}": f[0] for f in firearms}
        selected_gun = st.selectbox("Wybierz broń", list(gun_options.keys()))
        dist = st.slider("Dystans (metry)", 5, 100, 25)
        
        uploaded_file = st.file_uploader("Wgraj zdjęcie tarczy", type=['jpg', 'jpeg', 'png'])
        
        if uploaded_file is not None:
            bytes_data = uploaded_file.getvalue()
            shots, processed_img = analyzer.detect_shots(bytes_data)
            
            if shots:
                res = analyzer.analyze_group(shots, dist)
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.image(processed_img, caption="Wykryte przestrzeliny", use_container_width=True)
                with col2:
                    st.success(f"Wykryto {len(shots)} strzałów!")
                    st.write(f"**Rozrzut:** {res['group']} mm")
                    st.write(f"**Skupienie:** {res['moa']} MOA")
                    st.warning(f"**Porada Trenera:** {res['advice']}")
                    
                    if st.button("Zapisz wynik sesji"):
                        sid = db.create_session(gun_options[selected_gun], 0)
                        db.add_target(sid, dist, len(shots)*9, res['group'], res['moa'], res['advice'], shots)
                        st.balloons()
            else:
                st.error("Nie wykryto przestrzelin. Spróbuj innego zdjęcia.")

    elif menu == "Historia":
        st.header("Historia Twoich strzelań")
        st.write("Moduł statystyk w przygotowaniu...")

if __name__ == "__main__":
    main()
