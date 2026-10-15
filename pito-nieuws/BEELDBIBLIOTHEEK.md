# PITO beeldbibliotheek en Utrecht-ingang — 10 oktober 2026

De provinciale ingang staat op /nieuws/utrecht. Het hoofdmenu Nieuws opent deze pagina. Het gekozen ontwerp ‘Dit is jouw Utrecht’ is op verzoek verkort: 330 px desktop en 300 px mobiel. De bestaande homepage, header en nieuwsindeling blijven behouden.

## Beelden

22 artikelbeelden: 8 bestaande gelicentieerde foto's en 14 nieuwe AI-sfeerbeelden. Elk heeft een assetId, onderwerpstags en provenance. media_library.assign kiest relevante beelden per render met maximum matching, zodat een beeldidentiteit niet op twee artikelkaarten voorkomt. Bestandsaliassen/uitsneden moeten dezelfde assetId behouden. Dit is metadata-gebaseerde controle, geen automatische visuele herkenning van identieke afbeeldingen. Alle 19 recente berichten krijgen momenteel een verschillend passend beeld. Bij tekorten volgt geen willekeurige vervanging.

De artikel-link bewaart het geselecteerde beeld in de parameter beeld; de server accepteert alleen relevante catalogusbeelden. De canonical blijft de artikel-URL zonder parameter. Gegenereerde beelden zijn gemarkeerd AI-sfeerbeeld, echte foto's behouden maker/licentie/archiefaanduiding. De hamer is uitsluitend symbolisch en krijgt geen algemene politietag.

Catalogus: /nieuws/beeldbibliotheek. JSON: /api/media-library. Strapi-conceptimport neemt imageKey en imageTopics mee. Werkelijke media-upload, native app-rendering en productie-opslag zijn niet aangesloten; daar moet dezelfde selectie per volledige pagina worden toegepast.

## Gemeentelijke openingsbeelden

17 van 26 gemeenten hebben een gekoppeld lokaal beeld. Vijftien komen uit de eerdere PITO-cloudselectie; Woerden en Montfoort zijn aangevuld met Wikimedia Commons-foto’s onder CC BY-SA 3.0, inclusief maker, jaartal, bronlink, licentielink en uitsnedevermelding. Zie data/municipality-images.json.

Amersfoort, Rhenen en Vinkeveen hebben nieuwe AI-bewerkingen op basis van de eigen dronepreview, zonder browserranden of bestandsnamen. Deze zijn decoratief, herkenbaar als AI-bewerkt en mogen niet dienen als exacte locatie-documentatie of bewijs van nieuwsfeiten. AI kan details veranderen. Voor productie heeft directe kleurcorrectie van originele hoge-resolutie videoframes de voorkeur. De andere cloudbeelden zijn bestaande gecropte preview-assets; originele exports ontbreken nog.

Nog geen geschikte recente overzichtsfoto geselecteerd: Bunschoten, De Bilt, Eemnes, Houten, Lopik, Oudewater, Stichtse Vecht, Utrecht-stad en Vijfheerenlanden. De zoekronde leverde voor veel plaatsen vooral historisch materiaal (1920–1940/1977) op. Dat is niet als actuele gemeenteopening gebruikt. De pagina toont expliciet ‘Nog geen lokaal luchtbeeld · provinciebeeld: Amersfoort’. Geen verzonnen stadsgezicht wordt als echte plaats gepresenteerd.

## Agenda

Gemeenteagenda toont primair dezelfde gepubliceerde, voor web toegestane activiteiten als de PITO-app, gefilterd op municipality. Vandaag/morgen gebruikt dezelfde bron en gemeente. Raadsbijeenkomsten staan als afzonderlijke sectie daaronder. De echte Strapi/PITO-contentendpoint is nog niet geconfigureerd; daarom toont de preview eerlijk een lege appagenda. Geen demonstratieactiviteiten toegevoegd als echte evenementen.

## Verificatie

33 tests geslaagd: routes, gemeentefilters, moderatie, agenda, matching, aliasidentiteit en dekking recente editie. Browser: 19 artikelbeelden/19 unieke bronnen; gemeente Baarn wisselt beeld en agenda; drie provinciale fotokeuzes werken; zoekterm rechtspraak vindt twee beelden; desktop 1488×1058 en mobiel 390×844 zonder horizontale pagina-overflow; geen browserconsolefouten tijdens eindcontrole.
