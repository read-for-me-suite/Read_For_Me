# `core.speaker`

## Rôle

`Speaker` est le service audio central de l'application.
Toutes les sorties sonores importantes passent par lui.

## Deux canaux audio distincts

Le module sépare volontairement deux usages différents.

### 1. Les annonces courtes

Les appels `say()` et `speak()` :

- synthétisent le texte avec Piper ;
- produisent des fichiers WAV temporaires ;
- les mettent dans une file d'attente ;
- les jouent séquentiellement avec `mplayer`.

Cela garantit que deux annonces ne se chevauchent pas.

### 2. La lecture longue

`play()` est pensé pour la machine à lire.
Il lance `mplayer` en mode slave afin de permettre :

- pause ;
- reprise ;
- avance ;
- retour ;
- changement de vitesse.

## Contrôle global du son

Le `Speaker` garde aussi la main sur :

- le volume global via `amixer` ;
- la vitesse globale de lecture ;
- les sons de notification ;
- l'arrêt global de tout audio.

## Méthodes publiques importantes

- `say(text, blocking=False)` : annonce courte via la file d'attente ;
- `speak(text)` : alias non bloquant ;
- `play(path)` : lecture longue, retourne un `PlaybackHandle` ;
- `play_sound(path, blocking=False)` : son court hors file ;
- `stop_all_audio()` : coupe les annonces et la lecture longue ;
- `synthesize_to_file(text, output_path)` : génère un WAV à partir d'un texte ;
- `set_volume_global(percent)` ;
- `set_global_speed(speed)` ;
- `close()` : nettoyage complet.

## Pourquoi ce module est structuré ainsi

Le dépôt avait besoin d'un point audio unique pour :

- éviter plusieurs modèles Piper chargés en mémoire ;
- centraliser le contrôle du volume et de la vitesse ;
- garantir une UX cohérente entre modes ;
- fournir une API plus simple que d'appeler directement Piper, `mplayer` et `amixer` partout.

## Cas particulier de la machine à lire

La machine à lire s'appuie sur deux fonctionnalités spécialisées :

- `synthesize_to_file()` pour produire le WAV final ;
- `play()` pour le lire avec un contrôle fin.

C'est l'un des points les plus élégants du projet : le même service central gère à la fois les annonces courtes et la lecture longue, sans dupliquer le chargement du modèle TTS.
