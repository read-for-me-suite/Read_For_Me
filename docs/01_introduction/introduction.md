# Introduction

Ce dépôt contient un assistant vocal embarqué modulaire destiné à être exécuté sur Raspberry Pi.
Le projet ne repose pas sur une interface graphique : toute l'expérience utilisateur passe par des entrées matérielles simples et par un retour audio.

## Finalité du projet

L'objectif principal est de fournir un socle logiciel extensible pour des usages d'assistance technique.
La première famille d'usages consiste à rendre accessibles des informations ou des mesures sans écran :

- heure et date ;
- mesures d'un multimètre ;
- température d'un capteur réseau ;
- lecture de texte à partir d'une photo ;
- mesure d'un pied à coulisse.

Le système a donc été construit autour de trois exigences fortes :

- modularité : ajouter un mode ou un périphérique sans réécrire l'application ;
- robustesse : éviter qu'une opération lente bloque toute l'interface ;
- lisibilité : rendre le code compréhensible et documentable.

## Interface utilisateur

L'interface physique actuelle repose sur deux familles d'entrées :

- un sélecteur rotatif avec bouton poussoir ;
- un clavier matriciel 4x4.

Le sélecteur rotatif sert à changer de mode.
Le bouton du sélecteur fournit trois gestes :

- appui court ;
- appui long ;
- double appui.

Le clavier 4x4 est partagé par tout le système.
Certaines touches sont globales et toujours actives :

- augmentation du volume ;
- diminution du volume ;
- augmentation de la vitesse de lecture ;
- diminution de la vitesse de lecture.

Les autres touches sont déléguées au mode actif.
C'est particulièrement important pour la machine à lire, qui utilise le clavier pour capturer, mettre en pause, relancer ou annuler une lecture.

## Périmètre fonctionnel actuel

À la date de cette version, les modes disponibles sont :

- `datetime` : annonce l'heure et la date système ;
- `dummy` : valide la chaîne d'événements et la synthèse vocale ;
- `multimeter` : pilote un multimètre OWON via BLE ;
- `reading_machine` : capture une photo, lance l'OCR, synthétise puis lit le texte ;
- `caliper` : lit un pied à coulisse numérique via NRF24 ;
- `thermometer` : lit une température publiée par un ESP32 via HTTP local.

## Architecture logique

Le projet est structuré en couches volontairement simples :

- `core/` : règles communes de l'application, synthèse vocale, orchestration des modes ;
- `config/` : chargement, fusion et validation de la configuration TOML ;
- `hardware/` : accès au matériel local, aux transports et aux périphériques ;
- `modes/` : logique fonctionnelle orientée utilisateur ;
- `main.py` : assemblage de toutes les briques.

Cette séparation permet de conserver une frontière nette entre :

- ce qui relève de l'entrée/sortie physique ;
- ce qui relève du transport de données ;
- ce qui relève du métier utilisateur ;
- ce qui relève de l'orchestration globale.

## Conception orientée extension

Le dépôt a déjà été préparé pour évoluer.
Les deux mécanismes principaux sont :

- un registre de modes (`core/mode_registry.py`) ;
- une configuration centralisée (`config/config.toml`).

Concrètement :

- l'ordre des modes actifs ne dépend pas d'une liste codée en dur dans `main.py` ;
- les timings matériels, GPIO, paramètres OCR, BLE et audio vivent dans la configuration ;
- les modes restent découplés des détails de câblage tant qu'ils passent par les drivers adaptés.

## Contraintes techniques importantes

Le système dialogue avec des composants lents ou instables par nature :

- synthèse vocale ;
- Bluetooth Low Energy ;
- polling réseau ;
- caméra Raspberry Pi ;
- OCR Tesseract ;
- radio NRF24.

Pour éviter les blocages, le projet utilise plusieurs threads dédiés :

- thread de file d'attente pour les annonces TTS ;
- thread interne du client BLE ;
- thread de scan du clavier ;
- thread de pipeline de la machine à lire ;
- thread de surveillance caméra ;
- thread de polling HTTP ;
- thread d'écoute NRF24.

La documentation détaillera ces flux plus loin, car ils conditionnent une grande partie de la robustesse du projet.

## Ce qu'il faut retenir avant de lire la suite

Si tu découvres le code, les idées centrales sont les suivantes :

- un seul mode est actif à un instant donné ;
- `ModeManager` reçoit les événements et les route vers ce mode ;
- tous les retours vocaux passent par `Speaker` ;
- les drivers matériels exposent des API simples et des callbacks ;
- `main.py` est le seul point d'assemblage global.
