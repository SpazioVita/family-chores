"""Regression tests for v0.2 visibility and horizon."""
from datetime import date, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'custom_components' / 'family_chores'))
from engine import Store


def test_schedule_visibility():
    with TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / 'chores.db')
        today = date(2026, 11, 15)
        store.add_user('Mario', 'ha_mario')
        store.add_user('Lucia', 'ha_lucia')
        store.add_chore('Cucina', today.isoformat(), 1)
        store.plan(today)
        all_schedule = store.snapshot('ha_mario', True, today)['schedule']
        mario = store.snapshot('ha_mario', False, today)['schedule']
        lucia = store.snapshot('ha_lucia', False, today)['schedule']
        unknown = store.snapshot('ha_unknown', False, today)['schedule']
        assert len(all_schedule) == 14
        assert len(mario) + len(lucia) == 14
        assert len(mario) > 0 and len(lucia) > 0
        assert all(item['mine'] for item in mario + lucia)
        assert unknown == []
        assert all(date.fromisoformat(item['due_date']) <= today + timedelta(days=13) for item in all_schedule)
        # The internal planning horizon is intentionally unchanged.
        assert store.one('SELECT COUNT(*) as total FROM assignments')['total'] == 31
        store.close()

if __name__ == '__main__':
    test_schedule_visibility()
    print('OK: 14-day window, per-user isolation, admin visibility, 30-day planner')
