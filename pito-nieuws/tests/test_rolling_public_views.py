"""Rolling editions keep historical archives reachable across calendar years."""
import datetime
import os
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import archive_navigation
import environment_notices
import latest_news
import news


class RollingPublicViews(unittest.TestCase):
 def test_archival_date_has_no_fixed_2026_boundary_and_respects_test_edition(self):
  with patch.dict(os.environ,{'PITO_EDITION_DATE':'2028-01-15'}):
   self.assertTrue(archive_navigation.in_archive({'sourcePublishedAt':'2025-04-01'}))
   self.assertTrue(archive_navigation.in_archive({'sourcePublishedAt':'2028-01-15T14:00:00+01:00'}))
   self.assertFalse(archive_navigation.in_archive({'sourcePublishedAt':'2028-01-16'}))
   self.assertFalse(archive_navigation.in_archive({'sourcePublishedAt':None}))

 def test_latest_news_keeps_old_archive_month_accessible_after_new_year(self):
  def row(slug,date):
   return dict(slug=slug,title=slug,summary='Samenvatting',category='Samenleving',municipalities=['woerden'],sourcePublishedAt=date)
  items=[row('Bewaar oud archief','2025-04-01'),row('Actueel bericht','2028-01-15'),row('Toekomstig bericht','2028-01-16')]
  with ExitStack() as stack:
   stack.enter_context(patch.dict(os.environ,{'PITO_EDITION_DATE':'2028-01-15'}))
   stack.enter_context(patch.object(news,'articles',return_value=items))
   stack.enter_context(patch.object(news,'artwork',return_value=''))
   stack.enter_context(patch.object(news,'layout',side_effect=lambda title,body,*args:body))
   stack.enter_context(patch.object(news.ranking,'order',side_effect=lambda items,*args:items))
   stack.enter_context(patch.object(latest_news.media_library,'assign',side_effect=lambda items,*args:items))
   stack.enter_context(patch.object(latest_news.starter,'render',return_value=''))
   stack.enter_context(patch.object(latest_news.community,'tabs',return_value=''))
   html=latest_news.render('woerden')
   self.assertIn('Bewaar oud archief',html)
   self.assertIn('Actueel bericht',html)
   self.assertNotIn('Toekomstig bericht',html)
   old_month=latest_news.render('woerden',month='2025-04')
   self.assertIn('Bewaar oud archief',old_month)
   self.assertNotIn('Actueel bericht',old_month)

 def test_environment_default_window_rolls_but_old_month_and_details_survive(self):
  def row(identifier,date,title):
   return dict(id=identifier,municipality='woerden',authority='Woerden',sourcePublishedAt=date,
               sourceTitle='Ontvangen aanvraag omgevingsvergunning '+title,
               sourceUrl='https://zoek.officielebekendmakingen.nl/gmb-2028-'+identifier+'.html')
  today=datetime.date(2028,1,15)
  cutoff=(today-datetime.timedelta(days=90)).isoformat()
  notices=[row('1','2028-01-15','Vandaag'),row('2',cutoff,'Grens van venster'),
           row('3','2025-03-12','Oud archief'),row('4','2028-01-16','Toekomst')]
  original_read=news.read
  def read(name):
   if name=='koop-inbox':return notices
   return original_read(name)
  with ExitStack() as stack:
   stack.enter_context(patch.dict(os.environ,{'PITO_EDITION_DATE':'2028-01-15'}))
   stack.enter_context(patch.object(news,'read',side_effect=read))
   stack.enter_context(patch.object(news,'layout',side_effect=lambda title,body,*args:body))
   stack.enter_context(patch.object(environment_notices.official_content,'read',return_value=None))
   stack.enter_context(patch.object(environment_notices.starter,'compact',return_value=''))
   stack.enter_context(patch.object(environment_notices.community,'tabs',return_value=''))
   self.assertEqual({r['id'] for r in environment_notices.records()},{'1','2','3'})
   current=environment_notices.page('woerden')
   self.assertIn('Vandaag',current)
   self.assertIn('Grens van venster',current)
   self.assertNotIn('Oud archief',current)
   self.assertNotIn('Toekomst',current)
   old=environment_notices.page('woerden',month='2025-03')
   self.assertIn('Oud archief',old)
   self.assertNotIn('Grens van venster',old)
   self.assertIn('Maart 2025',old)
   self.assertIn('Januari 2028',old)
   home=environment_notices.block('woerden')
   self.assertNotIn('Oud archief',home)


if __name__=='__main__':unittest.main()
