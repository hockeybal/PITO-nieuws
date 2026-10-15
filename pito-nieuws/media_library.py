"""Reusable, request-local stock selection. Never substitute an unrelated asset."""
import hashlib,json,re,datetime
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).parent

def load():return json.loads((ROOT/'data/images.json').read_text())
def identity(media):
 return media.get('assetId') or media.get('sha256') or media['file']
def eligible(media):
 if not media or not media.get('webApproved',True):return False
 if media.get('kind')=='generated':return False
 if media.get('kind') not in ('photo','commons-photo'):return True
 # Only the capture date qualifies, never a download or verification date.
 date=str(media.get('capturedAt') or media.get('date') or '')
 year=re.search(r'\b(19\d{2}|20\d{2})\b',date)
 if not year or not 2022<=int(year.group(1))<=datetime.date.today().year:return False
 try:return datetime.date.fromisoformat(date[:10])<=datetime.date.today()
 except ValueError:return True

@lru_cache(maxsize=1)
def football_clubs():
 try:
  return [c for c in json.loads((ROOT/'data/sports-sources.json').read_text()) if c.get('sport')=='voetbal']
 except (OSError,ValueError):return []

def club_name_tokens(value):
 # Apostrophes and punctuation vary between feed headlines and club directories.
 return re.sub(r"[^\w]+", " ", value.casefold()).strip()

def club_mentions(text, club):
 text=' '+club_name_tokens(text)+' '
 return any(' '+club_name_tokens(name)+' ' in text
            for name in [club['name']]+club.get('aliases',[]) if name)

def matching_football_clubs(article):
 if article.get('category')!='Sport':return []
 text=' '.join([article.get('title',''),article.get('summary','')])
 places=article.get('municipalities',[])
 return [c for c in football_clubs() if c['municipality'] in places and club_mentions(text,c)]

def article_topics(article):
 topics=set(article.get('imageTopics',[]))
 if matching_football_clubs(article):topics.add('voetbal')
 text=article.get('title','').lower()
 if not topics.difference({'veiligheid','samenleving','verkeer','bestuur','wonen','sport'}):
  text+=' '+article.get('summary','').lower()
 rules={
  'kleding':r'kleding|textiel|kleren',
  'rivierkreeft':r'rivierkreeft',
  'varkens':r'varken',
  'ontbijt':r'ontbijt',
  'panda':r'panda|lang yue',
  'piano':r'piano|vleugel van ramses',
  'theater':r'theater|voorstelling|familievoorstelling',
  'concert':r'concert|koor|klarinet',
  'herfst':r'herfsttocht|herfstwandeling|herfstbladeren',
  'kunst':r'kunstkring|schilder|expositie|atelier|kunst en',
  'ruimtevaart':r'ruimtevaart|astronaut|sterrenwacht',
  'knutselen':r'knutsel|creatieve.*kind|kinderprogramma',
  'voorlezen':r'voorlees|voorlezen',
  'gereedschap':r'gereedschap|boormachine|klus|reparat|repareren',
  'medische-zorg':r'huisarts|ziekenhuis|medisch|gezondheidszorg|\bggd\b|vaccin|\barts\b',
  'sportlust':r'sportlust',
  'woonrecht':r'huurrecht|huurgeschil|huurbescherming|verhuurvergunning|verhuurders|verhuurverbod',
  'cameratoezicht':r'cameratoezicht|bewakingscamera',
  'elektrisch-laden':r'laadpaal|laadpalen|laden met|laadkabel|laadpunt',
  'fruit':r'appels|peren|fruit|boomgaard|plukken',
  'bomen-planten':r'bomen.*uit|bomen.*plant|boomplant',
  'basketbal':r'basketbal',
  'schaken':r'schaak|schaken',
  'koffie':r'koffie|koffieochtend|koffiemiddag',
  'flitser':r'flitser|snelheidscontrole',
  'water':r'wateraanvoer|gemaal|dijk|sloot|droogte',
  'geld':r'mantelzorgwaardering|\bozb\b|begroting|subsidie|woonlast|belasting|tarieven|financi|koopkracht|armoede|minimuminkomen|schuldhulp|meedoenkaart|kidskaart',
  'verkiezingen':r'verkiezing|stembus|stemlokaal|stemhokje',
  'statiegeld':r'statiegeld',
  'zonnepanelen':r'zonnepane|zonne-energie|zonnedak',
  'ferm-werk':r'ferm werk', 'rivm':r'\brivm\b',
  'park':r'nieuweroord|\bpark\b', 'wandelen':r'wandel',
  'universiteitsbibliotheek':r'universiteitsbibliotheek',
  'vrijwilligers':r'vrijwilliger',
  'ov':r'\btrein|\bspoor|\bstation|omreizen', 'bus':r'\bbus\b|\bbussen\b|\bbushalte|\bhalte|u-ov',
  'wegen':r'wegwerk|afsluiting|asfalt|verkeer|rotonde|parkeren',
  'wegwerkzaamheden':r'wegenplan|wegwerkzaam|werkzaamheden.*(?:weg|straat)|(?:weg|straat).*werkzaamheden|onderhoud.*(?:n233|a2|n224)|omleiding',
  'brandweer':r'brandweer|brand\b|brandveilig',
  'politie':r'politie|diefstal|criminaliteit|aanhouding|aangehouden|verdacht|ondermijn',
  'toezicht':r'veiligheid|inspectie|toezicht',
  'noodcommunicatie':r'noodradio|crisisinformatie|radio m utrecht',
  'onderwijs':r'school|onderwijs|kindcentrum|leerling|klaslokaal',
  'sport':r'\bsport\b|bewegen', 'gymzaal':r'gymzaal|sporthal',
  'voetbal':r'voetbal|sportlust|knvb|fc utrecht',
  'volleybal':r'volleybal|vtc woerden|vives',
  'korfbal':r'korfbal|midlandia',
  'honkbal':r'honkbal|nieuwegein diamonds',
  'atletiek':r'atletiek|av pijnenburg|sylvestercross',
  'curling':r'curling',
  'waterpolo':r'waterpolo|duinkikkers',
  'schaatsen':r'(?<!rol)schaats|softijs|shorttrack',
  'rolschaatsen':r'rolschaats|krc rolling',
  'badminton':r'badminton|bc inside',
  'basketbal':r'basketbal|new stars',
  'wielrennen':r'wielren|veldr[it]|nacht van woerden|lucinda brand',
  'schermen':r'schermclub|schermsport|schermlessen|nurvera',
  'petanque':r'pétanque|petanque|jeu de boules|\bpvn\b',
  'hockey':r'\bhockey\b',
  'tennis':r'\btennis\b',
  'tafeltennis':r'tafeltennis|ttv woerden',
  'golf':r'\bgolf\b|golfclub|golfjeugd',
  'schaken':r'schaak|schaken',
  'kickboksen':r'kickboks',
  'pilates':r'pilates',
  'padel':r'\bpadel\b',
  'pickleball':r'pickleball',
  'handbal':r'handbal|bdc-lhv',
  'pencak-silat':r'pencak.?silat',
  'hapkido':r'hapkido',
  'taekwondo':r'taekwondo',
  'autosport':r'autosport|morris schuring',
  'rugby':r'\brugby\b',
  'zwemmen':r'zwem|zwembad', 'buitenfitness':r'calisthenics|buitenfitness|fitnesspark',
  'toilet':r'toilet', 'afval':r'afval|recycl|milieustraat|pmd|apparaten',
  'bibliotheek':r'bibliotheek|boek|lezing|lezen',
  'zorg':r'zorg|dementie|alzheimer|spreekuur|gezondheid|sociaal team',
  'buurthuis':r'cursus|cursussen|training|workshop|buurt|ontmoet|vrijwilliger|inloop|bijeenkomst|meedoen|jobhulp|werkzoekend|festival|cultuur',
  'participatie':r'meedenk|inspraak|bewoner|ideeën',
  'woningbouw':r'woningen|nieuwbouw|woningbouw',
  'ruimtelijk-plan':r'bouwplan|grondovereenkomst|herinricht|omgevingsplan',
  'energie':r'energie|stroomnet|duurzaam', 'bestuur':r'raad|begroting|gemeentehuis|besluit',
 }
 for topic,pattern in rules.items():
  if re.search(pattern,text):topics.add(topic)
 return topics

def candidates(article,library):
 topics=article_topics(article);preferred=article.get('imageKey')
 result=[]
 for key,media in library.items():
  if not eligible(media):continue
  article_slugs=media.get('articleSlugs',[])
  if media.get('usageMode')=='editorial-choice' and preferred!=key and article.get('slug') not in article_slugs:continue
  if article_slugs and article.get('slug') not in article_slugs:continue
  text=(article.get('title','')+' '+article.get('summary','')).casefold()
  if any(t.casefold() in text for t in media.get('excludedTerms',[])):continue
  # Named club assets are exclusive to that club, never other local teams.
  clubs=media.get('clubNames',[])
  if clubs and not any(club_mentions(text,{'name':c}) for c in clubs):continue
  terms=media.get('subjectTerms',[])
  # An explicitly selected photo can be substantiated by the article body too.
  subject_text=text+(' '+article.get('body','').casefold() if preferred==key else '')
  if terms and not any(t.casefold() in subject_text for t in terms):continue
  if article.get('imagePolicy')=='real_only' and media.get('kind')=='generated':continue
  if not (ROOT/'static/images'/media['file']).is_file():continue
  score=10*len(topics.intersection(media.get('topics',[])))
  # Specific subjects in the headline outrank generic themes in the summary.
  if terms and any(t.casefold() in article.get('title','').casefold() for t in terms):score+=30
  if media.get('usageMode')=='editorial-choice' and preferred==key:
   from rights_review import image_review
   if not image_review(media)['readyForPublication']:continue
   score+=100
  if article.get('slug') in article_slugs:
   from rights_review import image_review
   if not image_review(media)['readyForPublication']:continue
   score+=100
  # A requested image or variety must never override subject relevance.
  required=topics.intersection({'voetbal','volleybal','korfbal','honkbal','atletiek','curling','hockey','tennis','tafeltennis','golf','schaken','kickboksen','pilates','padel','pickleball','handbal','pencak-silat','hapkido','taekwondo','autosport','rugby','zwemmen','waterpolo','schaatsen','rolschaatsen','badminton','basketbal','petanque','schermen','wielrennen','buitenfitness','gymzaal'})
  if required and not required.intersection(media.get('topics',[])):continue
  named_place=any(t.casefold() in text for t in media.get('placeTerms',[]))
  if media.get('municipalities') and not named_place and not set(media['municipalities']).intersection(article.get('municipalities',[])):continue
  if score and named_place:score+=30
  elif score and media.get('municipalities'):score+=2
  # Equal subject matches remain available for page-wide image variety.
  # Preferred assets break ties without excluding equally relevant alternatives.
  if score:
   tie=('z' if key==preferred else '')+hashlib.sha256((article.get('slug',article.get('id',''))+'|'+key).encode()).hexdigest()
   result.append((score,tie,key))
 # A relevant licensed photograph wins over generated illustration.
 real=[item for item in result if library[item[2]].get('kind') in ('photo','commons-photo')]
 if real:result=real
 # Do not fill a page with weaker matches merely to avoid repetitions.
 best=max((score for score,_,_ in result),default=0)
 return [key for score,_,key in sorted(result,reverse=True) if score==best]
def assign(articles,library=None):
 """Maximum matching gives every article a relevant image when feasible.
 Image identity collapses aliases/crops. State is per render, not global.
 """
 library=load() if library is None else library
 options=[candidates(a,library) for a in articles];owners={};chosen={}
 def place(i,seen):
  for key in options[i]:
   asset=identity(library[key])
   if asset in seen:continue
   seen.add(asset);other=owners.get(asset)
   if other is None or place(other,seen):
    owners[asset]=i;chosen[i]=key;return True
  return False
 # Constrained stories go first; normal order is deterministic.
 for i in sorted(range(len(articles)),key=lambda n:(len(options[n]),n)):place(i,set())
 return [dict(a,_displayImageKey=chosen.get(i,options[i][0] if options[i] else '')) for i,a in enumerate(articles)]
def media_for(article,library=None):
 library=load() if library is None else library
 if '_displayImageKey' in article:
  media=library.get(article['_displayImageKey'])
  return media if eligible(media) else None
 choices=candidates(article,library)
 return library.get(choices[0]) if choices else None
