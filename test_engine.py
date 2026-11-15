from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location("chores_engine",Path(__file__).parent/"custom_components/family_chores/engine.py")
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
Store,ChoreError=engine.Store,engine.ChoreError

def run():
    with TemporaryDirectory() as p:
        s=Store(Path(p)/'test.sqlite')
        s.add_user('Mario','ha-mario');s.add_user('Lucia','ha-lucia')
        c=s.add_chore('Cucina','2026-11-15',1)
        s.plan(date(2026,11,15),4)
        before=s.rows('SELECT * FROM assignments')
        assert len(before)==5
        assert len({a['user_id'] for a in before[:2]})==2
        s.plan(date(2026,11,15),4)
        assert len(s.rows('SELECT * FROM assignments'))==5
        aid=before[0]['id']
        try:s.complete(aid,'ha-lucia',date(2026,11,15))
        except ChoreError:pass
        else:raise AssertionError('Non assegnatario ammesso!')
        s.complete(aid,'ha-mario',date(2026,11,15))
        s.expire(date(2026,11,17))
        assert s.one('SELECT status FROM assignments WHERE id=?',(aid,))['status']=='completed'
        assert s.one('SELECT status FROM assignments WHERE due_date=?',('2026-11-16',))['status']=='missed'
        assert len(s.rows('SELECT * FROM alerts'))==1
        s.expire(date(2026,11,17))
        assert len(s.rows('SELECT * FROM alerts'))==1
        try:s.complete(aid,'ha-mario',date(2026,11,17))
        except ChoreError:pass
        else:raise AssertionError('Conferma fuori scadenza!')
        s.close()
    print('TEST SUPERATI: rotazione, idempotenza, permessi, scadenze e alert')
if __name__=='__main__':run()
