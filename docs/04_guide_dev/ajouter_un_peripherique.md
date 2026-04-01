# Ajouter un périphérique

Le mot "périphérique" recouvre ici un matériel externe ou un sous-système technique qui doit être intégré proprement.

## 1. Identifier la bonne couche

Avant de coder, il faut déterminer à quel niveau placer la logique :

- `hardware/platform/` : matériel directement branché au Raspberry Pi ;
- `hardware/transports/` : protocole ou canal de communication générique ;
- `hardware/devices/` : décodage et pilotage d'un périphérique concret ;
- `modes/` : logique utilisateur finale.

Exemples :

- une caméra Raspberry Pi relève de `platform` ;
- un client BLE ou HTTP relève de `transports` ;
- un multimètre OWON relève de `devices` ;
- la lecture vocale des mesures relève d'un `mode`.

## 2. Commencer par le transport si nécessaire

Si le périphérique repose sur un canal réutilisable, créer ou réutiliser un transport.

Dans le dépôt actuel :

- `BleClient` gère la découverte, la connexion et les notifications BLE ;
- `WifiClient` gère un polling HTTP générique ;
- `Nrf24Transport` gère la réception radio NRF24.

Le transport ne doit pas connaître le métier.
Il ne doit exposer que :

- des callbacks de statut ;
- des callbacks de données brutes ;
- une API `start()` / `stop()` lisible.

## 3. Créer le driver de périphérique

Le driver transforme des paquets bruts en objets métier.
Il sert aussi à isoler les particularités protocolaires du reste du code.

Exemples existants :

- `OwonMultimeterDriver` ;
- `ThermometerDriver` ;
- `CaliperDriver` ;
- `TextReaderDevice`.

Le driver peut :

- mémoriser une dernière mesure ;
- fournir une API `get_last_measure()` ;
- traduire les statuts techniques en messages plus parlants.

## 4. Ne pas faire parler directement le périphérique

Bonne pratique du dépôt : les drivers remontent du texte ou des données, mais la décision de parler reste au niveau du mode.

Cela garde le design propre :

- le driver reste réutilisable ;
- le mode garde la maîtrise de l'expérience utilisateur ;
- la voix reste centralisée dans `Speaker`.

## 5. Exposer une API simple au mode

Le mode doit idéalement voir une interface minimale :

- `start()` ;
- `stop()` ;
- `is_connected` ;
- `get_last_measure()` ;
- éventuellement un callback `on_new_measure`.

Si l'API du driver commence à exposer beaucoup d'états internes ou d'objets de transport, c'est souvent le signe qu'il manque un niveau d'abstraction.

## 6. Configurer le périphérique

Les paramètres doivent aller dans `config/config.toml`.
Éviter les constantes codées en dur dans le driver.

Exemples de paramètres déjà configurés :

- GPIO du NRF24 ;
- URL de l'ESP32 ;
- UUID BLE et filtres de scan ;
- timings de reconnexion.

## 7. Ajouter un mode si nécessaire

Si le périphérique correspond à une fonctionnalité utilisateur, créer ensuite un mode dédié.
Ce mode décidera :

- quand lancer le driver ;
- quand lire une donnée ;
- comment formuler les annonces ;
- quels gestes ou touches le contrôlent.

## 8. Vérification recommandée

Avant de finaliser l'intégration :

- tester l'absence de périphérique ;
- tester la reconnexion ou le redémarrage ;
- vérifier que `on_exit()` coupe proprement le périphérique ;
- vérifier que l'audio ne reste pas actif lors d'un changement de mode.
