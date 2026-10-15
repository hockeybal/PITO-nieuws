import copy
import os
import unittest
from unittest.mock import patch

import ranking


class RankingEfficiencyTests(unittest.TestCase):
    def records(self, count=40):
        return [dict(slug=f'story-{i:03}', category='Sport' if i % 3 == 0 else 'Bestuur',
                     municipalities=['woerden'], sourceUrl=f'https://example.test/{i}',
                     sourcePublishedAt='2026-10-10', reviewStatus='preview',
                     ranking=dict(impact=3, audienceNeed='explanation', audienceReason='Uitleg'))
                for i in range(count)]

    def test_relevance_is_evaluated_once_per_story_and_inputs_stay_intact(self):
        items = self.records()
        before = copy.deepcopy(items)
        with patch.dict(os.environ, {'PITO_EDITION_DATE': '2026-10-10'}), \
                patch.object(ranking, 'relevance_tier', wraps=ranking.relevance_tier) as tier:
            ordered = ranking.order(items)
        self.assertEqual(tier.call_count, len(items))
        self.assertEqual(items, before)
        self.assertEqual(len(ordered), len(items))

    def test_category_spread_then_stable_order_and_later_edits(self):
        items = self.records(12)
        with patch.dict(os.environ, {'PITO_EDITION_DATE': '2026-10-10'}):
            ordered = ranking.order(items)
            self.assertEqual([a['slug'] for a in ordered],
                             ['story-011', 'story-009', 'story-010', 'story-006',
                              'story-008', 'story-003', 'story-007', 'story-005',
                              'story-004', 'story-002', 'story-001', 'story-000'])
            items[0]['ranking']['impact'] = 5
            self.assertEqual(ranking.order(items)[0]['slug'], 'story-000')


if __name__ == '__main__':
    unittest.main()
