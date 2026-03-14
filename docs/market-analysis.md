# Marktanalyse: Relevante Feature-Luecken bei Konkurrenzprodukten

Stand: 2026-03-14

## Ausgangslage

`hotkey-transcriber` ist bereits stark bei lokaler Spracherkennung, direkter Texteingabe per Hotkey, Tray-Integration sowie Linux-/Windows-Unterstuetzung inklusive AMD/ROCm-Sonderfaellen. Im Markt zeigen vergleichbare Produkte ihre groessten Vorteile jedoch meist nicht bei der reinen Transkription, sondern bei Workflow-, Kontext- und Nachbearbeitungsfunktionen.

## Relevante Marktanforderungen

### 1. Persoenliches Woerterbuch, Ersetzungen und Snippets

Viele Konkurrenzprodukte bieten benutzerdefinierte Woerterbuecher, Textersetzungen, persoenliche Fachbegriffe sowie Snippets fuer wiederkehrende Formulierungen. Das verbessert Erkennungsqualitaet, Konsistenz und Geschwindigkeit im Alltag deutlich.

Nutzen fuer dieses Projekt:
- Bessere Erkennung von Namen, Produktbegriffen und Fachsprache
- Schnellere Eingabe wiederkehrender Textbausteine
- Hoehere Bindung fuer Power-User

### 2. AI-Postprocessing-Modi

Produkte wie moderne Dictation-Tools differenzieren zunehmend ueber Modi wie `Nachricht`, `E-Mail`, `Notiz` oder `Prompt`. Dabei wird der diktierte Rohtext nachtraeglich in den passenden Stil, in bessere Struktur oder in eine bereinigte Form gebracht.

Nutzen fuer dieses Projekt:
- Weniger manuelle Nachbearbeitung
- Klarerer Mehrwert gegenueber einfachen Whisper-Frontends
- Besserer Fit fuer unterschiedliche Nutzungsszenarien

### 3. Kontextmodus mit aktivem Textfeld, Auswahl und Clipboard

Ein wachsender Teil des Markts bietet kontextsensitives Diktieren. Dazu gehoeren optionaler Zugriff auf markierten Text, Inhalte der Zwischenablage oder das aktuelle Eingabefeld. Dadurch kann das System Namen, Schreibweisen, Stil oder Arbeitskontext besser beruecksichtigen.

Nutzen fuer dieses Projekt:
- Hoehere Genauigkeit bei Fachbegriffen und Personen-/Firmennamen
- Moeglichkeit fuer kontextbezogene Umschreib- und Antwortmodi
- Gute Grundlage fuer spaetere Agent- oder Assistenzfunktionen

### 4. Transkript-Historie mit Wiederverwenden und Korrigieren

Einige Wettbewerber bieten eine lokale Historie frueherer Diktate. Das erleichtert Wiederverwendung, Korrekturen, Suche und den Rueckgriff auf kuerzlich erzeugte Inhalte.

Nutzen fuer dieses Projekt:
- Hoehere Fehlertoleranz im Alltag
- Bessere Wiederverwendbarkeit von Transkripten
- Natuerlicher Ausbaupfad zu Suche, Export und Qualitaetsverbesserung

### 5. Datei-Transkription fuer MP3/WAV/MP4

Viele aehnliche Tools bieten neben Live-Diktat auch die Transkription von Audiodateien oder Videos. Das erweitert den Anwendungsbereich deutlich in Richtung Meetings, Interviews, Sprachmemos und Content-Aufbereitung.

Nutzen fuer dieses Projekt:
- Neuer klarer Use Case ausserhalb des Live-Diktats
- Mehr Wert fuer Business-, Creator- und Dokumentations-Szenarien
- Gute Wiederverwendung vorhandener Whisper-Infrastruktur

### 6. Mehr Sprachbefehle fuer Editieren, Formatieren, Auswahl und Umschreiben

Fuehrende Sprachtools bieten nicht nur Diktat, sondern auch Sprachsteuerung fuer Textbearbeitung. Dazu gehoeren Befehle wie Loeschen, Auswaehlen, Ersetzen, neue Zeile, Formatieren oder Umschreiben.

Nutzen fuer dieses Projekt:
- Deutlich fluessigerer Hands-free-Workflow
- Groesserer Abstand zu simplen Speech-to-Text-Apps
- Gute Verlaengerung der bereits vorhandenen Sprachkommando-Basis

## Priorisierte Chancen

Aus Marktsicht wirken diese Ausbaustufen aktuell am sinnvollsten:

1. Persoenliches Woerterbuch + Ersetzungen + Snippets
2. AI-Postprocessing-Modi
3. Kontextmodus mit optionalem Clipboard-/Auswahlzugriff
4. Transkript-Historie
5. Datei-Transkription
6. Ausbau der Sprachbefehle

## Strategische Einordnung

Die Differenzierungschance fuer `hotkey-transcriber` liegt nicht primaer darin, noch ein weiteres Whisper-Frontend zu sein. Die staerkste Marktposition ergibt sich eher aus der Kombination von:

- Lokal und privacy-first
- Technisch robuste GPU-/Backend-Unterstuetzung
- Schneller Hotkey-Workflow
- Smarte Nachbearbeitung und Personalisierung

Wenn diese sechs Bereiche umgesetzt werden, bewegt sich das Produkt von einem guten lokalen Diktierwerkzeug in Richtung eines deutlich vollstaendigeren Voice-Productivity-Tools.
