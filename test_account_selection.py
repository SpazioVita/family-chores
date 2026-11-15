import sys, tempfile
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'custom_components'/'family_chores'))
from engine import Store
with tempfile.TemporaryDirectory() as temp:
    s=Store(Path(temp)/'test.sqlite')
    assert s.account_owner('ha-1') is None
    uid=s.add_user('Maria','ha-1')
    assert s.account_owner('ha-1')==uid
    s.edit_user(uid,'Maria','ha-1',False)
    assert s.account_owner('ha-1')==uid, 'Suspended account must remain reserved'
    assert s.account_owner('ha-2') is None
    s.close()
print('OK: account association remains unique and suspended accounts remain reserved')
