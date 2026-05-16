# 🏦 Finance Vault

**Deine persönliche Finanzverwaltung – privat, lokal, ohne Cloud.**

Finance Vault läuft vollständig auf deinem eigenen Rechner. Keine Registrierung, keine Cloud, keine Weitergabe deiner Daten. Alles bleibt bei dir.

---

## ❗ Fix die Tage

***- Persönliche Ansprache in der App***

***- Diverse Bugs im Einstellungen Tab***

## ✨ Features

| Bereich | Was du bekommst |
|---|---|
| **Dashboard** | Monatliche Übersicht mit Einnahmen, Ausgaben, Bilanz & Sparquote |
| **Transaktionen** | Erfassen, bearbeiten, filtern & durchsuchen mit Kategorien, Tags, Notizen |
| **CSV-Import** | Automatische Erkennung von DKB, Sparkasse, ING, Commerzbank, N26, Revolut u.v.m. |
| **Budget** | Monatliche Limits pro Kategorie mit Warnungen |
| **Analytik** | Interaktive Charts – Einnahmen/Ausgaben, Kategorien, Verlauf |
| **Sparziele** | Ziele anlegen und Fortschritt verfolgen |
| **Monatsbericht** | Detaillierter PDF-exportierbarer Monatsbericht |
| **Dokumente** | Belege & Rechnungen hochladen und verwalten |
| **Einstellungen** | Kategorien, Schnelleingaben, Sicherheit, Sitzungsdauer |

---


## 📁 Dateistruktur

```
finance-vault/
├── app/
│   ├── static/
│   │   ├── css/          Styles
│   │   ├── js/           JavaScript
│   │   └── uploads/      
│   └── templates/        HTML-Templates
├── data/
│   ├── finance.db        
│   └── documents/        
├── run.py                Startpunkt
└── requirements.txt      Python-Abhängigkeiten
```

---

## 🔐 Sicherheit

- Alle Daten liegen **ausschließlich lokal** auf deinem Rechner
- Passwörter werden mit **bcrypt** (12 Rounds) gehasht
- Brute-Force-Schutz: nach 10 Fehlversuchen 15 Minuten gesperrt
- Session-Timeout konfigurierbar (1 Tag bis nie)
- Für lokalen Heimgebrauch konzipiert – **nicht für öffentliche Server**

### Empfohlene erste Schritte

1. Nach dem ersten Login: **Passwort in den Einstellungen ändern**
2. Optional: Eigenen `SECRET_KEY` als Umgebungsvariable setzen
3. Optional: Port in `run.py` anpassen

---

---

## 🌍 Sprache & Lokalisierung

- **Vollständig auf Deutsch** – alle Monatsnamen, Bezeichnungen, Fehlermeldungen
- Währungssymbol und -position konfigurierbar (€, $, CHF etc.)
- Datumsformat: `DD.MM.YYYY`

---

## 📊 CSV-Import – Unterstützte Banken

| Bank | Export-Pfad |
|---|---|
| **DKB** | Banking → Umsätze → Export (CSV) |
| **Sparkasse** | Kontoumsätze → Exportieren → CSV |
| **ING** | Umsätze → Download (CSV) |
| **Commerzbank** | Umsätze → Export |
| **N26** | Statistiken → CSV Export |
| **Revolut** | Statements → CSV |
| **Volksbank / VR** | Kontoauszüge → Download |
| **Comdirect** | Umsätze → Export |

Andere Banken werden als **generisches CSV** versucht.

---

## ⚙️ Umgebungsvariablen (optional)

| Variable | Standard | Beschreibung |
|---|---|---|
| `SECRET_KEY` | (unsicher) | Flask Secret Key – unbedingt ändern! |
| `VAULT_USER` | `admin` | Standard-Benutzername beim ersten Start |
| `VAULT_PASSWORD` | `vault1234` | Standard-Passwort beim ersten Start |

Beispiel `.env`:
```
SECRET_KEY=dein-langer-zufaelliger-schluessel-hier
VAULT_USER=max
VAULT_PASSWORD=MeinSicheresPasswort123!
```

---

## 🐛 Häufige Probleme

**Port 8844 bereits belegt**
```bash
# In run.py die Port-Zeile ändern:
app.run(host='0.0.0.0', port=9000, debug=False)
```

**CSV wird nicht erkannt**
- Datei im Browser-Upload prüfen → Konsole (F12) zeigt detaillierten Fehler
- CSV muss `;` oder `,` als Trennzeichen haben
- Encoding: UTF-8 oder Latin-1

---

## 📜 Lizenz

Privater Eigengebrauch. Kein Support, keine Gewährleistung.

---

*Finance Vault – Dein Geld. Dein Überblick.*
