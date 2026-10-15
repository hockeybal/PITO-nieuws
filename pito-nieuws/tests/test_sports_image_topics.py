import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import media_library
class SportsPhotos(unittest.TestCase):
 def test_different_sport_is_not_illustration(self):
  real=next(m for m in media_library.load().values() if media_library.eligible(m))
  for title,topic in [('TTV Woerden zoekt recreanten','tafeltennis'),('Doornse golfjeugd wint','golf'),('Schaakclub begint competitie','schaken'),('Kickboksen in Baarn','kickboksen'),('Pilatesles in de wijk','pilates'),('PRSH wint bij pencak silat','pencak-silat'),('Willem Enoch behaalt hapkido-examen','hapkido'),('Taekwondo-examen in Seoul','taekwondo'),('Morris Schuring tweede in race','autosport'),('BDC-LHV wint handbalwedstrijd','handbal'),('Pickleballtoernooi in Breukelen','pickleball'),('VTC Woerden wint','volleybal'),('Midlandia J1 wint','korfbal'),('Nieuwegein Diamonds kampioen','honkbal'),('AV Pijnenburg kampioenen','atletiek'),('Curling in Woerden','curling'),('Waterpolosters Duinkikkers winnen','waterpolo'),('Schaatsvereniging Softijs organiseert training','schaatsen'),('PVN speelt pétanque','petanque'),('BC Inside geeft badmintontraining','badminton'),('KRC Rolling wint bij rolschaatsen','rolschaatsen'),('New Stars wint basketbalwedstrijd','basketbal'),('Schermclub Nurvera geeft schermlessen','schermen'),('Orts en Brand op deelnemerslijst Nacht van Woerden','wielrennen')]:
   library={'wrong':dict(real,topics=['sport','voetbal'],municipalities=[],subjectTerms=[],usageMode='',articleSlugs=[]),'correct':dict(real,topics=[topic],municipalities=[],subjectTerms=[],usageMode='',articleSlugs=[])}
   self.assertEqual(media_library.candidates({'title':title,'imageTopics':['sport']},library),['correct'])
if __name__=='__main__':unittest.main()
