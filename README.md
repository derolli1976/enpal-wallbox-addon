# Enpal Wallbox Controller (Home Assistant Add-on)

Dieses Add-on ermöglicht die Steuerung der Enpal Wallbox über die lokale Webseite der Enpal Box (z. B. `http://192.168.178.178/wallbox`). Die Steuerung erfolgt durch automatisiertes Klicken der UI-Buttons mittels Selenium und Chromium im Headless-Modus.

## 🔧 Funktionen

- Steuerung über HTTP-API (REST)
- Automatisierte Klicks auf Web-UI per Headless Chrome
- Unterstützt folgende Aktionen:
  - Start / Stop Ladevorgang
  - Wechsel zwischen Lademodi: Eco / Solar / Full (Fast)

## 🔌 HTTP-Endpunkte

Alle Endpunkte akzeptieren `POST`-Requests:

```
/wallbox/start         → Startet das Laden
/wallbox/stop          → Stoppt den Ladevorgang
/wallbox/set_eco       → Setzt Lademodus auf Eco
/wallbox/set_full      → Setzt Lademodus auf Full
/wallbox/set_fast      → Setzt Lademodus auf Full
/wallbox/set_solar     → Setzt Lademodus auf Solar
```

Der Dienst lauscht standardmäßig auf Port `36725`.

## 🚀 Installation über Custom Repository

1. Öffne im Home Assistant Menü **Einstellungen → Add-ons → Add-on Store**
2. Klicke oben rechts auf die drei Punkte (⋮) und wähle **Repositories**
3. Gib die URL deines Git-Repositories ein, das dieses Add-on enthält (z. B. `https://github.com/dein-benutzername/enpal-wallbox-addon`)
4. Klicke auf **Hinzufügen** – das Add-on erscheint jetzt im Store
5. Öffne das Add-on und installiere es
6. Bevor du das Add-on startest, öffne die Registerkarte **Konfiguration** und gib die IP-Adresse deiner Enpal Box ein (z. B. `http://192.168.178.178`)
7. Danach kannst du das Add-on starten

## 📦 Abhängigkeiten

- Python 3
- Flask (HTTP-Server)
- Selenium
- Firefox + Geckodriver

## ⚠️ Hinweise

- Dieses Add-on ist nicht offiziell von Enpal unterstützt.
- Die Steuerung basiert auf Annahmen über die HTML-Struktur – bei Änderungen kann eine Anpassung der Button-IDs nötig sein.
