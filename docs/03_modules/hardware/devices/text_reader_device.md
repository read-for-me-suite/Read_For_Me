# `hardware.devices.text_reader_device`

## Rôle

`TextReaderDevice` porte la chaîne de traitement documentaire de la machine à lire jusqu'à la production d'un texte propre.

## Étapes gérées

Pour un `basename` donné, le module enchaîne :

1. capture de l'image `<basename>.jpg` ;
2. OCR vers `<basename>_raw.txt` ;
3. nettoyage vers `<basename>.txt`.

## Ce que le module ne fait pas

Il ne gère pas :

- la synthèse vocale ;
- la lecture audio ;
- les touches clavier ;
- le cycle de vie du mode.

Ces responsabilités restent dans `ModeReadingMachine` et `Speaker`.

## `OCRConfig`

La dataclass `OCRConfig` regroupe les paramètres principaux de l'OCR :

- langue ;
- `psm` ;
- `oem` ;
- activation du prétraitement ;
- seuil ;
- timeout ;
- stratégies de fallback.

## Prétraitement

Avant l'OCR, le module peut appliquer :

- passage en niveaux de gris ;
- autocontraste ;
- filtre médian ;
- renforcement de netteté ;
- binarisation.

## Heuristique de sélection OCR

Le module essaie plusieurs `psm` possibles et conserve le meilleur texte selon un score heuristique.
Cela améliore la robustesse sur des documents variés sans exposer cette complexité au mode.

## API principale

- `capture(basename)` ;
- `ocr_to_text(basename)` ;
- `clean_text(basename)` ;
- `run_full_pipeline(basename)`.
