# Fotografie en PITO-appagenda — 10 oktober 2026

## Beeld
Acht echte archieffoto’s beschikbaar, inclusief de eerder aanwezige Utrecht Centraal-foto. Zeven nieuwe beelden: Amersfoort Centraal (2024), stadskantoor Utrecht (2021), Utrechtse raadzaal (2005), A12 Lunetten (2011), algemene Nederlandse politiebus (2017), Leidsche Rijn (2020), gemeentehuis Soest (2017). Makers, bronpagina’s, opnameperiode, licenties en visuele controle staan in data/images.json. Foto’s met CC BY-SA en de weergegeven uitsneden blijven onder dezelfde beeldlicentie. De licentie geldt niet voor het hele nieuwsartikel.

Er wordt geen foto van een ander gemeentehuis als het plaatselijke gemeentehuis gepresenteerd. Utrechtse raadzaal is waar gebruikt expliciet sfeerbeeld; geen foto van de besproken vergadering. Geen politie.nl-foto’s overgenomen: https://www.politie.nl/algemeen/disclaimer.html sluit beeldhergebruik onder de algemene toestemming uit. Afzonderlijke toestemming blijft mogelijk.

Geen illustratief standaardbeeld meer. Zonder geschikt beeld verschijnt een tekstbericht. Geen fotorealistische AI-nieuwsfoto’s gegenereerd; echte locatiebeelden hebben voorrang. Eventuele toekomstige AI-sfeerbeelden moeten herkenbaar als zodanig worden aangeduid.

## App- en webpatronen
Bronnen: bestaande PITO-webpreview van 25 september; officiële app-screenshot public/assets/app-screens-official/agenda.png uit de lokale PITO-codebase; activiteitenoverzicht app-agenda.png uit sector-assets van 28 september.

Nieuws blijft in de bestaande PITO-website onder Nieuws. Originele header/footer/home behouden. Typografie en knoppen sluiten aan op de website. Nieuwssubnavigatie gebruikt appkleur/onderstreping; filters zijn inklapbaar. Vandaag/Morgen/Binnenkort werken per gemeente. Agenda heeft leesbare activiteitenkaarten, datumblokken en gemeentelijke bijeenkomsten. De app-screenshot op de pagina is nadrukkelijk een ontwerpvoorbeeld en geen actuele agenda.

De live Strapi-appagenda is nog niet aangesloten; er worden daarom geen activiteiten verzonnen. PITO_APP_CONTENT_URL blijft het bestaande contract gebruiken. Optioneel web_images per activiteit: [{url: HTTPS, alt: beschrijving, credit: rechtenvermelding, web_usage_approved: true}]. Alleen goedgekeurde beelden met credit worden als de horizontale appfotogalerij weergegeven. Bronapp moet juiste rechtenvermelding en licentievoorwaarden leveren; het vinkje bewijst geen rechten. Toekomstige publieke aansluiting moet dit server-side afdwingen.

## Controle
28 tests geslaagd: alle 26 gemeenten, bron- en reviewgrenzen, formuliercontrole, agenda datums/gemeente, beeldtoestemming. Browser: desktop 1440 × 1050 en mobiel 390 × 844; archief mei levert 5 artikelen, Morgen-tab, gemeente Baarn en agenda, geen horizontale pagina-overloop. Live appactiviteit/data blijft een integratiehiaat.
