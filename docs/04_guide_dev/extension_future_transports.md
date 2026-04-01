# Étendre les transports

Cette page explique comment ajouter un nouveau transport générique sans casser l'architecture actuelle.

## 1. Quand créer un transport

Créer un transport si plusieurs périphériques pourraient partager le même canal technique.

Exemples typiques :

- UART ;
- WebSocket ;
- USB série ;
- MQTT ;
- CAN ;
- nouveau protocole radio.

Ne pas créer un transport si la logique est spécifique à un seul matériel et ne sera jamais réutilisée.

## 2. Contrat recommandé

Un transport du dépôt suit généralement ces règles :

- API simple `start()` / `stop()` ;
- état lisible via propriété comme `is_connected` ou `is_running` ;
- thread ou boucle interne propre ;
- callbacks de statut ;
- callback de données brutes.

Exemple de callbacks récurrents :

- `on_status(event: str)` ;
- `on_packet(data: bytes)` ;
- `on_data(payload: str)`.

## 3. Ce que le transport ne doit pas faire

Pour rester réutilisable, un transport ne doit pas :

- annoncer des phrases orientées utilisateur ;
- formater une mesure métier ;
- connaître le `ModeManager` ;
- manipuler directement le `Speaker`.

Ces responsabilités appartiennent au driver de périphérique puis au mode.

## 4. Cycle de vie attendu

Le transport doit être capable de :

- démarrer proprement ;
- s'arrêter proprement ;
- tolérer un second appel à `start()` sans tout casser ;
- signaler les erreurs sans planter silencieusement.

Quand le média le justifie, prévoir aussi :

- reconnexion automatique ;
- filtrage des statuts dupliqués ;
- timeouts explicites ;
- logs de diagnostic.

## 5. Exemple d'intégration complète

Chemin recommandé :

1. créer `hardware/transports/mon_transport.py` ;
2. créer `hardware/devices/mon_device.py` ;
3. créer `modes/mode_mon_device.py` ;
4. enregistrer le mode dans `mode_registry` ;
5. ajouter la configuration dans `config.toml`.

## 6. Questions utiles avant d'implémenter

Avant de coder, répondre à ces points :

- le transport pousse-t-il des données ou faut-il les poller ?
- faut-il un thread, `asyncio`, ou un simple appel synchrone suffit-il ?
- quelles erreurs sont normales et doivent être tolérées ?
- quel niveau de log est utile sur Raspberry Pi en exploitation ?
