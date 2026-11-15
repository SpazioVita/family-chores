"""Check kiosk read-only payload, no leak of IDs and visibility of today/tomorrow."""
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent/"custom_components/family_chores"))
from engine import Store

class CardsTests(unittest.TestCase):
    def test_board_two_days_and_no_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'chores.sqlite')
            today=date(2026,11,15)
            store.add_user('Mario','ha-mario')
            store.add_user('Lucia','ha-lucia')
            store.add_chore('Cucina',today.isoformat(),1)
            store.plan(today)
            store.expire(today)
            result=store.board_snapshot(today)
            self.assertEqual(result['today'],today.isoformat())
            self.assertEqual(len(result['schedule']),2)
            self.assertEqual({a['due_date'] for a in result['schedule']},{today.isoformat(),(today+timedelta(days=1)).isoformat()})
            self.assertEqual(set(result['schedule'][0]),{'due_date','status','chore','assignee'})
            self.assertNotIn('ha-mario',repr(result))
            self.assertNotIn('ha-lucia',repr(result))
            self.assertIn('Mario',repr(result))
            self.assertIn('Lucia',repr(result))
            store.close()

if __name__=='__main__': unittest.main()
