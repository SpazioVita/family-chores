# Family Chores — installazione da browser (v0.6, pacchetto per repository)

Questa è una **bozza installabile da repository GitHub pubblico tramite Home Assistant Marketplace**; non è ancora pubblicata su GitHub. Non contiene alcun database, storico o dati utente.

## Prima pubblicazione del repository

1. Crea un repository GitHub **pubblico** per Family Chores.
2. Carica **il contenuto** di questa cartella alla radice del repository, senza inserirlo in una sottocartella aggiuntiva.
3. In `custom_components/family_chores/manifest.json` sostituisci `REPLACE_OWNER` con il nome del proprietario GitHub e aggiorna l'URL di `documentation`.
4. Aggiungi sul repository una descrizione e abilita Issues; per un progetto da distribuire stabilmente, esegui anche i controlli ufficiali `hassfest`.

## Installazione da browser su una nuova Home Assistant

1. Apri **Impostazioni > Marketplace** (Home Assistant aggiornato). Dal menu aggiungi un repository tramite link GitHub, indicando quello appena creato.
2. Installa Family Chores come integrazione e riavvia Home Assistant se richiesto.
3. Vai in **Impostazioni > Dispositivi e servizi > Aggiungi integrazione**, cerca `Family Chores` e conferma **Installa Family Chores**.
4. Il database SQLite vuoto sarà creato automaticamente in `.storage/family_chores.sqlite`; il pannello **Faccende** apparirà nella barra laterale.
5. Da **Faccende > Utenti** associa gli account Home Assistant, quindi crea le faccende.
6. Nella dashboard personale aggiungi una card manuale:

   ```yaml
   type: custom:family-chores-my-card
   title: Le mie faccende
   ```

7. Nella dashboard della bacheca comune aggiungi una card manuale:

   ```yaml
   type: custom:family-chores-board-card
   title: Faccende di oggi e domani
   ```

**Non servono** configurazioni `configuration.yaml`, copie in `/config/www`, registrazione manuale delle risorse JavaScript o database preesistenti.

## Limiti e note

- Il pacchetto è stato validato con controlli Python e test del motore, ma **non collaudato direttamente su Home Assistant** in questa sessione: consigliata prima installazione su istanza di test.
- La pubblicazione su GitHub è necessaria per l'installazione tramite Marketplace. Un ZIP locale da solo non viene installato direttamente dal Marketplace.
- Il progetto è destinato a nuove installazioni: su un impianto che usa già v0.5 non installare in parallelo senza predisporre una procedura di migrazione.
- La risorsa JavaScript delle card viene caricata automaticamente tramite il frontend. È necessario aggiungere manualmente le due card alle dashboard desiderate.
- La bacheca è leggibile da qualunque utente HA autenticato; le conferme restano vincolate all'assegnatario.
