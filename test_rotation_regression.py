"""v0.6.1: rotation continuity across user changes, replan and absence."""
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent/'custom_components/family_chores'))
from engine import Store

TODAY=date(2026,11,15)

class RotationRegression(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.db=Store(Path(self.temp.name)/'test.sqlite')
        self.u=[self.db.add_user(n,'ha-'+n) for n in ('Superanzio','Eritreo','Mastino','Palmiro')]
    def tearDown(self):
        self.db.close();self.temp.cleanup()
    def seq(self,cid,count=10):
        return self.db.rows('SELECT due_date,user_id,status,id FROM assignments WHERE chore_id=? ORDER BY due_date LIMIT ?', (cid,count))
    def test_replan_preserves_today_and_rotates_tomorrow(self):
        c=self.db.add_chore('Invadere la Polonia',TODAY.isoformat(),1)
        self.db.plan(TODAY,10)
        before=self.seq(c)
        original_today=before[0].copy()
        self.db.refresh_future(TODAY)
        after=self.seq(c)
        self.assertEqual(after[0],original_today)
        self.assertEqual([a['user_id'] for a in after[:5]],self.u+[self.u[0]])
        self.assertTrue(all(a['user_id']!=b['user_id'] for a,b in zip(after,after[1:])))
        self.db.refresh_future(TODAY)
        self.assertEqual([a['user_id'] for a in self.seq(c)],[a['user_id'] for a in after])
    def test_two_chores_progressive_user_additions(self):
        # Reconstruct the bug: assignments exist before all four users are added.
        for uid in self.u[1:]:
            self.db.db.execute('DELETE FROM users WHERE id=?',(uid,))
        c=self.db.add_chore('Invadere la Polonia',TODAY.isoformat(),1)
        self.db.plan(TODAY,10)
        first=self.seq(c)[0]
        for uid,name in zip(self.u[1:],('Eritreo','Mastino','Palmiro')):
            self.db.add_user(name,'ha-'+name)
            self.db.refresh_future(TODAY)
        second=self.db.add_chore('Riconquistare', (TODAY+timedelta(days=1)).isoformat(),7)
        self.db.refresh_future(TODAY)
        after=self.seq(c)
        self.assertEqual(after[0]['id'],first['id'])
        self.assertNotEqual(after[0]['user_id'],after[1]['user_id'])
        self.assertEqual(len({a['user_id'] for a in after[:4]}),4)
        self.assertEqual(len(self.seq(second)),5)
    def test_suspended_next_user_skipped_without_repeat(self):
        c=self.db.add_chore('Bagno',TODAY.isoformat(),1)
        self.db.plan(TODAY,5)
        self.db.absence(self.u[1],(TODAY+timedelta(days=1)).isoformat(),(TODAY+timedelta(days=2)).isoformat())
        self.db.refresh_future(TODAY)
        after=self.seq(c)
        self.assertEqual(after[0]['user_id'],self.u[0])
        self.assertEqual(after[1]['user_id'],self.u[2])
        self.assertNotEqual(after[1]['user_id'],after[2]['user_id'])
    def test_single_eligible_user_may_repeat(self):
        for uid in self.u[1:]:
            self.db.edit_user(uid,self.db.one('SELECT name FROM users WHERE id=?',(uid,))['name'], 'ha-'+self.db.one('SELECT name FROM users WHERE id=?',(uid,))['name'],False)
        c=self.db.add_chore('Cucina',TODAY.isoformat(),1)
        self.db.plan(TODAY,3)
        self.assertEqual([a['user_id'] for a in self.seq(c)], [self.u[0]]*4)
    def test_today_and_historical_rows_not_deleted(self):
        c=self.db.add_chore('Cucina',(TODAY-timedelta(days=1)).isoformat(),1)
        self.db.plan(TODAY,3)
        old=self.db.db.execute('INSERT INTO assignments(chore_id,user_id,due_date,status,chore_name,user_name) VALUES(?,?,?,?,?,?)',
             (c,self.u[2],(TODAY-timedelta(days=1)).isoformat(),'missed','Cucina','Mastino')).lastrowid
        original=self.db.one('SELECT id FROM assignments WHERE chore_id=? AND due_date=?',(c,TODAY.isoformat()))['id']
        self.db.refresh_future(TODAY)
        self.assertEqual(self.db.one('SELECT status FROM assignments WHERE id=?',(old,))['status'],'missed')
        self.assertEqual(self.db.one('SELECT id FROM assignments WHERE chore_id=? AND due_date=?',(c,TODAY.isoformat()))['id'],original)

if __name__=='__main__': unittest.main()
