# Family Chores — v0.6.1 (correzione turnazione)

**Repository:** https://github.com/SpazioVita/family-chores

Integrazione Home Assistant installabile tramite Marketplace. La v0.6.1 risolve l'assegnazione consecutiva della stessa faccenda allo stesso ospite in seguito a un ricalcolo della coda (per esempio, dopo l'aggiunta progressiva degli utenti).

## Cosa cambia rispetto alla v0.6

- Il calcolo dei turni parte dall'ultimo assegnatario della faccenda già presente nelle occorrenze conservate, inclusa quella odierna.
- La posizione non viene più azzerata nel ricalcolo dei turni futuri.
- La turnazione usa l'ordine stabile degli utenti, anche quando alcuni sono sospesi; privilegia un altro assegnatario per la stessa faccenda, cercando al contempo di evitare sovrapposizioni giornaliere.
- Gli incarichi già chiusi, quelli di oggi e lo storico non vengono modificati dal ricalcolo; se c'è un solo ospite disponibile può ricevere la stessa faccenda consecutivamente.
- Aggiunto `test_rotation_regression.py` per riprodurre il difetto e testare ricalcoli, assenze e continuità dei dati.

Non sono previste modifiche allo schema SQLite, né interventi manuali sul database.

## Pubblicazione su GitHub (installazione già esistente)

1. Sul repository, sostituire i file `custom_components/family_chores/engine.py`, `manifest.json` e `__init__.py` con quelli del pacchetto.
2. Caricare nella radice anche `test_rotation_regression.py`, facoltativo per l'installazione ma necessario come test di regressione, e aggiornare `README.md`.
3. Effettuare il commit sul branch `main`.
4. Consigliato: pubblicare una GitHub Release con tag `v0.6.1`, dopo aver verificato che il codice del tag contiene `manifest.json` versione `0.6.1`.
5. Su Home Assistant, aprire il Marketplace e aggiornare Family Chores quando viene rilevata la nuova versione; al termine **riavviare Home Assistant**.
6. Aprire **Faccende** con account amministratore e usare **Ricalcola** (azione `replan`) per ricostruire gli incarichi futuri. I turni di oggi e le registrazioni passate restano invariati.

Se una versione nuova non appare immediatamente, il Marketplace può aggiornare i repository custom secondo il proprio intervallo di controllo; non cancellare la vecchia installazione né il database per forzare l'aggiornamento. Vedi https://www.home-assistant.io/integrations/marketplace/.

## Installazione da zero

1. Aprire **Impostazioni → Marketplace → Add from link**, aggiungere `https://github.com/SpazioVita/family-chores`.
2. Installare la versione pubblicata e riavviare Home Assistant.
3. In **Impostazioni → Dispositivi e servizi** aggiungere l'integrazione **Family Chores**.
4. Il database SQLite vuoto viene creato automaticamente; registrare gli utenti Home Assistant e poi gli ospiti e le faccende.
5. Per le dashboard aggiungere le card manuali:

```yaml
type: custom:family-chores-my-card
title: Le mie faccende
```

```yaml
type: custom:family-chores-board-card
title: Faccende di oggi e domani
```

## Test

```bash
python -m unittest -v test_rotation_regression test_cards test_visibility test_account_selection
python test_engine.py
```

Per la suite di migrazione `test_deletion.py` serve anche una copia adiacente dei sorgenti v0.3 nel percorso del vecchio test: nel progetto di sviluppo completo è presente, ma non occorre per la normale installazione.

## Avvertenze

Eseguire un backup prima dell'aggiornamento. Il codice è stato verificato con test automatici locali, ma il nuovo comportamento va ancora provato sull'impianto Home Assistant reale. Non caricare file ZIP direttamente come singolo file del repository: caricare il contenuto mantenendo i percorsi.
