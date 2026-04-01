# Schéma des composants

Cette page synthétise l'organisation logique du projet.

## Schéma logiciel

```text
Entrées utilisateur
├── RotarySelector
└── Keypad4x4
        │
        ▼
   ModeManager
        │
        ├── ModeDateHeure
        ├── ModeDummy
        ├── ModeMultimetre
        ├── ModeReadingMachine
        ├── ModeCaliper
        └── ModeThermometre
                │
                ▼
             Speaker
```

## Schéma matériel / communication

```text
Raspberry Pi
├── GPIO
│   ├── sélecteur rotatif
│   └── clavier 4x4
├── caméra Pi
├── Bluetooth Low Energy
│   └── multimètre OWON
├── réseau local HTTP
│   └── ESP32 thermomètre
└── SPI + NRF24L01+
    └── pied à coulisse
```

## Pipeline machine à lire

```text
PiCamera
  -> image .jpg
  -> OCR Tesseract
  -> texte brut
  -> nettoyage
  -> Speaker.synthesize_to_file()
  -> wav
  -> Speaker.play()
```

## Photos

Le dossier `docs/05_annexes/00_images/` contient des photos du prototype.
Ces images peuvent être intégrées ensuite dans une documentation MkDocs ou dans une documentation générée automatiquement.
