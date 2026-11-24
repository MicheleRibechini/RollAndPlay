# Build

Script che genera il sito di Roll&Play dai documenti del vault. Python 3, nessuna dipendenza esterna. Cosa fa il sito e quale formato si aspetta dai MANUAL sta in `RNP-SITE.md` nel vault: qui non si ripete.

## Uso

```
python build/build-site.py --vault "C:\Users\miche\Documents\RedEnso\Roll&Play"
```

- `--vault`: la cartella `Roll&Play` del vault. Obbligatorio.
- `--out`: cartella di uscita. Di norma `docs/`, accanto a `build/`.
- `--manual SETTING=FILE`: usa `FILE` al posto del MANUAL di quel setting. Serve per il materiale di prova, e la pagina lo dichiara con un avviso.

Lo script riscrive `docs/index.html`, `docs/<setting>/index.html` e `docs/assets/`. Non cancella niente: un setting tolto dal vault va eliminato a mano da `docs/`.

## Cosa legge

- `system/RNP-MANUAL.md`: le sezioni `## Introduzione` e `## Come si gioca` della home.
- `settings/<nome>/<NOME>-MANUAL.md`: ogni cartella con un MANUAL è un setting e ha una pagina in `docs/<nome>/`.
- `system/RNP-THEME.md` e i THEME dei setting: solo le tabelle di palette, sotto i titoli `### Tema chiaro` e `### Tema scuro`. Le variabili finiscono in testa a `docs/assets/site.css`.

## File

- `build-site.py`: lo script.
- `site.json`: lingue attive, contatti della home, codici delle opzioni non selezionabili in creazione.
- `i18n/<lingua>.json`: tutti i testi dell'interfaccia, i testi segnaposto, le frasi che lo script riconosce nei MANUAL e la tabella che dà a ogni termine un codice indipendente dalla lingua.
- `assets/site.css`, `assets/site.js`: CSS e JavaScript comuni a tutte le pagine. Il CSS usa solo le variabili dei THEME.

## Lingue

L'italiano va nella radice di `docs/`, ogni altra lingua in `docs/<lingua>/`. Per aggiungerne una servono il suo `i18n/<lingua>.json`, la voce in `site.json` e i MANUAL tradotti (formato dei nomi ancora da decidere).

## Scheda salvata

Si salva nel browser con la chiave `rnp-sheet-<setting>`, come codici e non come testo, quindi resta valida se cambia la lingua. Le schede del vecchio sito (`drustvar-scheda-v1`) non si recuperano.

## Controllo in locale

Con il doppio clic su `docs/index.html` i link alle cartelle (`drustvar/`) non si aprono. Meglio un server locale:

```
python -m http.server 8000 --directory docs
```

poi apri `http://localhost:8000`.
