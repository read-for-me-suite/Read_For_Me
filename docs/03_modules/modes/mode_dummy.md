# `modes.mode_dummy`

## Rôle

`ModeDummy` est un mode de test et de démonstration.
Il ne pilote aucun matériel spécifique.

## Utilité

Il sert à vérifier rapidement :

- la rotation entre les modes ;
- la détection des appuis ;
- la chaîne de synthèse vocale ;
- le bon routage des événements par `ModeManager`.

## Comportement utilisateur

- appui court : annonce une phrase de confirmation ;
- appui long : annonce une autre phrase de confirmation ;
- double appui : confirme la détection du double clic.

## Pourquoi conserver ce mode

Même s'il n'apporte pas de valeur fonctionnelle directe à l'utilisateur final, il reste très utile pour :

- le débogage ;
- la validation d'une nouvelle plateforme matérielle ;
- l'exemple de squelette de mode minimal.
