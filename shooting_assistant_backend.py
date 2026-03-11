import sqlite3
import json
import math
import os
import cv2
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Shot:
    """Klasa reprezentująca pojedynczą przestrzelinę na tarczy."""
    x: float  # Współrzędna X w mm (relatywna do środka)
    y: float  # Współrzędna Y w mm (relatywna do środka)

class ShootingAssistantDB:
    """Klasa zarządzająca bazą danych SQLite dla Asystenta Strzeleckiego."""
    
    def __init__(self, db_name="shooting_assistant.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Tworzy strukturę tabel w bazie danych, jeśli nie istnieją."""
        # Tabela broni
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS firearms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT,
                model TEXT,
                caliber TEXT NOT NULL
            )
        ''')
        
        # Tabela sesji treningowych
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firearm_id INTEGER,
                date TEXT,
                range_fee REAL,
                total_shots INTEGER DEFAULT 0,
                FOREIGN KEY (firearm_id) REFERENCES firearms (id)
            )
        ''')
        
        # Tabela wyników na tarczach
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                distance_m INTEGER,
                score INTEGER,
                group_size_mm REAL,
                moa REAL,
                analysis_result TEXT,
                shots_json TEXT,
                image_path TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        ''')
        self.conn.commit()

    def add_firearm(self, brand, model, caliber):
        self.cursor.execute("INSERT INTO firearms (brand, model, caliber) VALUES (?, ?, ?)", 
                            (brand, model, caliber))
        self.conn.commit()
        print(f"\n✅ Dodano broń: {brand} {model}")

    def create_session(self, firearm_id, range_fee):
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cursor.execute("INSERT INTO sessions (firearm_id, date, range_fee) VALUES (?, ?, ?)", 
                            (firearm_id, date_str, range_fee))
        self.conn.commit()
        return self.cursor.lastrowid

    def add_target_to_db(self, session_id, distance, score, group, moa, analysis, shots, img_path):
        shots_json = json.dumps([{"x": s.x, "y": s.y} for s in shots])
        self.cursor.execute('''
            INSERT INTO targets (session_id, distance_m, score, group_size_mm, moa, analysis_result, shots_json, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, distance, score, group, moa, analysis, shots_json, img_path))
        
        # Aktualizacja liczby strzałów w sesji
        self.cursor.execute("UPDATE sessions SET total_shots = total_shots + ? WHERE id = ?", 
                            (len(shots), session_id))
        self.conn.commit()

    def get_firearms(self):
        self.cursor.execute("SELECT id, brand, model, caliber FROM firearms")
        return self.cursor.fetchall()

class TargetAnalyzer:
    """Moduł analizy obrazu przy użyciu OpenCV."""

    @staticmethod
    def detect_shots_from_image(image_path: str) -> List[Shot]:
        """Wykrywa przestrzeliny na zdjęciu za pomocą progowania adaptacyjnego i konturów."""
        if not os.path.exists(image_path):
            print(f"❌ BŁĄD: Plik '{image_path}' nie istnieje!")
            return []

        img = cv2.imread(image_path)
        if img is None:
            print("❌ BŁĄD: Nie można otworzyć obrazu.")
            return []

        # Przetwarzanie obrazu
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Automatyczne progowanie metodą Otsu (wykrywanie ciemnych obiektów)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Znajdowanie konturów
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        shots = []
        height, width = gray.shape
        center_x, center_y = width // 2, height // 2
        px_to_mm = 0.5  # Skala testowa (1px = 0.5mm)

        debug_img = img.copy()

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filtrowanie szumu i zbyt dużych obiektów
            if 10 < area < 50000:
                M = cv2.moments(cnt)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    
                    # Rysowanie wyniku na kopii obrazu
                    cv2.circle(debug_img, (cX, cY), 10, (0, 255, 0), 2)
                    
                    # Obliczanie współrzędnych relatywnych do środka obrazu
                    rel_x = (cX - center_x) * px_to_mm
                    rel_y = (center_y - cY) * px_to_mm
                    shots.append(Shot(rel_x, rel_y))

        # Zapis podglądu analizy
        cv2.imwrite("wynik_analizy.jpg", debug_img)
        return shots

    @staticmethod
    def analyze(shots: List[Shot], distance_m):
        """Analizuje parametry grupy strzałów i generuje porady."""
        if not shots: return None
        
        max_dist = 0
        sum_x, sum_y = 0, 0
        
        for i in range(len(shots)):
            sum_x += shots[i].x
            sum_y += shots[i].y
            for j in range(i + 1, len(shots)):
                d = math.sqrt((shots[i].x - shots[j].x)**2 + (shots[i].y - shots[j].y)**2)
                max_dist = max(max_dist, d)
        
        cx, cy = sum_x / len(shots), sum_y / len(shots)
        moa = (max_dist / 29.08) / (distance_m / 100) if distance_m > 0 else 0
        
        # Logika "Wirtualnego Trenera"
        advice = "DOBRA GRUPA. Skup się na powtarzalności chwytu."
        if cy < -30: 
            advice = "NISKO: Prawdopodobne 'zrywanie' języka spustowego. Ściągaj spust płynniej."
        elif cy > 30: 
            advice = "WYSOKO: Oczekiwanie na odrzut (pchanie broni barkiem przed strzałem)."
        elif abs(cx) > 30:
            advice = "BŁĄD POZIOMY: Sprawdź stabilność postawy i zgrywanie przyrządów."
        
        return {
            "group_mm": round(max_dist, 2),
            "moa": round(moa, 2),
            "score": len(shots) * 9, # Symulacja punktacji
            "advice": advice
        }

def main_menu():
    """Interfejs użytkownika w terminalu."""
    db = ShootingAssistantDB()
    analyzer = TargetAnalyzer()
    
    while True:
        print("\n--- ASYSTENT STRZELECKI V4.1 ---")
        print("1. Dodaj broń")
        print("2. Pokaż mój sprzęt")
        print("3. NOWA SESJA (Skanowanie zdjęć)")
        print("4. Wyjdź")
        
        choice = input("\nWybierz opcję: ")
        
        if choice == '1':
            db.add_firearm(input("Marka: "), input("Model: "), input("Kaliber: "))
            
        elif choice == '2':
            firearms = db.get_firearms()
            if not firearms:
                print("\nBrak zarejestrowanej broni.")
            else:
                print("\nTWOJA BROŃ:")
                for f in firearms:
                    print(f"ID: {f[0]} | {f[1]} {f[2]} | Kaliber: {f[3]}")
                    
        elif choice == '3':
            firearms = db.get_firearms()
            if not firearms:
                print("❌ Musisz najpierw dodać broń w menu głównym!")
                continue
            
            print("\nWybierz ID broni dla tej sesji:")
            for f in firearms: print(f"{f[0]}. {f[1]} {f[2]}")
            try:
                fid = int(input("ID: "))
                sid = db.create_session(fid, 0)
                print(f"🚀 Sesja #{sid} została utworzona.")
                
                while True:
                    print("\na. Analizuj zdjęcie tarczy")
                    print("b. Zakończ sesję")
                    s_choice = input("Wybierz: ")
                    
                    if s_choice == 'a':
                        img_name = input("Podaj nazwę pliku (np. test.jpg): ")
                        dist = int(input("Dystans w metrach: "))
                        
                        print("🔍 Analizuję obraz...")
                        found_shots = analyzer.detect_shots_from_image(img_name)
                        
                        if found_shots:
                            res = analyzer.analyze(found_shots, dist)
                            db.add_target_to_db(sid, dist, res['score'], res['group_mm'], res['moa'], res['advice'], found_shots, img_name)
                            print(f"\n🎯 WYKRYTO: {len(found_shots)} strzałów.")
                            print(f"📏 Rozrzut: {res['group_mm']} mm / {res['moa']} MOA")
                            print(f"💡 PORADA: {res['advice']}")
                            print("👉 Podgląd detekcji znajdziesz w pliku 'wynik_analizy.jpg'")
                        else:
                            print("❌ Algorytm nie wykrył przestrzelin. Upewnij się, że plik jest w folderze projektu.")
                    
                    elif s_choice == 'b':
                        break
            except ValueError:
                print("❌ Błąd: Podaj prawidłową liczbę.")

        elif choice == '4':
            print("Zamykanie asystenta. Powodzenia na strzelnicy!")
            break

if __name__ == "__main__":
    main_menu()
