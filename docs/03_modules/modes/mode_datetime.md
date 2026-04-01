# `modes.mode_datetime`

## Rôle

`ModeDateHeure` est le mode le plus simple du projet.
Il sert à annoncer l'heure et la date système.

## Comportement utilisateur

- arrivée sur le mode : aucune annonce supplémentaire, car `ModeManager` annonce déjà le nom du mode ;
- appui court : annonce l'heure courante ;
- appui long : annonce la date du jour.

## Dépendances

Le mode dépend seulement de :

- `datetime` pour lire l'heure système ;
- `Speaker` pour la synthèse vocale ;
- `Mode` pour le contrat d'interface.

## Intérêt dans le projet

Ce mode sert à la fois :

- de fonctionnalité utile ;
- d'exemple minimal de mode ;
- de cas simple pour tester le fonctionnement du gestionnaire de modes.

## Point d'attention

Les noms de jour et de mois dépendent de la locale système.
Si le Raspberry Pi n'est pas configuré en français, la date peut être énoncée en anglais.
