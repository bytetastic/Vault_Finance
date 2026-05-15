# 💰 Finance Tracker

> 🚧 **Work in Progress** — Die App befindet sich noch in aktiver Entwicklung. Features können sich ändern, Bugs sind möglich.

Eine persönliche Finance-Web-App mit Glassmorphism-Design, gebaut mit Flask + SQLite.  
Entwickelt in PyCharm, deployed via Docker auf dem Raspberry Pi.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📊 Dashboard | Monatsübersicht, Sparquote, Budget-Warnungen, Charts |
| 💸 Transaktionen | Einnahmen & Ausgaben, Filter, Suche, Paginierung |
| 📈 Analytik | Monatstrend, Kategorien-Doughnut, Zeitraum-Wahl |
| 🎯 Budget | Fortschrittsbalken pro Kategorie, Warn-/Gefahrenschwelle |
| 🔁 Wiederkehrend | Regelmäßige Einnahmen & Ausgaben automatisiert |
| 🖼️ Bilder & Emojis | PNG/JPG/GIF/WebP Upload + integrierter Emoji-Picker |
| 📤 Export | CSV & JSON Download aller Transaktionen |
| 🌙 Themes | Dark Mode (Standard) + Light Mode |
| 🔍 OCR | Belege scannen per Bild- oder PDF-Upload (Deutsch) |

---

## 🗂️ Projektstruktur

```
financetracker/
├── run.py                        ← Einstiegspunkt
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
├── .gitignore
│
├── data/                         
│   └── finance.db
│
└── app/
    ├── __init__.py              
    ├── models.py                
    ├── routes.py                
    ├── templates/
    │   ├── base.html            
    │   ├── dashboard.html
    │   ├── transactions.html
    │   ├── analytics.html
    │   ├── budget.html
    │   └── settings.html
    └── static/
        ├── css/style.css
        ├── js/app.js
        └── uploads/            
```

---

## 🖥️ Lokal in PyCharm testen (Windows)

### Voraussetzungen
- Python 3.11+ installiert
- PyCharm installiert

### Einrichten

**1. Virtual Environment erstellen**

In PyCharm: unten rechts → „Add Interpreter" → „Virtualenv Environment" → OK  
Oder im Terminal:
```bash
python -m venv venv
venv\Scripts\activate
```

**2. Abhängigkeiten installieren**
```bash
pip install -r requirements.txt
```

**3. App starten**
```bash
python run.py
```
Oder in PyCharm: Rechtsklick auf `run.py` → „Run 'run'"

**4. Browser öffnen**
```
http://localhost:8844
```

> Die Datenbank (`data/finance.db`) und Upload-Ordner werden beim ersten Start automatisch erstellt.

---

## 🍓 Deployment auf dem Raspberry Pi

### Verbindung via FileZilla (SFTP)

| Feld | Wert |
|---|---|
| Host | `sftp://192.168.178.10` |
| Benutzername | `raspi` |
| Port | `22` |

### Was übertragen?

✅ Alles in `financetracker/` — außer:

| Ausschließen | Grund |
|---|---|
| `venv/` | Docker baut eigenes Environment |
| `data/finance.db` | Datenbank bleibt lokal (außer bewusstes Migrieren) |
| `__pycache__/` | Python-Cache, unnötig |
| `.idea/` | PyCharm-Einstellungen |

### Docker starten (SSH)

```bash
ssh raspi@192.168.178.10
cd /home/raspi/financetracker
docker compose up -d --build
```

**App aufrufen:**
```
http://192.168.178.10:8844
```

---

## 🐳 Docker-Befehle

```bash
# Status prüfen
docker compose ps

# Logs live anzeigen
docker compose logs -f

# Container neustarten
docker compose restart

# Container stoppen
docker compose stop

# Komplett neu bauen (nach größeren Änderungen)
docker compose down --rmi all
docker compose up -d --build
```

---

## 🔄 Update-Workflow

1. Änderungen in PyCharm lokal testen (`python run.py`)
2. Dateien per FileZilla auf den Raspi übertragen
3. Per SSH neu bauen:
   ```bash
   cd /home/raspi/financetracker
   docker compose up -d --build
   ```

---

## 🗄️ Datensicherung

Die Datenbank liegt auf dem Host (nicht im Container):
```
/home/raspi/financetracker/data/finance.db
```
Diese Datei sichern = alle Daten gesichert.

Alternativ aus der App: **Einstellungen → Datenverwaltung → CSV/JSON Export**

---

## 🔌 API-Endpunkte

| Methode | Route | Beschreibung |
|---|---|---|
| GET | `/api/transactions` | Liste (Filter: type, category, date_from, date_to, search, page) |
| POST | `/api/transactions` | Neue Transaktion |
| PUT | `/api/transactions/<id>` | Transaktion bearbeiten |
| DELETE | `/api/transactions/<id>` | Löschen |
| GET | `/api/categories` | Alle Kategorien |
| POST | `/api/categories` | Neue Kategorie |
| PUT | `/api/categories/<id>` | Kategorie bearbeiten |
| DELETE | `/api/categories/<id>` | Kategorie löschen |
| GET | `/api/settings` | Alle Einstellungen |
| POST | `/api/settings` | Einstellungen speichern |
| GET | `/api/analytics?period=6months` | Analytik-Daten |
| GET | `/api/budget-status` | Budget-Status aller Kategorien |
| POST | `/api/upload` | Bild/Sticker hochladen |
| GET | `/api/export?format=csv` | Daten exportieren |

---

## ⚙️ Tech Stack

- **Backend:** Python 3.11, Flask, Flask-SQLAlchemy
- **Datenbank:** SQLite
- **Frontend:** Jinja2, Chart.js, Glassmorphism CSS
- **OCR:** pdfplumber, pytesseract (Deutsch)
- **Deployment:** Docker, Raspberry Pi
- **IDE:** PyCharm
