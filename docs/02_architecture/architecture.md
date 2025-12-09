# Architecture du système

Cette section présente la structure globale du projet, les rôles de chaque dossier, et la manière dont les différentes briques interagissent.

L’objectif est de donner une vue claire de l’architecture avant d’entrer dans le détail des fichiers.

---

## 1. Vue d’ensemble

Le système suit un schéma simple :

- Des **événements côté utilisateur** (rotation, clics…) sont captés par la couche matérielle.
- Ces événements sont traduits en appels vers un **gestionnaire de modes**.
- Le mode actif peut ensuite :
  - interroger des **drivers matériels** (ex : multimètre),
  - produire une réponse via la **synthèse vocale**.

Aujourd’hui, les événements utilisateur proviennent principalement du **sélecteur rotatif** et de son bouton, mais l’architecture permet d’ajouter d’autres sources d’événements si besoin (pavé numérique, autres entrées matérielles, etc.).

---

## 2. Organisation des dossiers

```text
project_root/
│
├── core/
│   ├── speaker.py
│   ├── mode_base.py
│   └── mode_manager.py
│
├── hardware/
│   ├── platform/
│   │   └── rotary_selector.py
│   ├── transports/
│   │   └── ble_client.py
│   └── devices/
│       └── owon_multimetre.py
│
├── modes/
│   ├── mode_datetime.py
│   ├── mode_dummy.py
│   └── mode_multimetre.py
│
└── main.py
```
Chaque dossier a un rôle bien précis :

- **core/** : logique centrale (modes, TTS, gestionnaire des modes).
- **hardware/** : accès au matériel (GPIO, BLE, drivers d’appareils).
- **modes/** : comportements fonctionnels vus par l’utilisateur.
- **main.py** : point d’entrée qui instancie et connecte toutes les briques.

Ces dossiers représentent les couches principales du système, chacune ayant une responsabilité claire et indépendante.

---

## 3. Flux global de fonctionnement


Le système suit un enchaînement d'événements simple et extensible :

1. **Entrées matérielles**
   - Impulsions rotatives, appuis bouton, signaux GPIO.
   - Données provenant d’un transport (BLE, futur Wi-Fi, futur USB…).

2. **Traitement**
   - Le matériel génère des événements.
   - Ces événements alimentent le `ModeManager` qui active ou notifie le mode courant.
   - Le mode courant fait appel à des drivers matériels si nécessaire.

3. **Sorties**
   - Toutes les annonces passent par le `Speaker`.
   - Le système reste non bloquant grâce à des threads et timers dédiés.

---

## 4. Rôle des couches principales

### 4.1 core/
Cette couche définit la structure logique globale du projet.  
Elle contient :
- la classe abstraite `Mode`,
- la gestion des transitions entre modes (`ModeManager`),
- la synthèse vocale (`Speaker`).

Elle ne dépend pas du matériel : elle pourrait être réutilisée dans un autre projet embarqué.

---

### 4.2 hardware/
Cette couche encapsule toute interaction avec le matériel réel.

Elle est organisée en trois sous-niveaux :

- **platform/** : ce qui concerne le matériel fixe du Raspberry Pi  
  (par exemple : le sélecteur rotatif, futurs pavés numériques, boutons supplémentaires).

- **transports/** : protocoles de communication génériques  
  (BLE aujourd’hui, Wi-Fi, série, USB ou NRF demain).

- **devices/** : drivers fonctionnels qui interprètent les données  
  (ex. multimètre OWON, et futurs appareils).

Chaque transport est réutilisable par plusieurs devices, et chaque device est indépendant de l’interface utilisateur.

---

### 4.3 modes/
Les modes sont les fonctionnalités finales accessibles à l'utilisateur.  
Chacun correspond à un scénario d’usage complet (dire l’heure, lire un multimètre…).

Un mode :
- hérite de la classe `Mode`,
- définit comment réagir aux appuis bouton,
- peut utiliser un ou plusieurs drivers matériels.

Les modes sont **isolés les uns des autres** : en ajouter un ne demande pas de modifier les autres.

---

### 4.4 main.py
C’est le point d’entrée de l’application.

Il :
- instancie le `Speaker`,
- crée tous les modes,
- les passe au `ModeManager`,
- configure le sélecteur rotatif,
- lance l’écoute des événements.

C’est le seul fichier qui connecte toutes les couches entre elles.

---

## 5. Extensibilité prévue

L’architecture est conçue pour supporter facilement de nouveaux composants.

### 5.1 Ajouter un mode
Créer un nouveau fichier dans `modes/` puis l’ajouter dans la liste des modes du main.

Aucune autre modification nécessaire.

### 5.2 Ajouter un device BLE (ou autre)
Créer un fichier dans `hardware/devices/` et réutiliser un transport existant  
(ex. BLEClient) ou en ajouter un nouveau dans `hardware/transports/`.

### 5.3 Ajouter de nouvelles entrées utilisateur
Exemples possibles :
- pavé numérique pour la machine à lire,
- boutons additionnels,
- capteurs tactiles,
- gestes via caméra.

Il suffit d’ajouter un driver dans `hardware/platform/`  
et d’envoyer des événements vers le `ModeManager`.

### 5.4 Ajouter de nouveaux transports
Des protocoles comme Wi-Fi, USB, UART ou NRF peuvent être ajoutés directement dans  
`hardware/transports/` sans impact sur les modes existants.

---

## 6. Conclusion

Cette architecture permet :

- une séparation nette des responsabilités,
- une compréhension facile par tout nouveau développeur,
- une addition simple de nouvelles fonctionnalités,
- une robustesse élevée grâce aux threads dédiés et au non-blocage,
- une indépendance entre matériel, logique métier et expérience utilisateur.

Elle constitue une base solide et évolutive pour toutes les futures extensions du projet.
