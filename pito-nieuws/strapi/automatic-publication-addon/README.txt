APARTE CONTROLEBOT — 29 OKTOBER 2026
De huidige publicatieroute gebruikt een aparte PITO_NEWS_REVIEW_TOKEN.
Bij een ingestelde reviewsleutel is /automatic-publish voor de schrijver geblokkeerd.
GET /api/pito-news/review-queue geeft versies, bewijs en beschermingsredenen.
POST /api/pito-news/review-decision beoordeelt alleen opgeslagen tekst en kan
publiceren of een hold-verslag opslaan. Menselijke wijzigingen en intrekkingen
blijven beschermd. De ingediende versie wordt binnen dezelfde transactie getoetst.
reviewKind=automatic en humanReviewed=false blijven ook bij aparte controle gelden.
Geen schemawijziging; deploy index.ts, reviewer.ts, controller en routes plus JS-build.
22 domeintests en 18 echte Strapi/PostgreSQL-integratiechecks zijn geslaagd.
Het volledige botprotocol staat in ../../GROKBOT-EINDREDACTIE.txt.

HISTORISCHE STATUS

HERSTEL PUBLICATIE — 29 OKTOBER 2026
Eigenaar heeft expliciet DOORLOPEND publiceren toegestaan. Live Strapi heeft
nu PITO_NEWS_AUTOMATIC_PUBLISH_ENABLED=1; de tijdelijke vervaldatum is verwijderd.
De bestaande DRAFT_TOKEN en /automatic-publish blijven gelden; /drafts blijft
alleen concepten opslaan. Bron-/datum-/bewijscontroles blijven ongewijzigd.
Identieke, nog ongewijzigde eigen botconcepten kunnen alsnog publiceren met
HTTP 200, hetzelfde documentId en newlyPublished=true. Menselijke saves,
gewijzigde voorstellen, verwijderingen en intrekkingen worden nooit overschreven.
Handmatig in Strapi: echte controle uitvoeren, Beoordelings- of correctienotitie
invullen, Redactionele beoordeling=approved, Save, daarna Publish. Bij die
expliciete goedkeuringsactie vult de server verifiedAt zelf met het echte
tijdstip. De datumkiezer is alleen-lezen. Foutmeldingen geven deze stappen aan.
Getest: 22 domeintests en 10 echte Strapi/PostgreSQL-integratiechecks, inclusief
handmatig goedkeuren/publiceren, doorlopende toegang ondanks oude vervaldatum,
concept alsnog publiceren, bescherming menselijke wijzigingen/intrekkingen en
behoud van bestaande dashboardindeling.
Back-up: /srv/pito-backups/publication-fix-20261029 op de CMS-server.
De bestaande Grok-routine (06:00 Europe/Amsterdam, maximaal40Firecrawl-credits)
wordt aangepast naar publiceren; geen extra betaalde crawl of tweede routine.
Geen nieuwe API-sleutel nodig. Afbeeldingen zijn met dit herstel niet uitgebreid.

HISTORISCHE STATUS

PITO Nieuws — automatische publicatie-uitbreiding, 26 oktober 2026
Overlay voor de bestaande PITO-nieuwsuitbreiding op Strapi 5.50.2.
De complete bestaande Strapi-app blijft vereist; dit is geen losse app.

POST /api/pito-news/automatic-publish gebruikt PITO_NEWS_DRAFT_TOKEN.
De server staat deze route alleen toe vóór de expliciet ingestelde UTC-tijd
PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL; standaard en na afloop is de route dicht.
De eigenaar heeft één ronde vanaf 26 oktober 2026 geautoriseerd.
/drafts blijft apart en publiceert nooit automatisch.

Automatische aanvoer vereist een actieve RSS-bron uit de beheerde catalogus,
passende bronhost/pad, recente bronpublicatie, volledige broninhoud met
ophaal-/controletijd, letterlijke bewijsfragmenten en gemeentebewijs.
Gevoelige en provinciebrede artikelen blijven concept. Ontbrekende gegevens
worden niet aangevuld met verzonnen feiten. Bestaande redactiewijzigingen,
intrekkingen en verwijderingen worden nooit door retries teruggedraaid.

Deze structurele controles zijn geen onafhankelijke semantische feitencheck.
De bot controleert de inhoud; de server registreert reviewKind=automatic en
humanReviewed=false. Menselijke review vereist nog steeds een echte CMS-login.
Bewijs en automatische beoordeling blijven privé; de snapshot toont alleen
het type beoordeling en auteurschap. De website-adapter is hiervoor aangepast.

Tests: 21 domeintests, 20 website-adaptertests en 6 echte Strapi/PostgreSQL-
integratiechecks met een tijdelijke lokale database. Geen testartikel is op
productie gezet. Zie scripts/test_automatic_strapi_e2e.cjs en reports/.
Live back-ups: /srv/pito-backups/automatic-20261026 op beide betrokken servers.
