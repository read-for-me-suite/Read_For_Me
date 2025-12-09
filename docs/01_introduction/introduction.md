# Introduction

Ce document décrit le fonctionnement interne, les choix techniques et l’architecture du **système d’assistance technique multimode** développé sur Raspberry Pi.

L’objectif principal est de permettre à un utilisateur d’accéder facilement à plusieurs fonctions utiles (lecture de l’heure, consultation d’un multimètre Bluetooth, etc.) via une interface matérielle simple et une synthèse vocale.

---

## Objectifs du projet

Le projet poursuit plusieurs objectifs concrets :

### 1. Faciliter l’accès à l’information

Permettre à l’utilisateur d’obtenir rapidement des informations utiles (heure, mesures électriques, messages de test…) sans avoir à regarder un écran.

Aujourd’hui, la navigation se fait principalement via :
- un **sélecteur rotatif** (changement de mode),
- un **bouton poussoir** (appui court / long / double).

> D’autres types de contrôles ou d’entrées pourront être ajoutés plus tard (clavier, caméra, etc.). L’architecture est pensée pour pouvoir les accueillir sans être complètement modifiée.

---

### 2. Proposer une architecture modulaire

Le code est structuré pour que l’on puisse :

- ajouter facilement de **nouveaux modes** (par exemple : lecture de fichiers, calculatrice vocale, etc.),  
- connecter d’autres **appareils matériels** (autres instruments BLE, futurs capteurs…),  
- réutiliser les briques centrales (`core/`) dans d’autres projets proches.

Chaque brique a un rôle bien délimité :
- gestion des modes,
- gestion de la voix,
- drivers matériels,
- modes orientés utilisateur.

---

### 3. Garantir un fonctionnement robuste

Le système doit rester stable même en présence de :

- connexions Bluetooth capricieuses,
- actions utilisateur rapides (rotations et clics rapprochés),
- délais de réponse du matériel.

Pour cela, on utilise notamment :
- un **thread dédié pour la synthèse vocale**,  
- un **thread dédié pour le BLE**,  
- des callbacks et timers non bloquants pour le sélecteur rotatif,  
- une séparation claire entre logique métier et accès matériel.

---

### 4. Faciliter la prise en main par un nouveau développeur

La documentation et l’architecture visent à permettre à quelqu’un qui rejoint le projet de :

- comprendre rapidement **qui fait quoi**,
- repérer où ajouter un **nouveau mode**,
- repérer où intégrer un **nouvel appareil**,
- intervenir sans risque de tout casser.

---

## 📦 Périmètre fonctionnel actuel

À la date de cette version, le système embarque :

### Modes disponibles

- **Mode Date & Heure**
  - Appui court : annonce de l’heure.
  - Appui long : annonce de la date du jour.

- **Mode Test (ModeDummy)**
  - Sert de mode de démonstration / vérification de la chaîne TTS et du sélecteur.

- **Mode Multimètre OWON 16**
  - Connexion BLE à un multimètre OWON.
  - Décodage des trames 6 octets spécifiques OWON.
  - Annonce des mesures sur demande.
  - Mode de lecture automatique activable par double appui.

---

### Briques techniques principales

- **Synthèse vocale (`core/speaker.py`)**
  - Gestion de la TTS dans un thread dédié.
  - File de messages pour éviter les blocages.

- **Gestionnaire de modes (`core/mode_manager.py`)**
  - Centralise les modes disponibles.
  - Gère le changement de mode via le sélecteur.
  - Propage les appuis bouton au mode courant.

- **Abstraction de mode (`core/mode_base.py`)**
  - Définition des hooks : `on_enter`, `on_exit`, `on_short_press`, `on_long_press`, `on_double_press`.

- **Sélecteur rotatif (`hardware/platform/rotary_selector.py`)**
  - Lecture des signaux GPIO.
  - Gestion des gestes de rotation (stabilisation).
  - Gestion des appuis : court / long / double.

- **Client BLE générique (`hardware/transports/ble_client.py`)**
  - Scan, connexion, reconnexion automatique.
  - Notifications sur une caractéristique BLE.

- **Driver OWON (`hardware/devices/owon_multimetre.py`)**
  - Décodage des trames du multimètre OWON 16.
  - Détection des changements de fonction (Volt, Ohm, Ampère…).
  - Interface simple pour récupérer la dernière mesure.

---

## Lecture recommandée

Pour comprendre le projet dans l’ordre :

1. **Cette introduction** (fichier actuel)  
2. **Architecture du système** : `02_architecture/architecture.md`  
3. **Description détaillée des modules** : `03_modules/...`  
4. **Guides de développement** pour ajouter des modes ou des appareils : `04_guide_dev/...`

Le but est qu’après cette lecture, tu saches :
- où se trouvent les responsabilités,
- comment circulent les événements,
- comment étendre proprement le système.
