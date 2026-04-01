# Choix techniques

Cette page résume les choix structurants du projet et pourquoi ils ont été retenus.

## Python comme langage principal

Python permet :

- une itération rapide sur Raspberry Pi ;
- une intégration simple avec GPIO, BLE, OCR et audio ;
- une bonne lisibilité pour un projet pédagogique ou évolutif.

## Piper pour la synthèse vocale

Le projet a centralisé la synthèse vocale autour de Piper.
Les raisons principales sont :

- fonctionnement local hors ligne ;
- qualité correcte des voix françaises ;
- intégration simple via fichiers WAV ;
- possibilité de partager un seul modèle chargé en mémoire.

## mplayer pour la lecture

`mplayer` est utilisé sous deux formes :

- lecture bloquante des annonces courtes ;
- mode slave pour la lecture longue pilotable.

Ce choix simplifie fortement :

- pause ;
- reprise ;
- avance / retour ;
- contrôle de vitesse.

## Tesseract pour l'OCR

La machine à lire repose sur `pytesseract`.
Le choix est cohérent avec les contraintes du projet :

- exécution locale ;
- support du français ;
- possibilité de jouer sur le prétraitement d'image ;
- pipeline simple à maintenir.

## GPIOZero pour le matériel local

Le projet utilise `gpiozero` pour :

- le sélecteur rotatif ;
- le bouton poussoir ;
- le clavier matriciel.

L'intérêt est de réduire le bruit de code bas niveau et d'avoir des abstractions simples pour les entrées/sorties.

## BLE avec bleak

`bleak` sert de couche BLE générique pour le multimètre.
Le choix est pertinent car la bibliothèque :

- est maintenue ;
- s'intègre bien avec `asyncio` ;
- reste suffisamment portable pour du développement et du test.

## Configuration TOML

Le fichier `config.toml` a été préféré à une dispersion de constantes dans le code.
Cela permet :

- de modifier un paramètre sans toucher à l'implémentation ;
- de centraliser la validation ;
- de documenter le comportement réel de l'application.

## Architecture en couches légères

Le découpage `core / platform / transports / devices / modes` est un choix volontairement simple.
Il évite d'introduire un framework d'injection ou un système de plugins complexe tout en gardant un dépôt extensible.
