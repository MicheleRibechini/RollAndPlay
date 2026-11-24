# Build

Script che generano il sito dai manuali dei setting. Python 3, nessuna dipendenza esterna.

## drustvar-build-site.py

Genera il sito HTML di Drustvar con la creazione interattiva. Produce un HTML unico con CSS e JavaScript dentro.

- **Uso:** `python drustvar-build-site.py "Drustvar - Roll&Play.md" "Drustvar - Roll&Play.html"`.
- **Formato del manuale:** lo descrive `RNP-SITE.md` nel vault, sezione "Formato della creazione". Qui non si ripete.
- **Scheda:** si salva nel browser con la chiave `drustvar-scheda-v1`.
- **Segno di chiusura:** usa il segno meno invece del trattino medio. Il sito pubblicato in `docs/drustvar/` è precedente a questa correzione.

Lo script va ancora adattato alla pipeline descritta in `RNP-SITE.md`: il lavoro aperto è in `RNP-TODO.md`.
