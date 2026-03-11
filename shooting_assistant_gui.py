import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import shooting_assistant_backend as backend
from PIL import Image, ImageTk
import os

class ShootingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Asystent Strzelecki v1.0")
        self.root.geometry("900x700")
        self.root.configure(bg="#18181b")  # Ciemne tło (Zinc-900)

        # Inicjalizacja bazy danych
        self.db = backend.ShootingAssistantDB()
        self.analyzer = backend.TargetAnalyzer()

        # Stylizacja
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TFrame", background="#18181b")
        self.style.configure("TLabel", background="#18181b", foreground="#f4f4f5", font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=10)

        self.setup_ui()

    def setup_ui(self):
        """Tworzy główny układ okna."""
        # Menu boczne
        self.sidebar = tk.Frame(self.root, bg="#27272a", width=200)
        self.sidebar.pack(side="left", fill="y")

        tk.Label(self.sidebar, text="MENU", font=("Segoe UI", 14, "bold"), bg="#27272a", fg="#f59e0b", pady=20).pack()

        buttons = [
            ("🏠 Dashboard", self.show_dashboard),
            ("🔫 Moja Broń", self.show_firearms),
            ("🎯 Nowa Sesja", self.show_new_session),
            ("📊 Statystyki", self.show_stats)
        ]

        for text, command in buttons:
            btn = tk.Button(self.sidebar, text=text, bg="#3f3f46", fg="white", bd=0, 
                            padx=20, pady=10, anchor="w", font=("Segoe UI", 10),
                            command=command, activebackground="#f59e0b", cursor="hand2")
            btn.pack(fill="x", pady=2)

        # Główny obszar treści
        self.main_content = tk.Frame(self.root, bg="#18181b")
        self.main_content.pack(side="right", fill="both", expand=True, px=20, py=20)

        self.show_dashboard()

    def clear_content(self):
        for widget in self.main_content.winfo_children():
            widget.destroy()

    def show_dashboard(self):
        self.clear_content()
        tk.Label(self.main_content, text="Witaj w Asystencie Strzeleckim", font=("Segoe UI", 20, "bold"), bg="#18181b", fg="white").pack(anchor="w")
        tk.Label(self.main_content, text="Wybierz opcję z menu, aby rozpocząć.", bg="#18181b", fg="#a1a1aa").pack(anchor="w", py=10)
        
        # Panel szybkich statystyk
        stats_frame = tk.Frame(self.main_content, bg="#18181b")
        stats_frame.pack(fill="x", pady=20)
        
        self.create_stat_card(stats_frame, "Ostatnia sesja", "Brak danych")
        self.create_stat_card(stats_frame, "Amunicja", "Sprawdź stan")

    def create_stat_card(self, parent, title, value):
        card = tk.Frame(parent, bg="#27272a", padx=20, pady=20, highlightbackground="#3f3f46", highlightthickness=1)
        card.pack(side="left", padx=10, expand=True, fill="both")
        tk.Label(card, text=title, bg="#27272a", fg="#a1a1aa", font=("Segoe UI", 10)).pack()
        tk.Label(card, text=value, bg="#27272a", fg="#f59e0b", font=("Segoe UI", 16, "bold")).pack(py=5)

    def show_firearms(self):
        self.clear_content()
        tk.Label(self.main_content, text="Twoja Broń", font=("Segoe UI", 18, "bold"), bg="#18181b", fg="white").pack(anchor="w")
        
        # Lista broni z bazy
        list_frame = tk.Frame(self.main_content, bg="#18181b")
        list_frame.pack(fill="both", expand=True, py=20)
        
        firearms = self.db.get_firearms()
        if not firearms:
            tk.Label(list_frame, text="Nie dodano jeszcze żadnej broni.", bg="#18181b", fg="#71717a").pack()
        else:
            for f in firearms:
                f_card = tk.Frame(list_frame, bg="#27272a", pady=10, px=10)
                f_card.pack(fill="x", pady=5)
                tk.Label(f_card, text=f"{f[1]} {f[2]}", bg="#27272a", fg="white", font=("Segoe UI", 11, "bold")).pack(side="left")
                tk.Label(f_card, text=f"Kaliber: {f[3]}", bg="#27272a", fg="#a1a1aa").pack(side="right")

        # Przycisk dodawania
        tk.Button(self.main_content, text="+ Dodaj nową broń", bg="#16a34a", fg="white", 
                  font=("Segoe UI", 10, "bold"), command=self.add_firearm_popup).pack(pady=20)

    def add_firearm_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("Dodaj broń")
        popup.geometry("300x400")
        popup.configure(bg="#27272a")

        tk.Label(popup, text="Marka:", bg="#27272a", fg="white").pack(py=5)
        brand_e = tk.Entry(popup)
        brand_e.pack()

        tk.Label(popup, text="Model:", bg="#27272a", fg="white").pack(py=5)
        model_e = tk.Entry(popup)
        model_e.pack()

        tk.Label(popup, text="Kaliber:", bg="#27272a", fg="white").pack(py=5)
        caliber_e = tk.Entry(popup)
        caliber_e.pack()

        def save():
            self.db.add_firearm(brand_e.get(), model_e.get(), caliber_e.get())
            popup.destroy()
            self.show_firearms()

        tk.Button(popup, text="Zapisz", command=save, bg="#f59e0b").pack(py=20)

    def show_new_session(self):
        self.clear_content()
        tk.Label(self.main_content, text="Nowa Sesja Strzelecka", font=("Segoe UI", 18, "bold"), bg="#18181b", fg="white").pack(anchor="w")
        
        # Wybór obrazu
        tk.Button(self.main_content, text="📁 Wybierz zdjęcie tarczy", command=self.analyze_target_ui).pack(pady=20)
        
        self.result_label = tk.Label(self.main_content, text="", bg="#18181b", fg="#f59e0b", font=("Segoe UI", 12))
        self.result_label.pack(py=10)

    def analyze_target_ui(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if file_path:
            shots = self.analyzer.detect_shots_from_image(file_path)
            if shots:
                res = self.analyzer.analyze(shots, 25)
                self.result_label.config(text=f"Sukces! Wykryto {len(shots)} strzałów.\nRozrzut: {res['group_mm']} mm\nTrener: {res['advice']}")
                messagebox.showinfo("Analiza zakończona", "Podgląd został zapisany w pliku wynik_analizy.jpg")
            else:
                messagebox.showwarning("Błąd", "Nie wykryto przestrzelin na tym zdjęciu.")

    def show_stats(self):
        self.clear_content()
        tk.Label(self.main_content, text="Statystyki i Historia", font=("Segoe UI", 18, "bold"), bg="#18181b", fg="white").pack(anchor="w")
        tk.Label(self.main_content, text="Moduł w trakcie budowy...", bg="#18181b", fg="#71717a").pack(py=20)

if __name__ == "__main__":
    root = tk.Tk()
    app = ShootingApp(root)
    root.mainloop()
