# Controle van de lokale preview

10 oktober 2026.

- Twaalf geautomatiseerde tests geslaagd; alle 26 gemeentepagina’s reageren met 200. Onbekende gemeenten en verborgen artikelen geven 404.
- Echte politie- en Woerden-feedinname uitgevoerd: 4 + 2 signalen in periode. Herhaalde politie-inname gaf nul duplicaten.
- Strapi-importplan voor acht concepten aangemaakt; geen live Strapi-import uitgevoerd.
- Bestaande homepage geopend in browser: inhoud behouden en Nieuws zichtbaar in bestaande hoofdmenu.
- Bestaand menu op kleinere viewport geopend: Nieuws, Lokaal aanbod, Voor organisaties, Ontdek PITO en Zakelijk inloggen behouden.
- Gemeenteselector Woerden bediend: juiste gemeente-URL, alleen lokale en provinciebrede artikelen.
- Onderwerp Bestuur bediend: politieke artikelen in de hoofdlijst; de zijbalk blijft het volledige editieoverzicht tonen.
- Artikel Woerden geopend: bronlink, bronpublicatie en redactionele status zichtbaar.
- Mobiele gemeente- en artikelpagina op 390 px: documentbreedte 390 px, geen horizontale overflow.
- Desktopnieuws op 1440 px: documentbreedte 1440 px, geen horizontale overflow; bestaande PITO-menubalk zichtbaar.
- Geen JavaScript-fouten in de gecontroleerde nieuwsinteracties.

Niet gecontroleerd: productie-Strapi, echte appagenda, live authenticatie/formulieren, volledige oorspronkelijke site, alle browsermerken en toegankelijkheid met hulpmiddelen.

## Uitbreiding 26 september–10 oktober
- 19 zichtbare conceptartikelen; 11 nieuwe primaire bronpublicaties gecontroleerd.
- 12 geautomatiseerde controles geslaagd, inclusief alle 26 gemeenten, bestaande homepage, verborgen concepten en redactionele beveiliging.
- Artikel daadwerkelijk via kop geopend; volledige tekst, gevolgen, datumnotitie, bronlink en illustratie zichtbaar.
- Desktop 1440 px en mobiel 390 px gecontroleerd. Mobiele afbreking van lange kop gecorrigeerd.
- Politie/Woerden-inname opnieuw uitgevoerd: 11 signalen in periode, vijf nieuw toegevoegd.
- Strapi-importplan opnieuw aangemaakt: 19 ongepubliceerde concepten, geen live import.
- OmgevingsAlert alleen bronlink; app-agenda wacht op de bestaande API-koppeling. Geen volledige nieuwsdekking per gemeente of juridische garantie geclaimd.

## Zes maanden en rangschikking — 10 oktober
- 42 geselecteerde artikelpagina's; na één gekoppeld A12-dossier 41 verhalen in het brede archiefoverzicht.
- Bronpublicaties april 2, mei 5, juni 3, juli 4, augustus 3, september 8, oktober 17.
- 21 tests geslaagd: inclusief maximumscore, verlopen urgentie, toekomst/archief, dossierdeduplicatie, spreiding, scorevalidatie, maandfilters, paginering, chronologische volgorde, gemeentefilters behouden en recente RSS.
- In de browser mei geselecteerd, archief met vier pagina's bekeken, oudste pagina geopend en 46 impactformulieren in redactie bevestigd (inclusief vier verborgen concepten).
- Desktop 1440 px en mobiel 390 px gecontroleerd; geen horizontale overloop.
- Primaire U-OV-kortingspublicatie na web-timeout via normale HTTPS-opvraag volledig gelezen; datum en productvoorwaarden bevestigd.
- Huidige RSS-feeds geven samen 15 signalen binnen zesmaandenvenster. Ze bevatten geen compleet historisch archief.
- Importplan omvat 42 concepten inclusief ranking-velden; geen productie-import of openbare publicatie.

## Vandaag, agenda en community
- 26 tests geslaagd; datums/gemeente van activiteiten, meerdere auteurs per gemeente, besloten wachtrij, verplichte broncontrole/toestemming, moderatie, HTML-escaping en contactgegevens niet in publieke artikelpagina gecontroleerd.
- Formulieren slaan uitsluitend lokaal op; geen verzonden e-mail, geen externe publicatie.
- Community blijft leeg tot echte inzendingen zijn beoordeeld; testinzendingen uitsluitend in tijdelijke bestanden.
