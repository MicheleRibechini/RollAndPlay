# Build

Script che generano il sito dai manuali dei setting. Python 3, nessuna dipendenza esterna.

## drustvar-build-site.py

Genera il sito HTML di Drustvar con la creazione interattiva. Produce un HTML unico con CSS e JavaScript dentro.

- **Uso:** `python drustvar-build-site.py "Drustvar - Roll&Play.md" "Drustvar - Roll&Play.html"`.
- **Struttura che si aspetta:** `#` per i capitoli, che si aprono uno alla volta, e `##` per le sezioni. Il capitolo della creazione deve iniziare con "Creazione".
- **Passi della creazione:** titoli nella forma `## Passo N: Scegli una|un Categoria (Tipo)`, più un `## Passo 0` per nome e Obiettivo. Ogni opzione è una voce `- **Nome:** descrizione`.
- **Sotto-scelte:** un nome come `Star (Arte)` crea un menu. Le voci arrivano dalla frase "X a scelta, per esempio A, B o C." (con l'opzione Altro) o "X a scelta tra A, B e C.", oppure dalle opzioni di un altro passo se il parametro è una categoria, come `(Classe)`.
- **Forme annidate:** voci rientrate di due spazi sotto un'opzione (Abomination). La riga "Bestie conosciute: A, B, C." crea il menu della bestia.
- **Casi speciali:** l'opzione `Maestro` è visibile ma non selezionabile. La scheda si salva nel browser con la chiave `drustvar-scheda-v1`.
- **Segno di chiusura:** usa il segno meno invece del trattino medio. Il sito pubblicato in `docs/drustvar/` è precedente a questa correzione.

Lo script va ancora adattato alla pipeline: sezioni a partire da `##` e scelte della creazione lette da MECHANICS.
