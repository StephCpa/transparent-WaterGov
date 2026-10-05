from copy import deepcopy
import unittest
from transparent_eval.association import associate


class AssociationTests(unittest.TestCase):
    def setUp(self):
        self.units = [dict(unit_id=u, reference_id='levee-A', geometry_version='v1',
                           chainage_m=b) for u, b in [('a', [0, 50]), ('b', [50, 100])]]
        self.contexts = [dict(context_id=u+'-c', unit_id=u, model_version='m1',
                             basis_ref='synthetic validity window',
                             valid_from='2026-09-21T08:00:00+08:00',
                             valid_to='2026-09-21T09:00:00+08:00',
                             available_at='2026-09-21T08:00:00+08:00') for u in ['a', 'b']]
        self.event = dict(event_id='e1', reference_id='levee-A', geometry_version='v1',
                          chainage_m=[20, 22], source_ref='synthetic',
                          observed_at='2026-09-21T08:10:00+08:00',
                          received_at='2026-09-21T08:20:00+08:00')
        self.now = '2026-09-21T08:30:00+08:00'

    def run_case(self, event=None, contexts=None):
        return associate([event or self.event], self.units,
                         self.contexts if contexts is None else contexts, self.now)

    def test_unique_and_identical_duplicate(self):
        out = associate([self.event, deepcopy(self.event)], self.units, self.contexts, self.now)
        self.assertEqual(len(out['records']), 1)
        self.assertEqual(out['records'][0]['status'], 'unique_candidate')

    def test_boundary_keeps_one_event_multiple_candidates(self):
        for location in ([50, 50], [49, 51]):
            self.event['chainage_m'] = location
            rec = self.run_case()['records'][0]
            self.assertEqual(rec['status'], 'spatial_ambiguity')
            self.assertEqual(rec['candidate_units'], ['a', 'b'])

    def test_partial_outside_not_unique(self):
        self.event['chainage_m'] = [-2, 2]
        self.assertEqual(self.run_case()['records'][0]['status'], 'spatial_ambiguity')

    def test_late_receipt_and_timezones(self):
        self.event['received_at'] = '2026-09-21T08:40:00+08:00'
        self.assertEqual(self.run_case()['records'], [])
        self.now = '2026-09-21T00:40:00Z'
        self.assertEqual(self.run_case()['records'][0]['status'], 'unique_candidate')

    def test_late_context_not_available(self):
        self.contexts[0]['available_at'] = '2026-09-21T09:00:00+08:00'
        self.assertEqual(self.run_case()['records'][0]['status'], 'no_available_context')

    def test_adjacent_time_windows_half_open(self):
        later = dict(self.contexts[0], context_id='later',
                     valid_from='2026-09-21T09:00:00+08:00',
                     valid_to='2026-09-21T10:00:00+08:00')
        self.event['observed_at'] = self.event['received_at'] = later['valid_from']
        self.now = later['valid_from']
        rec = self.run_case(contexts=self.contexts+[later])['records'][0]
        self.assertEqual([x['context_id'] for x in rec['candidate_links']], ['later'])

    def test_overlapping_contexts_not_silently_selected(self):
        extra = dict(self.contexts[0], context_id='alternative', model_version='m2')
        self.assertEqual(self.run_case(contexts=self.contexts+[extra])['records'][0]['status'],
                         'context_ambiguity')

    def test_wrong_reference_and_outside(self):
        self.event['geometry_version'] = 'v2'
        self.assertEqual(self.run_case()['records'][0]['status'], 'reference_mismatch')
        self.event['geometry_version'] = 'v1'
        self.event['chainage_m'] = [101, 102]
        self.assertEqual(self.run_case()['records'][0]['status'], 'outside_units')

    def test_conflicting_identity_rejected(self):
        with self.assertRaises(ValueError):
            associate([self.event, dict(self.event, chainage_m=[30, 31])],
                      self.units, self.contexts, self.now)

    def test_invalid_context_and_clock(self):
        with self.assertRaises(ValueError):
            self.run_case(contexts=[dict(self.contexts[0], unit_id='unknown')])
        with self.assertRaises(ValueError):
            self.run_case(event=dict(self.event, received_at='2026-09-21T07:00:00+08:00'))


if __name__ == '__main__':
    unittest.main()
