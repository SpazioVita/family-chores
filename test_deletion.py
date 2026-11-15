"""Regression tests: v0.3 migration and historical retention."""
import sys,sqlite3,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'custom_components/family_chores'))
from engine import Store,ChoreError

class DeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'db.sqlite'
        self.db=Store(self.path)
        self.today=date(2026,11,15)
        self.u=self.db.add_user('Mario','ha-mario')
        self.v=self.db.add_user('Lucia','ha-lucia')
        self.c=self.db.add_chore('Cucina','2026-11-14',1)
        self.db.plan(self.today,4)
    def tearDown(self):
        self.db.close();self.temp.cleanup()
    def test_delete_user_preserves_history(self):
        self.db.expire(self.today)
        # One previous missed occurrence from 14th must be set up before planning.
        self.db.db.execute("INSERT INTO assignments (chore_id,user_id,due_date,status,chore_name,user_name,original_chore_id,original_user_id) VALUES (?,?,?,?,?,?,?,?)",(self.c,self.u,'2026-11-14','missed','Cucina','Mario',self.c,self.u))
        self.db.db.execute('INSERT INTO alerts(assignment_id) VALUES(last_insert_rowid())')
        old=self.db.one("SELECT id FROM assignments WHERE due_date='2026-11-14'")['id']
        self.db.delete_user(self.u,'Mario',self.today)
        self.assertIsNone(self.db.one('SELECT * FROM users WHERE id=?',(self.u,)))
        historic=self.db.one('SELECT * FROM assignments WHERE id=?',(old,))
        self.assertEqual(historic['status'],'missed')
        self.assertEqual(historic['user_name'],'Mario')
        self.assertIsNone(historic['user_id'])
        self.assertEqual(self.db.snapshot('admin',True,self.today)['history'][0]['assignee'],'Mario')
        self.assertEqual(len(self.db.snapshot('admin',True,self.today)['alerts']),1)
        self.db.add_user('Mario','ha-mario')
        self.assertEqual(self.db.one('SELECT user_name FROM assignments WHERE id=?',(old,))['user_name'],'Mario')
        self.assertEqual(self.db.rows('PRAGMA foreign_key_check'),[])
    def test_delete_chore_keeps_completed_and_alerts(self):
        self.db.db.execute("INSERT INTO assignments(chore_id,user_id,due_date,status,chore_name,user_name,original_chore_id,original_user_id) VALUES(?,?,?,?,?,?,?,?)",(self.c,self.u,'2026-11-12','missed','Cucina','Mario',self.c,self.u))
        old=self.db.one("SELECT id FROM assignments WHERE due_date='2026-11-12'")['id']
        self.db.db.execute('INSERT INTO alerts(assignment_id) VALUES(?)',(old,))
        self.db.delete_chore(self.c,'Cucina',self.today)
        self.assertIsNone(self.db.one('SELECT * FROM chores WHERE id=?',(self.c,)))
        historic=self.db.one('SELECT * FROM assignments WHERE id=?',(old,))
        self.assertIsNone(historic['chore_id'])
        self.assertEqual(historic['chore_name'],'Cucina')
        self.assertEqual(self.db.snapshot('admin',True,self.today)['history'][0]['chore'],'Cucina')
        self.assertEqual(self.db.snapshot('admin',True,self.today)['alerts'][0]['chore'],'Cucina')
        self.assertEqual(self.db.rows('PRAGMA foreign_key_check'),[])
    def test_wrong_confirmation(self):
        with self.assertRaises(ChoreError):self.db.delete_user(self.u,'Wrong',self.today)
        self.assertIsNotNone(self.db.one('SELECT id FROM users WHERE id=?',(self.u,)))
    def test_today_cancelled(self):
        a=self.db.one("SELECT id FROM assignments WHERE due_date=? AND user_id=?",(self.today.isoformat(),self.u))
        self.assertIsNotNone(a)
        self.db.delete_user(self.u,'Mario',self.today)
        self.assertEqual(self.db.one('SELECT status FROM assignments WHERE id=?',(a['id'],))['status'],'cancelled')
        self.assertNotIn(a['id'],[x['id'] for x in self.db.snapshot('admin',True,self.today)['schedule']])
    def test_migrate_v03(self):
        # Build a clean database with the actual v0.3 engine, then open in v0.4.
        self.db.close()
        self.path.unlink()
        import importlib.util
        old_engine=Path(__file__).resolve().parent.parent/'family_chores_v0_3/custom_components/family_chores/engine.py'
        spec=importlib.util.spec_from_file_location('old_family_engine',old_engine)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        old=module.Store(self.path)
        uid=old.add_user('Mario','ha-mario')
        cid=old.add_chore('Cucina','2026-11-12',1)
        old.plan(date(2026,11,12),2)
        old.expire(self.today)
        old.close()
        self.db=Store(self.path)
        historic=self.db.one("SELECT * FROM assignments WHERE due_date='2026-11-12'")
        self.assertEqual(historic['user_name'],'Mario')
        self.assertEqual(historic['chore_name'],'Cucina')
        self.db.delete_chore(cid,'Cucina',self.today)
        self.assertEqual(self.db.snapshot('admin',True,self.today)['history'][0]['chore'],'Cucina')
        self.assertEqual(self.db.rows('PRAGMA foreign_key_check'),[])

if __name__=='__main__':unittest.main()
