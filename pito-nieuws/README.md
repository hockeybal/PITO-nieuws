> Actuele overdracht (14 oktober 2026): zie **START-HIER-DEVELOPER.txt**. De onderstaande historische beschrijving bevat oudere aantallen en tussenstanden. Zelfstandig starten: `PITO_STANDALONE=1 python3 -B server.py`.

# PITO Nieuws — lokale uitbreiding van de bestaande PITO-website

## Vaste projectafspraken

Lees bij vervolgwerk `PITO-PROJECTAFSPRAKEN.txt` en `RECHTEN-EN-PUBLICATIE.txt`. Bronlinks en beeldvindplaatsen zijn onderzoeksmateriaal; de huidige preview is geen volledig gecontroleerde productieredactie.

## Openen

- Bestaande PITO-website: http://127.0.0.1:4198/
- Provinciaal nieuws: http://127.0.0.1:4198/nieuws/utrecht
- Gemeenten: http://127.0.0.1:4198/nieuws/gemeenten
- Woerden: http://127.0.0.1:4198/nieuws/utrecht/woerden
- Redactie: http://127.0.0.1:4198/nieuws/redactie
- Bronnen: http://127.0.0.1:4198/nieuws/bronnen
- Eigen RSS: http://127.0.0.1:4198/nieuws/feed.xml
- Gemeentelijke RSS: http://127.0.0.1:4198/nieuws/feed.xml?gemeente=woerden
- Sitemap: http://127.0.0.1:4198/nieuws/sitemap.xml

Start vanuit deze map met `PYTHONDONTWRITEBYTECODE=1 python3 server.py`. De server bindt alleen aan 127.0.0.1. Er zijn geen nieuwe packages nodig.

## Bestaande site behouden

De basis is de recente lokale `pito-preview` van 25–29 september. De bronlocatie staat in `base.json` en is overschrijfbaar via `PITO_BASE_PREVIEW`. `server.py` breidt de bestaande previewhandler uit. De homepage, Vue-aanbodmodule, vacatures, organisaties, bestaande assets en routes blijven afkomstig uit die basis. Alleen een Nieuws-link is aan de bestaande navigatie toegevoegd. Nieuwspagina’s hergebruiken de bestaande header, footer, CSS en menubediening; nieuwe styles zijn beperkt tot de nieuwsinhoud. Er is niets in de oorspronkelijke site overschreven.

Dit is een **lokale geïntegreerde preview**, geen wijziging in de Laravel-productieapp. De preview verwijst naar bestaande lokale bronmappen en is daarom niet zelfstandig overdraagbaar zonder die basisbestanden. Authenticatie en formulieren blijven de bestaande previewbeperkingen houden.

## Geïnspecteerde techniek

De oorspronkelijke applicatie gebruikt Laravel, Vue 3 en Vite. De nieuwere preview combineert de hoofdwebsite en Vue Deals met een Python-previewserver. De hoofdsite heeft een uitgeschakelde `PITO_CMS_CONFIG`. De Laravel Deals-integratie leest via `PitoContentService` een gedeeld Strapi-contentcontract (`settings`, `categories`, `offers`, `jobs`, `collectives`) met server-side token en cache. Zonder configuratie valt die terug op fixtures. Er is geen bevestigde bestaande nieuwscollectie of productie-agenda-API gevonden.

De nieuwe nieuwsinhoud wordt server-side gerenderd, zodat titels, tekst, links, canonical, Open Graph en NewsArticle JSON-LD zonder JavaScript beschikbaar zijn. Lokale pagina’s blijven bewust `noindex,nofollow`. Er zijn geen verzonnen PITO-publicatiedatums in structured data opgenomen. Voor productie zijn echte publicatietijden, eindredactie, canonicals en de keuze voor indexeren van dunne gemeentepagina’s nog nodig.

## Redactionele selectie

Alleen belangrijke ontwikkelingen met een aantoonbare relatie tot een Utrechtse gemeente of de provincie: lokaal en provinciaal bestuur, woningbouw, bereikbaarheid, politie en veiligheid. Geen buitenlands nieuws, geen generieke landelijke berichten en geen kleine meldingen om lege pagina’s op te vullen. Kleine serviceberichten zijn als verborgen concept bewaard. Provinciebrede veiligheidsinformatie kan op alle gemeentepagina’s verschijnen, duidelijk als provinciebreed artikel.

De eerste acht geselecteerde berichten zijn eigen feitelijke samenvattingen. Alle bronteksten en persfoto’s blijven bij de bron. De grafische vlakken zijn eigen CSS, geen nieuwsfoto’s. De periode is de gevraagde editie 3–10 oktober 2026; bronpublicatie en gebeurtenisdatum zijn afzonderlijke velden. Activiteiten/vacatures worden beoordeeld ten opzichte van de vaste onderzoeksdatum, niet als onbeperkt actueel aanbod gepresenteerd.

## Feeds en redactie

`python3 scripts/intake.py --start 2026-10-03 --end 2026-10-10`

Twee echte officiële RSS-feeds zijn opgehaald: Politie provincie Utrecht en Gemeente Woerden. Zes signalen binnen de periode; herhaald ophalen voegt geen duplicaten toe. Alleen kop, URL en bronpublicatiedatum worden als interne signalen opgeslagen. De invoer wordt begrensd op grootte, tijd en HTTPS. XML-DTD/entities worden geweigerd. Ongedateerde en verkeerd gedateerde items worden overgeslagen. Fouten worden in `data/intake-report.json` zichtbaar gemaakt. Een feed is geen archief; dit is geen garantie op volledige weekdekking.

De redactiepagina biedt eigen titel, samenvatting, artikel, gemeente en datumnotitie bij een signaal. Dit maakt een verborgen concept. Daarna zijn bewerken, goedkeuren en intrekken mogelijk; wijzigingen worden lokaal bewaard en gelogd. Goedkeuring vereist een redacteursnaam, notitie en controlebevestiging. De lokale omgeving is geen multi-user productieredactie: voor productie zijn accounts, rollen, echte auditidentiteit, transacties en conflictcontrole nodig. Feedinname wordt met de opdracht gestart; er is geen terugkerende automatisering ingesteld.

## Bestaande appagenda / Strapi

Er is **geen tweede agenda** gebouwd. `app_content.py` leest server-side een gedeeld PITO-contentendpoint, als `PITO_APP_CONTENT_URL` is ingesteld. Een eventueel token staat uitsluitend in `PITO_APP_CONTENT_TOKEN`. Het endpoint moet de bestaande activiteit/occurrence-velden normaliseren naar `strapi/app-content-contract.example.json`. Dit voorbeeld is uitsluitend een contractfixture, geen echte activiteit. Alleen gepubliceerde records met expliciete webzichtbaarheid worden getoond; dubbele occurrences en verlopen dagen verdwijnen. Bij storingen worden geen oude of verzonnen activiteiten getoond.

De exacte actuele app/Strapi-codebase, endpoint, veldmapping en toegang ontbreken nog. Daardoor is de agenda nog niet live gekoppeld. Los gevonden externe evenementen zijn niet als appagenda opgenomen. De bestaande aanbiedingen blijven via de bestaande PITO-route bereikbaar en zijn fixtures; één apart gecontroleerde RWS-vacature is als bronverwijzing in de onderzoekseditie opgenomen.

## Nieuws naar Strapi

`python3 scripts/import_strapi.py` maakt een controleerbaar importplan zonder netwerkverzoeken.

Het voorbeeldschema in `strapi/schema.json` is een nieuw voorstel voor Strapi 5, niet een claim over jullie bestaande backend. Laat het inpassen in de actuele Strapi-codebase met Draft & Publish aan. Daarna kan een beheerder de import uitvoeren met `--apply` en deze procesvariabelen: `STRAPI_URL`, `STRAPI_TOKEN`, `STRAPI_MAJOR_VERSION=5`, `STRAPI_DRAFT_PUBLISH_CONFIRMED=true`. Optioneel `--approved-only`.

De import gebruikt expliciet `status=draft` en `publishedAt:null`, zoekt op unieke slug en slaat bestaande records over om CMS-redactiewerk niet te overschrijven. Geen automatische publicatie, geen productie-import uitgevoerd. Endpointrechten, versie, schema en live import zijn nog niet getest tegen jullie server. Raadpleeg [Strapi 5 REST status](https://docs.strapi.io/cms/api/rest/status).

## Vervolg voor productie

1. Actuele app/Strapi-codebase en gedeelde agenda-API aanwijzen; mapping en leesrechten testen.
2. Nieuwsroutes en rendering in de bestaande Laravel/Vue-codebase integreren; deze Python-server blijft alleen lokaal.
3. Nieuwscollectie, redactierollen, menselijke eindredactie en publicatiebeleid in Strapi instellen.
4. Provinciale en raadsdocumenten inhoudelijk ontsluiten. NDW heeft nog geen aangesloten DATEX II-adapter; ORI nog geen aangesloten API. Officiële bekendmakingen zijn deels handmatig gebruikt, niet volledig ingelezen.
5. Brondekking uitbreiden per gemeente, met monitoring van fetchfouten, correcties en intrekkingen. Niet iedere gemeente heeft al eigen nieuws in deze eerste selectie.

## Controle

Twaalf geautomatiseerde tests controleren routes, filters, HTML-escaping, feeddatums, XML-beveiliging, appagenda-publicatie/verval/deduplicatie, conceptafscherming, lokale goedkeuring, host/CSRF-controle en draft-only Strapi-payloads. Uitvoeren: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`.

Zie BRONNEN.md voor de gebruikte artikelen en hiaten, en CONTROLE.md voor de browsercontrole.


## Uitbreiding 10 oktober — twee weken
19 artikelen uit bronpublicaties 26 september–10 oktober, vaste rubrieken, zes PITO-illustraties en één CC0-archieffoto. Artikelpagina’s tonen gevolgen, datum/status, bronnen en beeldverantwoording. Zie BRONNEN.md voor volledige actuele inventaris. Inname standaard uitgebreid naar 26 september. Impact en imageKey worden in Strapi-concepten meegenomen; afbeeldingen en data/images.json moeten bij CMS-integratie mee worden gemigreerd.


## Zes maanden en impactrangschikking
Archief: http://127.0.0.1:4198/nieuws/utrecht?periode=archive
Selectieuitleg: http://127.0.0.1:4198/nieuws/selectie
42 artikelpagina’s, maand- en gemeentefilters, paginering, belangrijkste/nieuwste. Beoordeling 0–5 per criterium in lokale redactie. Ranking reist mee in Strapi-import als JSON. Zie REDACTIEMODEL.md voor criteria, testbare formule en grenzen. Peildatum blijft de historische preview van 10 oktober 2026; geen live nieuwsdienst.

## Lokale tabs en community
- `?weergave=vandaag`: gepubliceerde appactiviteiten op de peildatum, per gemeente.
- `?weergave=agenda`: komende appactiviteiten plus afzonderlijk gemarkeerde gemeentelijke bijeenkomsten (momenteel Baarn en Rhenen).
- `?weergave=community`: uitsluitend beoordeelde bijdragen, met publieke auteursnaam; meerdere bijdragers per gemeente.
- `/nieuws/meedoen?gemeente=baarn`: aanmelden als redacteur of verhaal indienen. Opslag alleen lokaal, geen e-mail of externe publicatie.
- `/nieuws/redactie`: aparte communitywachtrij; naam, contactgegevens, broncontrole, goedkeuren/afwijzen met beoordelaar en notitie. Beoordelingsgeschiedenis wordt per inzending bewaard.
- Databestand `data/community.json` is privéredactiedata. Niet statisch hosten of opnemen in een publieke export. Communityrecords gaan niet via de nieuwsimport naar Strapi.

Productiestap: bevestigde accounts, publieke auteursprofielen los van privécontactgegevens, auteurslidmaatschap van één of meerdere gemeenten, rol auteur/eindredacteur, uploadrechten, privacy- en bewaarbeleid, spambeperking en notificaties. De lokale naamvelden zijn geen identiteitsverificatie. De appagenda wacht nog op het bestaande endpoint; er zijn geen fictieve activiteiten, schrijvers of bijdragen toegevoegd. Datum voor Vandaag gebruikt dezelfde preview-peildatum als de editie.

## Fotografie en agenda-update
Zie `BEELD-EN-AGENDA.md` voor bronbeelden, rechten, ontwerpbronnen en het optionele web_images-contract. De zeven nieuwe foto's staan met maker en licentie in `data/images.json`. `static/refresh.css` bevat de PITO-website/app-afstemming. De live appagenda blijft afhankelijk van `PITO_APP_CONTENT_URL`; geen voorbeeldactiviteiten als echte evenementen gepubliceerd. Dagkeuze: `?weergave=vandaag&dag=morgen` of `dag=binnenkort`. QA: `design-qa.md`.


## Gemeentelijke archieven — 11 oktober 2026

De standaard nieuwsselectie is nu 11 juli t/m 11 oktober 2026. Oudere artikelen blijven bereikbaar via hun bestaande URL. De nieuwsvoorpagina gebruikt een lead met laatste nieuws ernaast en drie kolommen met beeld en kop.

Bronkaart: `/nieuws/redactie/gemeenten`. Gemeentelijke broninbox: `/nieuws/redactie/signalen?type=gemeenten`. De JSON/CSV-export staat in `data/municipal-source-inventory.*`. Een ontdekte link is niet automatisch een actieve feed; per bron staat de status vermeld.

Installeer voor de gemeentelijke collectors `python3 -m pip install -r requirements-intake.txt`. Een begrensde herhaalbare inname is `python3 scripts/news_pipeline.py --adapters municipal --start 2026-07-11 --end 2026-10-11 --max-pages 20`. Pas de datums bij een volgende editie expliciet aan. De collector volgt zichtbare links en gemeentelijke nieuwspaginering, inclusief de door Houten geadverteerde laadfragmenten. Bronpagina's staan privé in work; caches verversen na zes uur en inhoudsversies krijgen een eigen bestand.

`read_source_documents.py` leest primaire bronnen voor onderzoek; dit publiceert niets. `import_quarter_articles.py` importeert uitsluitend de afzonderlijk geschreven en aan bronrecords gekoppelde teksten in `work/quarter-sources/written.tsv` als lokale preview. Het bestand editorial-candidates.json gebruikt stabiele indices: niet hersorteren of vervangen. De import is op bron-URL herhaalbaar. Automatische broninname is nog geen automatische journalistieke eindredactie.

Stand: 268 eigen artikelen toegevoegd, 330 zichtbare artikelen binnen de driemaandsperiode. Dit is geen compleet archief. Van 545 onderzochte bronrecords konden 441 met tekst worden gelezen, 9 leverden geen bruikbare artikeltekst en 95 mislukten (77 toegangsweigeringen, 17 aanvraaglimieten en 1 ontbrekende pagina). Voor Leusden ontbreken bij meerdere berichten controleerbare publicatiedatums. Sportclubs, ondernemers, corporaties en ontwikkelaars zijn nog niet per gemeente volledig aangesloten. Gemeentelijke archiefpaginering is begrensd en is geen volledigheidsbewijs.

`python3 scripts/import_strapi.py` maakt de importplanning opnieuw, uitsluitend als concepten. Deze ronde heeft geen Strapi-mutaties of externe publicatie uitgevoerd. Verificatie staat in `data/quarter-verification.json`; browserbeelden en bronnenbewijs staan in `work/quarter-sources`.
