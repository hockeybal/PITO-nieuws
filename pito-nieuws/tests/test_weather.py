import unittest,datetime as dt,json,tempfile
from pathlib import Path
from unittest.mock import patch
import weather
class WeatherTests(unittest.TestCase):
 def test_station_and_temperature_column(self):
  s='<h2>Waarnemingen 14 oktober 2026 10:00 uur</h2><table><tr><th>Station</th><th>Weer</th><th>Temp (°C)</th></tr><tr><td>Cabauw</td><td></td><td>13</td></tr><tr><td>De Bilt</td><td>bewolkt</td><td>-1,2</td></tr></table>'
  d=weather.parse(s);self.assertEqual(d['temperature'],-1.2);self.assertEqual(d['measuredAt'],'2026-10-14T10:00:00+02:00')
 def test_missing_temperature_rejected(self):
  with self.assertRaises(ValueError):weather.parse('<h2>Waarnemingen 14 oktober 2026 10:00 uur</h2>')
 def test_old_and_future_observations_hidden(self):
  now=dt.datetime(2026,10,14,10,tzinfo=dt.timezone.utc)
  with tempfile.TemporaryDirectory() as folder,patch.object(weather,'CACHE',Path(folder)/'weather.json'):
   for age,status in [(600,'fresh'),(2400,'stale'),(7500,'unavailable'),(-600,'unavailable')]:
    weather.CACHE.write_text(json.dumps({'measuredAt':(now-dt.timedelta(seconds=age)).isoformat(),'temperature':12}))
    self.assertEqual(weather.get(False,now)['status'],status)
