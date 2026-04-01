# Documentation technique de Read_For_Me

Cette documentation décrit l'architecture, les modules et les choix de conception du projet `Read_For_Me`.
Elle a deux objectifs :

- aider un nouveau développeur à comprendre rapidement le dépôt ;
- préparer une génération de documentation plus automatique à partir des docstrings Python.

## Vue rapide

`Read_For_Me` est un assistant vocal embarqué pensé pour fonctionner sans écran autour d'un Raspberry Pi.
L'utilisateur navigue entre plusieurs modes au moyen d'un sélecteur rotatif, d'un bouton poussoir et d'un clavier matriciel 4x4.
Selon le mode actif, le système peut :

- annoncer l'heure et la date ;
- lire les mesures d'un multimètre OWON en Bluetooth Low Energy ;
- piloter une machine à lire basée sur caméra + OCR + synthèse vocale ;
- annoncer des mesures issues d'un pied à coulisse radio NRF24 ;
- annoncer une température lue via un capteur ESP32 exposé en HTTP local.

## Table des matières

1. Introduction
   - [Présentation générale](01_introduction/introduction.md)

2. Architecture
   - [Architecture du système](02_architecture/architecture.md)

3. Modules
   - Core
     - [mode_base](03_modules/core/mode_base.md)
     - [mode_manager](03_modules/core/mode_manager.md)
     - [mode_registry](03_modules/core/mode_registry.md)
     - [speaker](03_modules/core/speaker.md)
   - Configuration
     - [config_loader](03_modules/config/config_loader.md)
   - Hardware / platform
     - [rotary_selector](03_modules/hardware/platform/rotary_selector.md)
     - [keypad_4x4](03_modules/hardware/platform/keypad_4x4.md)
     - [pi_camera](03_modules/hardware/platform/pi_camera.md)
   - Hardware / transports
     - [ble_client](03_modules/hardware/transports/ble_client.md)
     - [wifi_client](03_modules/hardware/transports/wifi_client.md)
     - [nrf24_transport](03_modules/hardware/transports/nrf24_transport.md)
   - Hardware / devices
     - [owon_multimeter](03_modules/hardware/devices/owon_multimeter.md)
     - [text_reader_device](03_modules/hardware/devices/text_reader_device.md)
     - [esp32_thermometer](03_modules/hardware/devices/esp32_thermometer.md)
     - [caliper](03_modules/hardware/devices/caliper.md)
   - Modes
     - [mode_datetime](03_modules/modes/mode_datetime.md)
     - [mode_dummy](03_modules/modes/mode_dummy.md)
     - [mode_multimetre](03_modules/modes/mode_multimetre.md)
     - [mode_reading_machine](03_modules/modes/mode_reading_machine.md)
     - [mode_caliper](03_modules/modes/mode_caliper.md)
     - [mode_thermometer](03_modules/modes/mode_thermometer.md)

4. Guides de développement
   - [Ajouter un mode](04_guide_dev/ajouter_un_mode.md)
   - [Ajouter un périphérique](04_guide_dev/ajouter_un_peripherique.md)
   - [Patterns utilisés](04_guide_dev/patterns_utilises.md)
   - [Étendre les transports](04_guide_dev/extension_future_transports.md)

5. Annexes
   - [Choix techniques](05_annexes/choix_techniques.md)
   - [Glossaire](05_annexes/glossaire.md)
   - [Schéma des composants](05_annexes/schema_composants.md)

## Parcours recommandé

Pour découvrir le projet dans le bon ordre :

1. lire l'[introduction](01_introduction/introduction.md) ;
2. lire l'[architecture](02_architecture/architecture.md) ;
3. explorer le `core` puis la `config` ;
4. parcourir les drivers `hardware` ;
5. terminer par les modes et les guides d'extension.
