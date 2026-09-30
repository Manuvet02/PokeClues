# Pokémon Clues

Pokémon Clues è un puzzle logico giornaliero ispirato a _Clues by Sam_. La griglia contiene Pokémon già assegnati alle celle: l'obiettivo è dedurre quali sono **Regular** e quali **Shiny**, usando gli indizi senza tirare a caso.

## Come si gioca

- La griglia giornaliera contiene 20 Pokémon. I loro nomi sono visibili da subito, mentre gli sprite restano nascosti.
- Una cella iniziale è già risolta e mostra lo sprite e il proprio indizio.
- Ogni cella propone sempre entrambe le risposte: **Regular** e **Shiny**.
- Si può rispondere a una cella soltanto quando gli indizi già sbloccati forzano logicamente il suo stato. Un tentativo non deducibile non viene accettato.
- Quando la risposta forzata è corretta, la cella rivela la variante Regular o Shiny dello sprite e il suo indizio. L'indizio diventa così disponibile per le deduzioni successive.
- Il puzzle è completato quando tutte le celle sono state risolte.

Gli indizi descrivono conteggi o confronti tra insiemi di celle. Gli insiemi possono essere definiti dalla posizione nella griglia (righe, colonne, diagonali, bordo, angoli e vicinati) o da caratteristiche note dei Pokémon (tipo, colore, generazione, stadio evolutivo e statistiche base). Le categorie sono calcolate usando i dati del Pokédex.

## Puzzle giornaliero

La GitHub Action in `.github/workflows/daily-shiny-puzzle.yml` genera il puzzle ogni giorno alle 00:17 nel fuso `Europe/Rome`, tenendo conto dell'ora legale. GitHub può ritardare i workflow schedulati; il job calcola quindi la data italiana quando parte e non annulla la generazione se l'avvio slitta oltre mezzanotte. Il nuovo JSON viene committato su `main`, da cui Cloudflare Pages può pubblicarlo. È possibile avviare il workflow anche manualmente dalla scheda **Actions** di GitHub.

Per generare un puzzle manualmente dalla radice del repository:

```sh
python scripts/generate_shiny_puzzle.py --date YYYY-MM-DD
```

Il generatore verifica che gli indizi siano veri, che la soluzione sia unica e che ogni cella sia deducibile senza tentativi.
