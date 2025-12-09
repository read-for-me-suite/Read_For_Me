# Documentation du Projet - Assistant Technique Multimode

Bienvenue dans la documentation officielle du **système d’assistance vocale multimode** basé sur Raspberry Pi, rotacteur matériel et communication BLE.  
Ce document présente l’architecture du système, les modules logiciels, les choix techniques et les guides pour permettre son évolution.

---

# Table des matières

1. **Introduction**
   - [Présentation générale](01_introduction/introduction.md)

2. **Architecture du système**
   - [Architecture complète et flux de fonctionnement](02_architecture/architecture.md)

3. **Description détaillée des modules**
   - **Core**
     - [mode_base](03_modules/core/mode_base.md)
     - [mode_manager](03_modules/core/mode_manager.md)
     - [speaker](03_modules/core/speaker.md)
   - **Hardware**
     - [rotary_selector](03_modules/hardware/rotary_selector.md)
     - [ble_client](03_modules/hardware/ble_client.md)
     - [owon_multimetre](03_modules/hardware/owon_multimetre.md)
   - **Modes**
     - [mode_datetime](03_modules/modes/mode_datetime.md)
     - [mode_dummy](03_modules/modes/mode_dummy.md)
     - [mode_multimetre](03_modules/modes/mode_multimetre.md)

4. **Guides de développement**
   - [Ajouter un mode](04_guides/ajouter_mode.md)
   - [Ajouter un périphérique compatible BLE](04_guides/ajouter_peripherique.md)

5. **Annexes**
   - [Choix techniques](05_annexes/choix_techniques.md)
   - [Glossaire](05_annexes/glossaire.md)

---

# Résumé du projet

L’assistant technique est un système embarqué permettant :

- une **interaction vocale fiable** via TTS (pyttsx3),
- une **navigation par sélecteur rotatif** (rotacteur matériel),
- la **connexion BLE générique** à divers instruments,
- l’acquisition et l’annonce de mesures en temps réel (ex : multimètre OWON).

L’ensemble a été conçu pour être **modulaire, extensible et robuste**, afin de faciliter l’ajout de nouveaux modes ou de nouveaux appareils.

---

# Organisation générale du code

Le projet est structuré en trois grandes couches :

### **1. core/**
Logique principale :
- gestion des modes,
- interface abstraite pour les modes,
- moteur TTS asynchrone.

### **2. hardware/**
Gestion du matériel réel :
- rotacteur,
- transport BLE générique,
- drivers d’appareils (OWON, futurs capteurs…).

### **3. modes/**
Comportements utilisateur :
- Date et heure,
- mode test,
- multimètre OWON.

---

# Pour bien commencer

Pour comprendre le système dans l'ordre :

1. Lire l’**Introduction générale**  
2. Lire l’**Architecture complète**  
3. Explorer les modules **core**  
4. Explorer les modules **hardware**  
5. Lire les **Modes**  
6. Terminer avec les **Guides de développement**

---

# À propos de cette documentation

Cette documentation est :

- simple à parcourir,  
- utile pour un nouveau développeur,  
- claire pour un responsable technique,  
- prête à être générée via **MkDocs + Material** (HTML ou PDF).

---

# Prochaine étape

Commencez par :  
**01_introduction/introduction.md**
