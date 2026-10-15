## Update 10 oktober 2026 — informatiebehoeften als standaard

De standaard is nu `relevance`, uitgelegd op `/nieuws/selectie`; bronnen, zoekdekking en beperkingen staan op `/nieuws/onderzoek` (`research.py`). De oudere impactformule hieronder blijft uitsluitend een alternatieve volgorde, niet de standaard. De nieuwe regels zijn onderzoeksgeïnformeerde productkeuzes, geen wetenschappelijk geschatte voorkeurpercentages.

`ranking.audienceNeed` is service, explanation, participation of connection; `audienceReason` is verplicht bij een label. Er zijn 16 recent geselecteerde conceptartikelen expliciet gelabeld op basis van de bestaande tekst; geen trefwoordclassificatie of verzonnen communityverhalen. `actionFrom` en `actionUntil` bepalen een concrete handelingsperiode. Alleen recent nieuws kan extra tijdsvoorrang krijgen. `alertConfirmed`, `alertCheckedOn`, goedgekeurde status, redacteur en lopende periode zijn samen vereist voor waarschuwingvoorrang. Er zijn geen echte alarmmeldingen geactiveerd. Elke import wordt defensief opnieuw beoordeeld; ongeldige metadata krijgt geen voorrang.

Volgorde: geverifieerde waarschuwing, lopende/binnen zeven dagen beginnende service of participatie, gemotiveerde informatiebehoefte, ongeclassificeerd. Binnen een groep wisselen de eerste zes posities behoeften af; dan gevolgen 0–5, rubriekspreiding, bronpublicatiedatum en slug. Geen spreiding in archief of onderwerpfilter. De datum is in deze historische preview vastgezet op 10 oktober 2026; dit is geen live waarschuwingsdienst. De nieuwe volgorde blijft over alle kaarten behouden, zonder hergroepering onder rubrieken. Gemeente blijft eerst een hard filter inclusief expliciet provinciale berichten. RSS blijft chronologisch.

Velden zijn te bewerken in de lokale redactie; bestaande auditlog en Strapi ranking-JSON nemen ze mee. Import-dry-run opnieuw opgebouwd; bestaande Strapi-concepten worden door de bestaande importer niet overschreven, dus reeds geïmporteerde verhalen vragen een bewuste CMS-migratie. Nog geen productieverbinding of publieksmeting. Onderzoeksverkenning omvat openbare geïndexeerde universitaire repositories; geen volledige systematische review. Raadpleeg de webverantwoording voor studies, methoden, beperkingen en evaluatievoorstel.

---

# PITO — nieuwsselectie en impactmodel v1

Stand: 10 oktober 2026. Werkend als lokaal prototype. De scores zijn voorlopige redactionele inschattingen, niet gebaseerd op gemeten bezoekersaantallen, bevolkingsmodellen of een getraind aanbevelingsmodel.

## Hoe nieuwsplatforms dit doen

De [NOS beschrijft](https://over.nos.nl/nieuws/persoonlijke-aanbevelingen-in-de-nos-app/) een redactioneel samengestelde voorpagina met daarnaast optionele persoonlijke aanbevelingen. Dat is geen openbaar bewijs van één universele formule voor alle nieuwswebsites. PITO gebruikt een transparante eigen weging. Geen individuele leesprofielen, cookies voor aanbevelingen of klikoptimalisatie toegevoegd.

## Eerst toelaten, daarna rangschikken

Een artikel heeft een bronlink, bronpublicatiedatum, vastgelegde broncontrole, rechtennotitie en geografische koppeling nodig. Verborgen concepten en afgewezen stukken blijven buiten overzichten. In deze lokale preview zijn geselecteerde concepten zichtbaar; openbare publicatie vereist eindredactie. Een onbetrouwbaar bericht wordt niet gered door een hoge impactscore.

Hoofdonderwerpen: politiek/bestuur, veiligheid, verkeer/OV, wonen/omgeving en voorzieningen. Geen buitenland zonder direct aantoonbare Utrechtse gevolgen. Geen grote hoeveelheid kleine vergunningen, parkeerbonnen of losse incidenten om de site te vullen.

## Score van maximaal 100

De vijf redactionele invoervelden zijn gehele getallen van 0 tot 5:

| Kenmerk | Factor | Maximum | Beoordeling |
|---|---:|---:|---|
| Gevolgen | 7 | 35 | Gezondheid/veiligheid, kosten, dagelijks functioneren, democratische betekenis |
| Bereik | 4 | 20 | Hoe breed raakt het de betrokken lokale gemeenschap? Geen automatisch voordeel voor een grote stad |
| Urgentie | 3 | 15 | Moeten inwoners op korte termijn handelen? Een voorbij incident krijgt 0 |
| Duur | 2 | 10 | Eenmalig effect tegenover maanden/jaren gevolgen |
| Handelingsperspectief | 1 | 5 | Kunnen inwoners concreet plannen, reageren, aanvragen of deelnemen? |
| Actualiteit | automatisch | 15 | Leeftijd van bronpublicatie, niet laatste tekstbewerking |

Gevolgenschaal: 0 geen onderbouwde gevolgen; 1 beperkt; 2 duidelijk maar klein; 3 merkbaar voor dagelijks leven; 4 groot voor veiligheid, bestaanszekerheid, dienstverlening of democratische keuzes; 5 zeer groot/structureel. Bereik 1 kleine groep, 3 substantieel deel doelgroep, 5 vrijwel hele betrokken gemeenschap. Urgentie 1 later relevant, 3 binnenkort handelen, 5 onmiddellijk handelen (alleen met actuele betrouwbare onderbouwing). Duur 1 kort, 3 maanden, 5 structureel. Handelingsperspectief 0 geen concrete actie, 3 bruikbare voorbereiding, 5 duidelijke actie met datum en route.

Actualiteit: leeftijd 0–1 dagen = 15; 2–3 = 12; 4–7 = 9; 8–14 = 5; ouder = 0. Urgentie vervalt na `activeUntil` en staat voor archiefberichten altijd op 0. Voorbeeld: groot spoorwerk rond Amersfoort komt hoger dan een afgehandeld klein incident. Een geagendeerde commissie krijgt minder gewicht dan een definitief verstrekkend besluit.

De gemeente is eerst een filter, geen heimelijke bonus. Op provinciaal niveau verlaagt herhaling in de eerste drie posities de selectiescore: 4 punten per eerdere gelijke rubriek (maximaal 8), 3 per eerdere identieke enkele gemeente (maximaal 6). Dit is een zachte correctie; een veel belangrijker verhaal kan nog steeds winnen. In de recente impactweergave staan overige berichten onder vaste rubrieken. Archief en Nieuwste eerst behouden over alle kaarten de gekozen volgorde. ‘Nieuwste eerst’ omzeilt impact en spreidingscorrectie.

Dubbele bronlinks of redactioneel gekoppelde dossier-ID’s worden samengenomen in het overzicht; de nieuwste bronpublicatie wint. Oudere artikelen blijven via hun eigen URL en maandselectie beschikbaar. Dit herkent nog niet automatisch alle semantisch gelijke berichten. De A12-updates uit mei/juli zijn als voorbeeld gekoppeld.

## Archief en actualiteit

42 artikelpagina’s uit 10 april–10 oktober: 2 april, 5 mei, 3 juni, 4 juli, 3 augustus, 8 september, 17 oktober. Dit is een selectie, geen complete zesmaandendekking van 26 gemeenten. Na samenvoeging van één dossier zijn er 41 verhalen in het brede archiefoverzicht. Alle maanden hebben een filter; archiefpagina’s tonen 12 verhalen per pagina. Recente editie bevat 19 artikelen. RSS beperkt tot de recente periode: archiefimport leidt niet tot een golf oude meldingen.

Oude waarschuwingen krijgen een archieflabel, geen actuele noodstatus. Ook een oud plan dat mogelijk nog relevant is blijft in het archief tot een redactioneel gecontroleerd vervolgbericht wordt gemaakt. Dit is bewust eenvoudig; een toekomstig dossierblok kan langlopende plannen opnieuw toetsen zonder oude datums te veranderen.

## Meer relevante redactionele punten

- Maak bij vergunningen onderscheid tussen aanvraag, ontwerp, besluit en onherroepelijkheid. OmgevingsAlert signaleert; de originele bekendmaking onderbouwt het artikel.
- Bij conflicten: voeg wederhoor en onafhankelijke context toe. Gemeenteberichten geven het perspectief van het bestuur weer.
- Beperk persoonsgegevens van verdachten, slachtoffers en minderjarigen. Een verdenking is geen veroordeling.
- Houd wijzigingen, motivering en correcties bij. De lokale redactie schrijft wijzigingen naar een auditlog; productie heeft geauthenticeerde rollen en centraal log nodig.
- Geef kleine gemeenten ruimte, maar vul lege gemeentepagina’s niet met irrelevante berichten.
- Activiteiten/agenda komen uit de bestaande app; vacatures, aanbiedingen en PITO-promotie staan los van nieuwsrangschikking.
- Meet later geaggregeerd doorklikken, leestijd, terugkerend bezoek, bronkliks en correcties, uitgesplitst naar onderwerp/gemeente. Combineer die met redactionele kwaliteit; maak kliks niet de leidende score.
- Evalueer gewichten met echte lezers en redacteuren. Dubbel beoordelen van een steekproef helpt subjectieve scoreverschillen zichtbaar maken.
- Voor automatische meldingen: expliciete bronstatus, korte vervaltijd, laatste controle en terugtrekking nodig. Nog geen pushmeldingen of alarmfunctie geïmplementeerd.

## Nog open

Structurele archiefadapters, volledige geografische dekking, ORI/NDW/OmgevingsAlert-contracten, productie-Strapi en bestaande app-agenda. RSS-feeds bewaren vaak alleen recente items; een ruimer datumfilter reconstrueert geen ontbrekend historisch archief. De 23 nieuwe historische artikelen zijn afzonderlijk onderzocht. Huidige bronvoorwaarden, privacy, beeldrechten en redactionele verantwoordelijkheid blijven onderdeel van eindcontrole.
