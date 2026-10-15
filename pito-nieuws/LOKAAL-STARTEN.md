# PITO Nieuws lokaal bekijken

Dubbelklik op **start-local.command**. Een Terminal-venster start de site en opent je browser op:

http://127.0.0.1:4198/nieuws/utrecht

Laat Terminal open zolang je de site bekijkt. Druk daar op **Ctrl+C** om de server te stoppen. Na een wijziging aan Python-code stop je de server en start je hem opnieuw; CSS- en JavaScript-wijzigingen zie je na verversen.

Je hebt Python 3.9 of nieuwer nodig. Voor de preview zijn geen extra Python-pakketten, database of build nodig. Bewaar de volledige map met `data`, `static` en `portable-assets` bij elkaar.

## Starten vanuit Terminal

Open Terminal in deze map en voer uit:

```sh
./start-local.command
```

Is poort 4198 bezet, dan geeft de starter uitleg. Draait de site al, open de bovenstaande link. Anders sluit je de eerdere server met Ctrl+C, of gebruik je:

```sh
PORT=4200 ./start-local.command
```

De browser opent dan poort 4200. Op andere systemen kun je vanuit deze map starten met:

```sh
PITO_STANDALONE=1 PITO_SITE_MODE=preview python3 -B server.py
```

## Wat je ziet

Dit is een lokale ontwerp- en contentpreview. Hij is alleen bereikbaar op deze computer. De voorbeeldinhoud en appagenda zijn momentopnamen; sommige knoppen verwijzen naar de bestaande PITO-app of externe bronnen.

De meegeleverde Python-server is volgens de overdracht bedoeld voor een lokale preview. Voor livegang moeten de productieapp, publicatiegoedkeuring, inhoud en beeldrechten, beveiligd beheer, HTTPS en echte bronkoppelingen worden afgerond. De technische overdracht staat in [START-HIER-DEVELOPER.txt](START-HIER-DEVELOPER.txt).
