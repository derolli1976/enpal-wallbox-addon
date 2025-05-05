# Enpal Wallbox Controller (Home Assistant Add-on)

Dieses Add-on ermöglicht die Steuerung der Enpal Wallbox über die lokale Webseite der Enpal Box (z. B. `http://192.168.2.70/wallbox`). Die Steuerung erfolgt durch automatisiertes Klicken der UI-Buttons mittels Selenium und Chromium im Headless-Modus.

## 🔧 Funktionen

- Steuerung über HTTP-API (REST)
- Automatisierte Klicks auf Web-UI per Headless Chrome
- Unterstützt folgende Aktionen:
  - Start / Stop Ladevorgang
  - Wechsel zwischen Lademodi: Eco / Solar / Full

## 🔌 HTTP-Endpunkte

Alle Endpunkte akzeptieren `POST`-Requests:

```
/wallbox/start         → Startet das Laden
/wallbox/stop          → Stoppt den Ladevorgang
/wallbox/set_eco       → Setzt Lademodus auf Eco
/wallbox/set_full      → Setzt Lademodus auf Full
/wallbox/set_solar     → Setzt Lademodus auf Solar
```

Der Dienst lauscht standardmäßig auf Port `8090`.

## 🚀 Installation

1. Repository als lokales Add-on hinzufügen oder manuell in `/addons/enpal_wallbox_controller/` kopieren
2. Add-on im Supervisor installieren
3. Add-on starten

## 📦 Abhängigkeiten

- Python 3
- Flask (HTTP-Server)
- Selenium
- Chromium + Chromedriver

## ⚠️ Hinweise

- Dieses Add-on ist nicht offiziell von Enpal unterstützt.
- Die Steuerung basiert auf Annahmen über die HTML-Struktur – bei Änderungen kann eine Anpassung der Button-IDs nötig sein.
