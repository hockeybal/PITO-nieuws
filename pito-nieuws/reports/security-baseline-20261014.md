# Security Review: pito-nieuws

## Scope

Repository-wide offline static security audit of the supplied directory, prioritizing HTTP runtime and its content pipelines; no source mutations.

- Scan mode: repository
- Target kind: directory_snapshot
- Target ID: target_sha256_91d1bdc36b70841b5d2fc665269d777e07a143b523825a2799b9b12e2850e031
- Snapshot digest: codex-security-snapshot/v1:sha256:e543b70d0e2e366d705b5059a2a28e9330d1090501c6c9680742b79178402c95
- Inventory strategy: directory
- Included paths: .
- Excluded paths: none
- Artifacts reviewed: PITO-PROJECTAFSPRAKEN.txt, README.md, RECHTEN-EN-PUBLICATIE.txt, START-HIER-DEVELOPER.txt, agenda_views.py, app_content.py, archive_navigation.py, base.json, club_directory.py, club_identity.py, community.py, coverage.py, data/setup.py, dossiers.py, editorial.py, environment_notices.py, facts.py, frontpage.py, homepage_agenda.py, housing.py, latest_news.py, legal.py, local_features.py, local_services.py, location_prompt.py, masthead.py, media_coverage.py, media_library.py, municipal_inventory.py, municipality_overview.py, news.py, newsroom.py, official_content.py, photo_research.py, portable_handler.py, preferred_source.py, promotions.py, ranking.py, requirements-intake.txt, rights_review.py, scripts/amber_intake.py, scripts/audit_image_coverage.py, scripts/audit_local_addresses.py, scripts/audit_local_sport.py, scripts/audit_media_sources.py, scripts/audit_routes.py, scripts/build_club_photo_queue.py, scripts/build_club_photo_review.py, scripts/build_editorial_covers.py, scripts/build_local_coverage.py, scripts/build_municipal_source_handoff.py, scripts/build_processing_desk.py, scripts/build_source_gap_audit.py, scripts/build_source_work_queue.py, scripts/connect_discovered_feeds.py, scripts/connect_regional_feeds.py, scripts/connect_sports_feeds.py, scripts/council_intake.py, scripts/coverage_readiness.py, scripts/discover_club_logos.py, scripts/discover_club_photos.py, scripts/discover_councils.py, scripts/discover_sources.py, scripts/enrich_official_publications.py, scripts/expand_football_sources.py, scripts/expand_media_sources.py, scripts/import_quarter_articles.py, scripts/import_strapi.py, scripts/intake.py, scripts/koop_intake.py, scripts/municipal_archive_intake.py, scripts/municipal_source_inventory.py, scripts/ndw_intake.py, scripts/news_pipeline.py, scripts/prepare_base_archive.py, scripts/prepare_news_draft.py, scripts/read_source_documents.py, scripts/reconcile_identical_sources.py, scripts/regional_archive_intake.py, scripts/source_coverage_refresh.py, scripts/source_report.py, scripts/test_source_catalog.py, scripts/vru_intake.py, search_visibility.py, seo-production.env.example, seo.py, seo_review.py, server.py, signals.py, source_attribution.py, source_overview.py, start-local.command, starter.py, static/campaign.js, static/latest-news.js, static/location.js, static/masthead.js, static/navigation.js, static/news-footer.html, static/news.js, topic_policy.py, useful_addresses.py, weather.py
- Scan context: Received local preview is to run locally before any future live deployment. Threat model generated during this scan; one independent baseline and scan-owner review, with no independent architecture reviewer due to occupied runtime slots.

Limitations and exclusions:
- No application code or network execution by audit owner.
- Directory is not a Git repository and implementation may be edited concurrently by parent task.
- Large JSON datasets, generated evidence HTML/SVG, binary assets, all historical documents and all tests were not individually audited; source searches do not establish complete coverage.
- The immutable report records pre-hardening findings; the parent task's subsequent fixes and unit tests are a separate implementation step.

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 1 |
| Severity mix | low: 1 |
| Confidence mix | high: 1 |
| Coverage | partial |
| Validation mode | static |

Canonical artifacts: `scan-manifest.json`, `findings.json`, and `coverage.json`. This report is a deterministic projection of those files.

## Threat Model

PITO Nieuws is a server-rendered Python local preview for news, community, activities, official notices and address information. server.py:9-14 selects a portable handler by default (base.json contains ./portable-assets), optionally importing a separately supplied legacy preview module; server.py:280-282 binds only 127.0.0.1. Read-only pages use news.py:13-36 JSON data + templates. Local editorial POST routes mutate articles/community JSON (server.py:232-278; community.py:7-11). Privileged CLI tooling can fetch source material and explicitly import Strapi drafts (scripts/import_strapi.py:12-35).

### Assets

- Local articles, drafts and approval history in data/articles.json and data/audit.jsonl; writer save() uses a sibling .tmp + replace() while the shared threading lock serializes HTTP edits (server.py:15-16,251-277).
- Private contributor email, evidence and moderation notes in data/community.json; community.admin() renders contact records only on the local editorial page (community.py:7-11,81-86; server.py:181).
- Server-side PITO_APP_CONTENT_TOKEN and STRAPI_TOKEN are environment references, not browser-provided credentials (app_content.py:37-41; scripts/import_strapi.py:18-23).
- Publication integrity: preview/approved content is locally visible; production news additionally requires search_visibility.published() (news.py:18), while shared remote activity content requires status published and show_on_web true (app_content.py:13-30).

### Trust Boundaries

- External browser document -\> loopback preview: Host must exactly match 127.0.0.1:\<port\> or localhost:\<port\> (server.py:47-49); editorial writes additionally require same-origin Origin and the random X-Pito-CSRF token (server.py:14,235-241). There are no named accounts; a user who can read the local editor can obtain the shared token (server.py:39).
- URL path -\> local static file: portable_handler.py:11-14 resolves target and requires it to remain under the requested base. News MP4 range handler independently requires containment under static (server.py:204-224). Private data/work/report directories are outside these statically allowed routes (portable_handler.py:18-22).
- Structured content -\> browser markup: news.e() escapes HTML attributes/text (news.py:14); JSON-LD serialization replaces literal \< (news.py:35); article body is emitted as escaped paragraphs (newsroom.py:10-20). Imported URLs need their own scheme checks.
- Server -\> configured shared app endpoint: app_content.get() builds endpoint and optional bearer Authorization from operator-controlled environment; HTTPS or loopback HTTP, five-second network timeout, two-megabyte response bound, 60-second cache (app_content.py:32-47). This is not a request-supplied endpoint.
- Operator CLI -\> Strapi CMS: --apply, token + base URL, version 5 and confirmed Draft & Publish are required; payload publishedAt null + status=draft, existing slug records skipped (scripts/import_strapi.py:7-35). User-facing HTTP routes do not invoke this importer.
- Discovery source HTML -\> same-origin generated source reports is a distinct boundary: external hrefs are keyword-selected and retained after failed council fetch, then render into source-audit anchors (scripts/discover_sources.py:11,25; scripts/discover_councils.py:10-17; scripts/municipal_source_inventory.py:18-23; scripts/build_source_gap_audit.py:38,50). This is not the safely escaped article-text path.

### Attacker Capabilities

- An external attacker can send an operator a loopback URL with arbitrary path/query and can host a separate web origin; they do not initially know the CSRF token or read local JSON under browser same-origin policy.
- A process capable of direct loopback requests can read the editor and then mutate the local preview; local OS user/account isolation is assumed rather than provided by this preview.
- Imported source content and a configured shared app endpoint can supply content data; only operator-controlled configuration selects filesystem roots or credential-bearing destinations.
- Publishing this server behind a reverse proxy would add remote reachability absent from the supported deployment; production authentication/role boundaries are not implemented in this local preview.

### Security Objectives

- Keep local preview reachable only via loopback and reject unexpected Hosts / cross-origin writes.
- Keep draft and personal contributor data out of public exports and approved production pages.
- Prevent imported text and query values from becoming executable browser markup or local file paths.
- Keep CMS tokens server-side and require deliberate operator action for Strapi draft import.
- User request: make the received project locally viewable, tidy and appropriately secured before any future public release; no public deployment is authorized by this audit.

### Assumptions

- Exact user context retained by scan host; no user-supplied threat model or knowledge base; root SECURITY.md resolver returned no applicable policy.
- START-HIER-DEVELOPER.txt:20-31 explicitly says this Python server is only a local preview and must not be publicly exposed; production should port routes into the actual Laravel/Vue app.
- base.json:1 resolves ./portable-assets relative to startup cwd; supported standalone PITO_STANDALONE=1 prevents importing legacy Python source from PITO_BASE_PREVIEW. That override is operator authority, not public input.
- PITO_SITE_MODE=production changes content/indexing rules, not bind address, accounts, roles or editorial route protection (server.py:47-49,181,232-282; news.py:18).
- Independent architecture reviewer could not start because all active worker slots were occupied; architecture mapping performed sequentially by scan owner. Independent baseline is running.
- No network requests, application execution or live deployment tests performed by scan owner; validity of external API and CMS credentials unknown and not checked.
- Audit reviews current mutable directory snapshot; parent may apply fixes during work, so pre-fix locations/evidence are retained and follow-up changes must be distinguished from the original scan.
- Architecture and finding evidence describe the received source before parent hardening; concurrent edits and resulting CSP/auth changes are not retroactively represented as original controls.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [A discovered council link can run JavaScript in the local editorial preview](#finding-1) | low | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] A discovered council link can run JavaScript in the local editorial preview

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | Static source establishes each external href transformation, persistence, unvalidated fallback and executable same-origin href sink. No browser reproduction or existing poisoned artifact was asserted. |
| Category | Stored cross-site scripting through executable source URLs |
| CWE | CWE-79 |
| Affected lines | scripts/discover_sources.py:11, scripts/discover_sources.py:25, scripts/discover_councils.py:10, scripts/discover_councils.py:17, scripts/municipal_source_inventory.py:18-23, scripts/build_source_gap_audit.py:38, scripts/build_source_gap_audit.py:50, server.py:52, server.py:39, server.py:240 |

#### Summary

After municipal discovery and source-report generation, clicking an attacker-supplied `javascript:` council link can execute code in the local PITO preview origin. The injected code can read private community contact details and obtain the editorial CSRF token to modify local articles or moderation state. This concerns the received preview's discovery-to-report path, before the parent task's hardening changes; public production deployment is not established.

#### Root Cause

External council hrefs are selected by text keywords and persisted even when fetching fails, then promoted into clickable same-origin report links. The rendering helper validates HTML syntax only, so source data can become an executable `javascript:` URL with the local editor's authority.

**External homepage href enters discovery** — `scripts/discover_sources.py:11`

An upstream municipal page controls href text. No parsed scheme constraint applies when Links stores it for council selection.

```python
  if tag=='a' and d.get('href'):self.links.append(d['href'])
```

**Council keyword selection preserves executable schemes** — `scripts/discover_sources.py:25`

A javascript: href containing one council keyword passes this substring selection. urljoin preserves its absolute scheme, and the value is persisted in the discovery row.

```python
  parser=Links();parser.feed(raw.decode('utf-8','replace'));row.update(title=parser.title,homepage=final,status='reachable',feeds=list(dict.fromkeys(urllib.parse.urljoin(final,x) for x in parser.feeds)),councilLinks=list(dict.fromkeys(urllib.parse.urljoin(final,x) for x in parser.links if any(s in x.lower() for s in ('gemeenteraad','raadsinformatie','notubiz','ibabs','bestuur','besluit'))))[:10])
```

**URL is saved before fetching and survives failure** — `scripts/discover_councils.py:10-17`

The attempted fetch rejects unsupported URL schemes but the exception path keeps councilCheckedUrl as a stored discovery candidate.

```python
 target=max(links,key=score);result=dict(row);result['councilCheckedUrl']=target
 try:
  req=urllib.request.Request(target,headers={'User-Agent':'PITO-source-discovery/1.0 (local editorial research)'})
  with urllib.request.urlopen(req,timeout=15) as r:raw=r.read(2_000_000);url=r.url
  parser=Links();parser.feed(raw.decode('utf8','replace'))
  found=list(dict.fromkeys(urllib.parse.urljoin(url,x) for x in parser.links if any(w in x.lower() for w in ['raadsinformatie','bestuurlijkeinformatie','notubiz','ibabs','gemeentebestuur','raadsagenda','raadsvergadering','vergaderingen','raadlive'])))
  result.update(councilStatus='page_verified',councilFinalUrl=url,councilPortals=found[:12],councilCheckedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except Exception as e:result.update(councilStatus='needs_manual_check',councilError=str(e))
```

**Unchecked failed council candidate enters source inventory** — `scripts/municipal_source_inventory.py:18-23`

On fresh/unresolved discovery no councilFinalUrl overrides the failed candidate. add accepts the executable fallback and writes it into municipal source inventory.

```python
  def add(topic,name,url,state,evidence,workflow):
   if not url or (topic,url) in seen:return
   seen.add((topic,url));found.append(dict(topic=topic,name=name,url=url,state=state,evidence=evidence,workflow=workflow))
  ar=reports.get(slug,{})
  for url in ar.get('archiveUrls',[]):add('Gemeentenieuws','Nieuwsarchief '+m['name'],url,ar.get('status','onbekend'),m['homepage'],'Gemeentelijke archiefadapter → privé broncontrole → eigen concept')
  add('Bestuur & besluiten','Gemeenteraad',m.get('councilFinalUrl') or m.get('councilCheckedUrl'),m.get('councilStatus','onbekend'),m['homepage'],'OpenBesluitvorming waar beschikbaar; voorstel en besluit afzonderlijk lezen')
```

**HTML escaping leaves a javascript URL executable** — `scripts/build_source_gap_audit.py:38`

Escaping protects attribute syntax but does not reject the javascript scheme. The generated current-tab anchor executes the URL in the report's document origin on click.

```python
 def link(u,t):return '<a href="'+esc(u)+'">'+esc(t)+'</a>'
```

**Every municipal source URL reaches the anchor helper** — `scripts/build_source_gap_audit.py:50`

The council fallback persisted in sources is rendered as a clickable report link, without checking its fetch status or scheme.

```python
  body+='<details><summary>'+esc(c['name'])+'</summary><h3>Lokale media</h3><p>'+ ' · '.join(link(m['url'],m['name']) for m in mm)+'</p><h3>Officiële en lokale routes</h3><ul>'+''.join('<li>'+link(s['url'],s['name'])+' — '+esc(s.get('state','onbekend'))+'</li>' for s in c['sources'])+'</ul></details>'
```

**Generated reports share the preview origin** — `server.py:52`

static/source-audit/index.html is served within the same origin as the local editor rather than an isolated evidence viewer.

```python
  if p.startswith('/news-static/'):return self.file(ROOT/'static',p[len('/news-static/'):])
```

**Same-origin script can obtain the shared editor token** — `server.py:39`

admin returns private community details and the token in HTML. Injected same-origin code can fetch this page and then satisfy the Origin/CSRF guard.

```python
 return news.layout('Redactie',community.admin()+content,'/nieuws/redactie').replace('</head>',f'<meta name="csrf" content="{TOKEN}"></head>')
```

#### Validation

The full fresh-discovery -\> failed council fetch -\> unchecked inventory fallback -\> current-tab href -\> same-origin editor chain is established from current source. The baseline proposed medium; owner calibrated low for manual workflow, upstream compromise and local-only impact.

Validation method: offline static source trace and independent baseline reconciliation

- **Status:** validated
- **Disposition:** reportable

**Council keyword selection preserves executable schemes** — `scripts/discover_sources.py:25`

A javascript: href containing one council keyword passes this substring selection. urljoin preserves its absolute scheme, and the value is persisted in the discovery row.

```python
  parser=Links();parser.feed(raw.decode('utf-8','replace'));row.update(title=parser.title,homepage=final,status='reachable',feeds=list(dict.fromkeys(urllib.parse.urljoin(final,x) for x in parser.feeds)),councilLinks=list(dict.fromkeys(urllib.parse.urljoin(final,x) for x in parser.links if any(s in x.lower() for s in ('gemeenteraad','raadsinformatie','notubiz','ibabs','bestuur','besluit'))))[:10])
```

**URL is saved before fetching and survives failure** — `scripts/discover_councils.py:10-17`

The attempted fetch rejects unsupported URL schemes but the exception path keeps councilCheckedUrl as a stored discovery candidate.

```python
 target=max(links,key=score);result=dict(row);result['councilCheckedUrl']=target
 try:
  req=urllib.request.Request(target,headers={'User-Agent':'PITO-source-discovery/1.0 (local editorial research)'})
  with urllib.request.urlopen(req,timeout=15) as r:raw=r.read(2_000_000);url=r.url
  parser=Links();parser.feed(raw.decode('utf8','replace'))
  found=list(dict.fromkeys(urllib.parse.urljoin(url,x) for x in parser.links if any(w in x.lower() for w in ['raadsinformatie','bestuurlijkeinformatie','notubiz','ibabs','gemeentebestuur','raadsagenda','raadsvergadering','vergaderingen','raadlive'])))
  result.update(councilStatus='page_verified',councilFinalUrl=url,councilPortals=found[:12],councilCheckedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except Exception as e:result.update(councilStatus='needs_manual_check',councilError=str(e))
```

**Unchecked failed council candidate enters source inventory** — `scripts/municipal_source_inventory.py:18-23`

On fresh/unresolved discovery no councilFinalUrl overrides the failed candidate. add accepts the executable fallback and writes it into municipal source inventory.

```python
  def add(topic,name,url,state,evidence,workflow):
   if not url or (topic,url) in seen:return
   seen.add((topic,url));found.append(dict(topic=topic,name=name,url=url,state=state,evidence=evidence,workflow=workflow))
  ar=reports.get(slug,{})
  for url in ar.get('archiveUrls',[]):add('Gemeentenieuws','Nieuwsarchief '+m['name'],url,ar.get('status','onbekend'),m['homepage'],'Gemeentelijke archiefadapter → privé broncontrole → eigen concept')
  add('Bestuur & besluiten','Gemeenteraad',m.get('councilFinalUrl') or m.get('councilCheckedUrl'),m.get('councilStatus','onbekend'),m['homepage'],'OpenBesluitvorming waar beschikbaar; voorstel en besluit afzonderlijk lezen')
```

**HTML escaping leaves a javascript URL executable** — `scripts/build_source_gap_audit.py:38`

Escaping protects attribute syntax but does not reject the javascript scheme. The generated current-tab anchor executes the URL in the report's document origin on click.

```python
 def link(u,t):return '<a href="'+esc(u)+'">'+esc(t)+'</a>'
```

**Every municipal source URL reaches the anchor helper** — `scripts/build_source_gap_audit.py:50`

The council fallback persisted in sources is rendered as a clickable report link, without checking its fetch status or scheme.

```python
  body+='<details><summary>'+esc(c['name'])+'</summary><h3>Lokale media</h3><p>'+ ' · '.join(link(m['url'],m['name']) for m in mm)+'</p><h3>Officiële en lokale routes</h3><ul>'+''.join('<li>'+link(s['url'],s['name'])+' — '+esc(s.get('state','onbekend'))+'</li>' for s in c['sources'])+'</ul></details>'
```

**Generated reports share the preview origin** — `server.py:52`

static/source-audit/index.html is served within the same origin as the local editor rather than an isolated evidence viewer.

```python
  if p.startswith('/news-static/'):return self.file(ROOT/'static',p[len('/news-static/'):])
```

**Same-origin script can obtain the shared editor token** — `server.py:39`

admin returns private community details and the token in HTML. Injected same-origin code can fetch this page and then satisfy the Origin/CSRF guard.

```python
 return news.layout('Redactie',community.admin()+content,'/nieuws/redactie').replace('</head>',f'<meta name="csrf" content="{TOKEN}"></head>')
```

Assertions:
- urljoin retains an absolute javascript: scheme.
- Council fetch failure does not remove the checked URL.
- Inventory add has no scheme guard and uses councilCheckedUrl as fallback.
- The report anchor helper emits current-tab href values and is served by the preview.

Counterevidence and remaining uncertainty:
- Requires attacker-controlled municipal source, operator CLI sequence and editor click.
- An existing valid councilFinalUrl overrides the fallback.
- The ordinary article/community text path is escaped and community href inputs require HTTPS.
- Local-only server does not publish edits to a public CMS.

Limitations:
- No browser proof of concept executed; no poisoned current dataset asserted.
- Parent may concurrently harden server CSP; this is pre-hardening source evidence.

#### Dataflow

External href -\> Links.links -\> councilLinks -\> councilCheckedUrl -\> inventory sources\[\].url -\> report link(u,t) -\> javascript URL in preview origin

- **Source:** External municipal homepage href

- **Sink:** Current-tab href in generated static/source-audit/index.html

- **Outcome:** Local editor read/write authority is available to external-source JavaScript

**Council keyword selection preserves executable schemes** — `scripts/discover_sources.py:25`

A javascript: href containing one council keyword passes this substring selection. urljoin preserves its absolute scheme, and the value is persisted in the discovery row.

```python
  parser=Links();parser.feed(raw.decode('utf-8','replace'));row.update(title=parser.title,homepage=final,status='reachable',feeds=list(dict.fromkeys(urllib.parse.urljoin(final,x) for x in parser.feeds)),councilLinks=list(dict.fromkeys(urllib.parse.urljoin(final,x) for x in parser.links if any(s in x.lower() for s in ('gemeenteraad','raadsinformatie','notubiz','ibabs','bestuur','besluit'))))[:10])
```

**HTML escaping leaves a javascript URL executable** — `scripts/build_source_gap_audit.py:38`

Escaping protects attribute syntax but does not reject the javascript scheme. The generated current-tab anchor executes the URL in the report's document origin on click.

```python
 def link(u,t):return '<a href="'+esc(u)+'">'+esc(t)+'</a>'
```

**Generated reports share the preview origin** — `server.py:52`

static/source-audit/index.html is served within the same origin as the local editor rather than an isolated evidence viewer.

```python
  if p.startswith('/news-static/'):return self.file(ROOT/'static',p[len('/news-static/'):])
```

**Same-origin script can obtain the shared editor token** — `server.py:39`

admin returns private community details and the token in HTML. Injected same-origin code can fetch this page and then satisfy the Origin/CSRF guard.

```python
 return news.layout('Redactie',community.admin()+content,'/nieuws/redactie').replace('</head>',f'<meta name="csrf" content="{TOKEN}"></head>')
```

**External homepage href enters discovery** — `scripts/discover_sources.py:11`

An upstream municipal page controls href text. No parsed scheme constraint applies when Links stores it for council selection.

```python
  if tag=='a' and d.get('href'):self.links.append(d['href'])
```

**URL is saved before fetching and survives failure** — `scripts/discover_councils.py:10-17`

The attempted fetch rejects unsupported URL schemes but the exception path keeps councilCheckedUrl as a stored discovery candidate.

```python
 target=max(links,key=score);result=dict(row);result['councilCheckedUrl']=target
 try:
  req=urllib.request.Request(target,headers={'User-Agent':'PITO-source-discovery/1.0 (local editorial research)'})
  with urllib.request.urlopen(req,timeout=15) as r:raw=r.read(2_000_000);url=r.url
  parser=Links();parser.feed(raw.decode('utf8','replace'))
  found=list(dict.fromkeys(urllib.parse.urljoin(url,x) for x in parser.links if any(w in x.lower() for w in ['raadsinformatie','bestuurlijkeinformatie','notubiz','ibabs','gemeentebestuur','raadsagenda','raadsvergadering','vergaderingen','raadlive'])))
  result.update(councilStatus='page_verified',councilFinalUrl=url,councilPortals=found[:12],councilCheckedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except Exception as e:result.update(councilStatus='needs_manual_check',councilError=str(e))
```

**Unchecked failed council candidate enters source inventory** — `scripts/municipal_source_inventory.py:18-23`

On fresh/unresolved discovery no councilFinalUrl overrides the failed candidate. add accepts the executable fallback and writes it into municipal source inventory.

```python
  def add(topic,name,url,state,evidence,workflow):
   if not url or (topic,url) in seen:return
   seen.add((topic,url));found.append(dict(topic=topic,name=name,url=url,state=state,evidence=evidence,workflow=workflow))
  ar=reports.get(slug,{})
  for url in ar.get('archiveUrls',[]):add('Gemeentenieuws','Nieuwsarchief '+m['name'],url,ar.get('status','onbekend'),m['homepage'],'Gemeentelijke archiefadapter → privé broncontrole → eigen concept')
  add('Bestuur & besluiten','Gemeenteraad',m.get('councilFinalUrl') or m.get('councilCheckedUrl'),m.get('councilStatus','onbekend'),m['homepage'],'OpenBesluitvorming waar beschikbaar; voorstel en besluit afzonderlijk lezen')
```

#### Reachability

Available through the supported local discovery/report tooling with an unresolved/fresh council record and a later source-link click; no direct public network exposure is required.

- **Attacker:** An attacker controlling an upstream configured municipal homepage or advertised council href

- **Entry point:** discover_sources.Links HTML href collection

- **Outcome:** Read private local community information and mutate local editorial records

Preconditions:
- Operator runs discovery, council checking, inventory generation and report build.
- Editor opens the generated same-origin report and clicks the source link.

Existing controls:
- Loopback and Host allowlist limit direct remote access.
- Same-origin Origin and random CSRF token protect cross-origin writes but do not distinguish injected same-origin JavaScript.

#### Severity

**Low** — The effect can compromise local editorial integrity and private contact data, but exploitation requires an attacker to control a configured upstream municipal homepage, an operator to run the discovery/inventory/report sequence and an editor to click the injected source link. The service is intentionally loopback-only and local changes do not publish to Strapi. These prerequisites reduce likelihood and impact below the independent baseline's medium proposal.

Publicly serving the same reports alongside a real authenticated CMS or automating attacker-selectable source discovery would raise severity; an enforced CSP blocking inline/javascript execution or rejecting non-HTTPS URLs at the sink closes this path.

Impact assessment:
- **Level:** medium
- **Rationale:** Compromises local editorial records and contributor contact information; no automatic internet publication.

Likelihood assessment:
- **Level:** low
- **Rationale:** Requires control of a configured municipal source plus multiple manual local workflow steps and a click.

#### Remediation

Require parsed HTTPS URLs with a hostname and no credentials at discovery, persistence and rendering. Reject executable schemes and render invalid URLs as inert text. Review existing generated inventory/report links, add a complete offline regression through the council discovery-to-report chain, and deny inline script execution on local preview pages.

Tests:
- Feed a council-keyword javascript: href through discovery and assert it is excluded from councilLinks.
- Assert failed council fetch cannot persist an unsafe councilCheckedUrl.
- Assert inventory.add rejects unsafe schemes and report link renders them as plain text.
- Assert regular HTTPS council links survive unchanged and quoted labels remain HTML-escaped.

Preventive controls:
- Use one URL-scheme validator across source-discovery and report-rendering paths.
- Keep third-party source evidence isolated from editorial origin where practical.
- Retain CSP restricting scripts and frame ancestors as defense in depth.

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| Loopback HTTP routing, private file access and editorial writes | Browser-origin isolation / access control / traversal | No issue found | server.py:47-49 and :232-240 reject unexpected Hosts/cross-origin writes; portable_handler.py:11-14 and server.py:204-224 constrain resolved files. The editor has no named accounts by design and is expressly prohibited from public exposure by START-HIER-DEVELOPER.txt:20-31. No supported remote auth bypass or traversal survived static review. |
| Runtime text, query and JSON-LD rendering | HTML/script injection | No issue found | news.py:14,35 escape text/attributes and JSON-LD; newsroom.py:10-20 emits plain text paragraphs; latest_news.py, agenda_views.py, environment_notices.py, community.py and static/\*.js inspected. news.home month/sort fields are allowlisted before interpolation (news.py:91-94), rejecting a tentative reflected-XSS concern. |
| Independent repository baseline | Independent security baseline and coverage reconciliation | No issue found | Baseline fully read 73 runtime/config/tool paths and searched all current authorized source including hidden files for credential/private-key indicators. No embedded credential established; tokens are generated or environmental. It returned one stored-XSS candidate with high confidence / medium severity, and source-backed observations on redirect destination checks, XML encoding-filter bypass, framing and intentional local-only auth. Source-owned generated HTML/SVG, large JSON and all tests/docs were not individually reviewed in full. Candidate preserved and separately validated; this baseline surface itself is now complete, with broad artifact coverage handled separately. |
| Municipal council discovery to source-audit href rendering | Stored XSS / external source authority gain | Reported | Validated one pre-hardening finding; source evidence proves executable href reaches a current-tab report anchor and the local editor origin. Owner severity low, baseline proposal medium. |
| Collector redirect destination boundary | SSRF / public-source to local-network crossing | Needs follow-up | scripts/municipal_archive_intake.py:21 and scripts/intake.py:67 follow HTTPS redirects without destination/IP checks; scripts/discover_councils.py:10-17 also fetches external selected links without a protocol boundary. No concrete internal service or resulting disclosure/action was established. HTTPS TLS validation, byte/time bounds and manual execution limit the confirmed consequence. Retain as hardening observation, not a reported exploit. |
| RSS, SRU, DATEX and media-audit XML parser guards | XML parser denial-of-service control | Needs follow-up | intake.py:11, koop_intake.py:10, ndw_intake.py:20 and audit_media_sources.py search ASCII raw bytes for DTD/entity declarations, which UTF-16 bypasses before ElementTree parse. No external entity I/O established. Modern Expat amplification protections and size bounds prevent an unrestricted Billion Laughs assertion. Parser-hardening observation retained pending concrete resource-impact validation. |
| Server-side content adapter and explicit Strapi import | Credential handling / publication controls | No issue found | app_content.py:13-30 requires published/show_on_web activity flags and validates external URLs; :32-47 uses environment-only endpoint/token, HTTPS or loopback HTTP, bounded response and timeout. scripts/import_strapi.py:7-35 defaults dry-run and requires --apply/token/version/Draft & Publish confirmation; publishedAt null + status draft and existing slug skip constrain mutation. No live CMS configuration/endpoint roles were checked. |
| Current-source embedded credential/private-key review | Secret exposure | No issue found | Independent offline searches included current code, hidden files, configuration, documentation, fixtures, examples and inactive code. No embedded credential or private key was established; strong-pattern matches were public Dutch source slugs verified by metadata, and environment examples contain placeholders. No credential was used or sent to a service. |
| Large datasets, generated assets, tests and handoff documents | Repository coverage limitations | Needs follow-up | 103 unique runtime/config/tool/document paths were fully reviewed; authoritative initial inventory had 2981 files. Large JSON/export content, binary and SVG assets, generated evidence HTML, all tests and all documents were not individually read in full. Searches and architecture mapping do not count as full-file audit coverage. No production app/CMS/hosting source exists in supplied target. |

## Open Questions And Follow Up

- Review retained external source URLs and generated static/source-audit reports for dangerous schemes after rebuilding through the safe URL validator.
  - Follow-up prompt: Review scripts/discover_sources.py, scripts/discover_councils.py, scripts/municipal_source_inventory.py and scripts/build_source_gap_audit.py for HTTPS-only validation on both newly discovered and existing records.
- What real production Laravel/Vue/Strapi app and hosting will serve pitonieuws.nl? The supplied Python server is local-only.
  - Follow-up prompt: Review the actual production account/role, publication-state, private contributor data, deployment HTTPS and CMS read/write token boundaries when that source is available.
- Do all future source-fetch paths enforce public HTTPS destinations for every redirect and every resolved address?
  - Follow-up prompt: Review scripts/municipal_archive_intake.py, scripts/intake.py and scripts/discover_councils.py destination controls, including DNS rebinding/proxy behavior, with offline test fixtures.
- All byte-filter XML parser entrypoints need encoding-independent DTD/entity rejection.
  - Follow-up prompt: Review scripts/intake.py, scripts/koop_intake.py, scripts/ndw_intake.py and scripts/audit_media_sources.py against UTF-8/UTF-16 fixtures and the supported Expat version.
- Concrete redirect/IP guard gap; internal-service impact not established under read-only/no-network audit restrictions.
  - Follow-up prompt: Review deferred unit candidate-source-redirect and close its stated proof gap. Paths: scripts/read_source_documents.py, scripts/municipal_archive_intake.py, scripts/intake.py.
- DTD check encoding bypass established, but concrete resource exhaustion/file disclosure not established and Expat version protections remain material.
  - Follow-up prompt: Review deferred unit candidate-xml-encoding and close its stated proof gap. Paths: scripts/intake.py, scripts/koop_intake.py, scripts/ndw_intake.py.
- Not all generated evidence HTML/SVG, JSON datasets/exports, tests and historical documentation were individually security-reviewed. Fully reviewed source paths retained in scope.artifactsReviewed; this is an honest partial broad-scope scan, not a production certification.
  - Follow-up prompt: Review deferred unit remaining-source-material and close its stated proof gap. Paths: tests, data, exports, work, reports, static/source-audit, static/images, portable-assets.
