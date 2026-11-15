"""Pure Python SQLite engine for Family Chores. All dates are HA local dates."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

class ChoreError(ValueError):
    pass

class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, ha_user_id TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1, ordinal INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS absences (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), start_date TEXT NOT NULL, end_date TEXT NOT NULL, CHECK(end_date >= start_date));
        CREATE TABLE IF NOT EXISTS chores (id INTEGER PRIMARY KEY, name TEXT NOT NULL, start_date TEXT NOT NULL, frequency INTEGER NOT NULL CHECK(frequency >= 1), active INTEGER NOT NULL DEFAULT 1, cursor INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS assignments (id INTEGER PRIMARY KEY, chore_id INTEGER REFERENCES chores(id) ON DELETE SET NULL, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled', completed_at TEXT, completed_by TEXT, chore_name TEXT, user_name TEXT, original_chore_id INTEGER, original_user_id INTEGER, original_ha_user_id TEXT, UNIQUE(chore_id,due_date));
        CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, assignment_id INTEGER NOT NULL UNIQUE REFERENCES assignments(id), acknowledged_at TEXT, acknowledged_by TEXT);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, assignment_id INTEGER REFERENCES assignments(id) ON DELETE SET NULL, event_type TEXT NOT NULL, actor_id TEXT, detail TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS ix_assignments_due ON assignments(due_date,status);
        ''')
        self._migrate_assignments()

    def _migrate_assignments(self):
        """Preserve existing occurrences when a person or chore is physically deleted.

        v0.3 referenced both tables with RESTRICT and lacked historical names.
        Migration is transactional; a rollback preserves the original table.
        """
        cols = {r['name']: r for r in self.rows('PRAGMA table_info(assignments)')}
        if 'chore_name' not in cols or cols['chore_id']['notnull']:
            self.db.execute('PRAGMA foreign_keys=OFF')
            try:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute("""CREATE TABLE assignments_new (
                    id INTEGER PRIMARY KEY,
                    chore_id INTEGER REFERENCES chores(id) ON DELETE SET NULL,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled',
                    completed_at TEXT, completed_by TEXT, chore_name TEXT, user_name TEXT,
                    original_chore_id INTEGER, original_user_id INTEGER, original_ha_user_id TEXT,
                    UNIQUE(chore_id,due_date))""")
                self.db.execute("""INSERT INTO assignments_new
                    (id,chore_id,user_id,due_date,status,completed_at,completed_by,
                     chore_name,user_name,original_chore_id,original_user_id,original_ha_user_id)
                    SELECT a.id,a.chore_id,a.user_id,a.due_date,a.status,a.completed_at,a.completed_by,
                           c.name,u.name,a.chore_id,a.user_id,u.ha_user_id
                    FROM assignments a LEFT JOIN chores c ON c.id=a.chore_id
                    LEFT JOIN users u ON u.id=a.user_id""")
                self.db.execute('DROP TABLE assignments')
                self.db.execute('ALTER TABLE assignments_new RENAME TO assignments')
                self.db.execute('CREATE INDEX ix_assignments_due ON assignments(due_date,status)')
                if self.rows('PRAGMA foreign_key_check'):
                    raise RuntimeError('Database migration: inconsistent foreign keys')
                self.db.execute('COMMIT')
            except Exception:
                if self.db.in_transaction: self.db.execute('ROLLBACK')
                raise
            finally:
                self.db.execute('PRAGMA foreign_keys=ON')
        else:
            # Rebuild not needed for new databases; old partial snapshots stay readable.
            pass

    def close(self): self.db.close()
    def rows(self, sql, args=()): return [dict(x) for x in self.db.execute(sql,args).fetchall()]
    def one(self, sql, args=()):
        x=self.db.execute(sql,args).fetchone()
        return dict(x) if x else None
    def _event(self, aid, kind, actor=None, detail=None):
        self.db.execute('INSERT INTO events(assignment_id,event_type,actor_id,detail) VALUES(?,?,?,?)',(aid,kind,actor,detail))

    def account_owner(self, ha_user_id):
        # None when not associated; includes suspended users.
        row = self.one('SELECT id FROM users WHERE ha_user_id=?', (ha_user_id,))
        return row['id'] if row else None

    def add_user(self,name,ha_user_id):
        if not name.strip() or not ha_user_id: raise ChoreError('Nome e account HA obbligatori')
        with self.db:
            ordinal=self.db.execute('SELECT COALESCE(MAX(ordinal),-1)+1 FROM users').fetchone()[0]
            cur=self.db.execute('INSERT INTO users(name,ha_user_id,ordinal) VALUES(?,?,?)',(name.strip(),ha_user_id,ordinal))
            return cur.lastrowid

    def edit_user(self,uid,name,ha_user_id,active):
        if not name.strip() or not ha_user_id: raise ChoreError('Nome e account HA obbligatori')
        with self.db:
            if not self.db.execute('UPDATE users SET name=?,ha_user_id=?,active=? WHERE id=?',(name.strip(),ha_user_id,int(active),uid)).rowcount: raise ChoreError('Utente non trovato')

    def absence(self,uid,start,end):
        if date.fromisoformat(end)<date.fromisoformat(start): raise ChoreError('Intervallo non valido')
        with self.db:
            self.db.execute('INSERT INTO absences(user_id,start_date,end_date) VALUES(?,?,?)',(uid,start,end))

    def add_chore(self,name,start,frequency):
        date.fromisoformat(start)
        if not name.strip() or frequency<1: raise ChoreError('Faccenda o frequenza non valida')
        with self.db:
            cur=self.db.execute('INSERT INTO chores(name,start_date,frequency) VALUES(?,?,?)',(name.strip(),start,frequency))
            return cur.lastrowid

    def edit_chore(self,cid,name,active):
        if not name.strip(): raise ChoreError('Nome obbligatorio')
        with self.db:
            if not self.db.execute('UPDATE chores SET name=?,active=? WHERE id=?',(name.strip(),int(active),cid)).rowcount: raise ChoreError('Faccenda non trovata')

    def deletion_impact(self, kind, obj_id, today):
        column = 'user_id' if kind == 'user' else 'chore_id'
        return self.one(f"""SELECT
            SUM(CASE WHEN due_date > ? AND status='scheduled' THEN 1 ELSE 0 END) AS future,
            SUM(CASE WHEN due_date = ? AND status IN ('pending','scheduled') THEN 1 ELSE 0 END) AS today,
            SUM(CASE WHEN status IN ('completed','missed','cancelled') THEN 1 ELSE 0 END) AS retained
            FROM assignments WHERE {column}=?""", (today.isoformat(),today.isoformat(),obj_id))

    def delete_user(self, uid, confirmation, today):
        with self.db:
            u=self.one('SELECT * FROM users WHERE id=?',(uid,))
            if not u: raise ChoreError('Utente non trovato')
            if confirmation != u['name']: raise ChoreError('Il nome di conferma non corrisponde')
            self._retire_assignments('user_id',uid,today,'user_deleted')
            self.db.execute('DELETE FROM absences WHERE user_id=?',(uid,))
            self.db.execute('DELETE FROM users WHERE id=?',(uid,))
        self.refresh_future(today)

    def delete_chore(self, cid, confirmation, today):
        with self.db:
            c=self.one('SELECT * FROM chores WHERE id=?',(cid,))
            if not c: raise ChoreError('Faccenda non trovata')
            if confirmation != c['name']: raise ChoreError('Il nome di conferma non corrisponde')
            self._retire_assignments('chore_id',cid,today,'chore_deleted')
            self.db.execute('DELETE FROM chores WHERE id=?',(cid,))
        self.refresh_future(today)

    def _retire_assignments(self, column, obj_id, today, reason):
        # Called only within a transaction; column is a trusted internal constant.
        records=self.rows(f'SELECT * FROM assignments WHERE {column}=? ORDER BY due_date,id',(obj_id,))
        for a in records:
            if a['due_date'] > today.isoformat() and a['status']=='scheduled':
                self._event(a['id'],'cancelled_future',detail=reason)
                # Existing events retain the audit with assignment_id NULL by ON DELETE SET NULL.
                self.db.execute('DELETE FROM assignments WHERE id=?',(a['id'],))
            elif a['due_date'] == today.isoformat() and a['status'] in ('pending','scheduled'):
                self.db.execute("UPDATE assignments SET status='cancelled' WHERE id=?",(a['id'],))
                self._event(a['id'],'cancelled',detail=reason)
        # Completed/missed/cancelled occurrences are retained with their snapshots.

    def eligible(self,day):
        return self.rows('''SELECT u.* FROM users u WHERE active=1 AND NOT EXISTS
        (SELECT 1 FROM absences a WHERE a.user_id=u.id AND ? BETWEEN a.start_date AND a.end_date)
        ORDER BY ordinal,id''',(day,))

    def plan(self,today,horizon=30):
        """Plan occurrences while preserving rotation across replanning.

        The stable ordering uses every known user's ordinal (including suspended
        users) so a changing eligibility list cannot reset the rotation.
        Existing assignments, including today's, are never rewritten here.
        """
        finish=today+timedelta(days=horizon)
        with self.db:
            roster=self.rows('SELECT id,ordinal FROM users ORDER BY ordinal,id')
            positions={u['id']:i for i,u in enumerate(roster)}
            for c in self.rows('SELECT * FROM chores WHERE active=1 ORDER BY id'):
                start=date.fromisoformat(c['start_date'])
                d=max(today,start)
                delta=(d-start).days
                if delta % c['frequency']:
                    d+=timedelta(days=c['frequency']-delta%c['frequency'])
                cursor=c['cursor']
                # Seed from the last retained occurrence before the planning window.
                previous=self.one('''SELECT user_id FROM assignments
                    WHERE chore_id=? AND due_date<?
                    ORDER BY due_date DESC,id DESC LIMIT 1''',
                    (c['id'],d.isoformat()))
                last_user=previous['user_id'] if previous else None
                while d<=finish:
                    stamp=d.isoformat()
                    existing=self.one('''SELECT id,user_id FROM assignments
                        WHERE chore_id=? AND due_date=?''',(c['id'],stamp))
                    if existing:
                        # E.g. today's retained assignment after refresh_future().
                        if existing['user_id'] is not None:
                            last_user=existing['user_id']
                    else:
                        users=self.eligible(stamp)
                        selected=None
                        if users:
                            if last_user in positions:
                                last_position=positions[last_user]
                                ordered=sorted(users,key=lambda u:
                                    (positions[u['id']]-last_position-1)%len(roster))
                            else:
                                # New chore / an assignee who has since been deleted.
                                ordered=users[cursor%len(users):]+users[:cursor%len(users)]
                            occupied={x['user_id'] for x in self.rows('''
                                SELECT user_id FROM assignments
                                WHERE due_date=? AND user_id IS NOT NULL
                                  AND status NOT IN ('cancelled','missed')''',(stamp,))}
                            # Avoid a consecutive repeat first, and avoid same-day
                            # collisions where possible; a sole eligible user may repeat.
                            selected=(next((u for u in ordered if u['id']!=last_user
                                            and u['id'] not in occupied),None)
                                      or next((u for u in ordered if u['id']!=last_user),None)
                                      or next((u for u in ordered if u['id'] not in occupied),None)
                                      or ordered[0])
                            cursor=(users.index(selected)+1)%len(users)
                            last_user=selected['id']
                        new=self.db.execute('''INSERT INTO assignments(chore_id,user_id,due_date,status,chore_name,user_name,original_chore_id,original_user_id,original_ha_user_id) VALUES(?,?,?,?,?,?,?,?,?)''',(c['id'],selected['id'] if selected else None,stamp,'pending' if d==today else 'scheduled',c['name'],selected['name'] if selected else None,c['id'],selected['id'] if selected else None,selected['ha_user_id'] if selected else None))
                        self._event(new.lastrowid,'assigned',detail='uncovered' if not selected else None)
                    d+=timedelta(days=c['frequency'])
                self.db.execute('UPDATE chores SET cursor=? WHERE id=?',(cursor,c['id']))

    def expire(self,today):
        """At or after midnight close all earlier uncompleted occurrences exactly once."""
        with self.db:
            ids=self.rows("SELECT id FROM assignments WHERE due_date < ? AND status IN ('scheduled','pending')",(today.isoformat(),))
            for item in ids:
                aid=item['id']
                self.db.execute("UPDATE assignments SET status='missed' WHERE id=?",(aid,))
                self.db.execute('INSERT OR IGNORE INTO alerts(assignment_id) VALUES(?)',(aid,))
                self._event(aid,'missed')
            self.db.execute("UPDATE assignments SET status='pending' WHERE due_date=? AND status='scheduled'",(today.isoformat(),))

    def complete(self,aid,ha_user_id,today,admin=False):
        with self.db:
            a=self.one('SELECT * FROM assignments WHERE id=?',(aid,))
            if not a: raise ChoreError('Assegnazione inesistente')
            if a['due_date']!=today.isoformat(): raise ChoreError('Si può completare soltanto nel giorno previsto')
            if a['status'] not in ('scheduled','pending'): raise ChoreError('Faccenda già chiusa')
            if not admin:
                u=self.one('SELECT * FROM users WHERE ha_user_id=?',(ha_user_id,))
                if not u or u['id']!=a['user_id']: raise ChoreError('Non sei assegnatario della faccenda')
            self.db.execute("UPDATE assignments SET status='completed', completed_at=CURRENT_TIMESTAMP, completed_by=? WHERE id=?",(ha_user_id,aid))
            self._event(aid,'completed',ha_user_id)

    def acknowledge(self,alert_id,ha_user_id):
        with self.db:
            if not self.db.execute('UPDATE alerts SET acknowledged_at=CURRENT_TIMESTAMP, acknowledged_by=? WHERE id=? AND acknowledged_at IS NULL',(ha_user_id,alert_id)).rowcount: raise ChoreError('Anomalia non trovata o già visionata')

    def refresh_future(self,today):
        """Recalculate only future assignments, recording each removal in history.
        Today and the past are immutable; completed records are never deleted.
        """
        with self.db:
            future=self.rows("SELECT * FROM assignments WHERE due_date>? AND status='scheduled'",(today.isoformat(),))
            for a in future:
                self._event(a['id'],'replanned',detail=f"assignment={a['id']};chore={a['chore_id']};previous_user={a['user_id']};date={a['due_date']}")
            self.db.execute("DELETE FROM alerts WHERE assignment_id IN (SELECT id FROM assignments WHERE due_date>? AND status='scheduled')",(today.isoformat(),))
            self.db.execute("DELETE FROM assignments WHERE due_date>? AND status='scheduled'",(today.isoformat(),))
            # Preserve the cursor; plan() derives continuity from retained assignments.
        self.plan(today)

    def board_snapshot(self, today):
        # Read-only summary available to authenticated HA accounts, including kiosk.
        return {
            'today': today.isoformat(),
            'schedule': self.rows("""SELECT a.due_date,a.status,
                COALESCE(a.chore_name,c.name) AS chore,
                COALESCE(a.user_name,u.name) AS assignee
                FROM assignments a LEFT JOIN chores c ON c.id=a.chore_id
                LEFT JOIN users u ON u.id=a.user_id
                WHERE a.due_date BETWEEN ? AND ? AND a.status != 'cancelled'
                ORDER BY a.due_date,chore,assignee""",
                (today.isoformat(),(today + timedelta(days=1)).isoformat()))
        }

    def snapshot(self,user_id,admin,today):
        # Show only 14 calendar days (today + next 13 days). Keep internal planning at 30 days.
        # Non-admin accounts receive only assignments tied to their authenticated HA user ID.
        base='''SELECT a.id,a.due_date,a.status,COALESCE(a.chore_name,c.name) AS chore,COALESCE(a.user_name,u.name) AS assignee,u.ha_user_id AS owner
                FROM assignments a LEFT JOIN chores c ON c.id=a.chore_id LEFT JOIN users u ON u.id=a.user_id'''
        filters=" WHERE a.due_date>=? AND a.due_date<=? AND a.status!='cancelled'"
        args=[today.isoformat(),(today+timedelta(days=13)).isoformat()]
        if not admin:
            filters+=' AND u.ha_user_id=?'
            args.append(user_id)
        scheduled=self.rows(base+filters+' ORDER BY a.due_date,c.name',tuple(args))
        for a in scheduled:
            a['mine']=(a.pop('owner')==user_id)
        result={'today':today.isoformat(),'schedule':scheduled,'admin':admin}
        if admin:
            result['users']=self.rows('SELECT * FROM users ORDER BY ordinal,id')
            for u in result['users']:
                u['deletion_impact']=self.deletion_impact('user',u['id'],today)
            result['chores']=self.rows('SELECT * FROM chores ORDER BY id')
            for c in result['chores']:
                c['deletion_impact']=self.deletion_impact('chore',c['id'],today)
            result['absences']=self.rows('SELECT a.*,u.name AS user_name FROM absences a JOIN users u ON u.id=a.user_id ORDER BY a.start_date DESC')
            result['alerts']=self.rows('''SELECT al.id,al.acknowledged_at,a.due_date,COALESCE(a.chore_name,c.name) AS chore,COALESCE(a.user_name,u.name) AS assignee
                FROM alerts al JOIN assignments a ON a.id=al.assignment_id LEFT JOIN chores c ON c.id=a.chore_id
                LEFT JOIN users u ON u.id=a.user_id WHERE al.acknowledged_at IS NULL ORDER BY a.due_date DESC''')
            result['history']=self.rows('''SELECT a.id,a.due_date,a.status,a.completed_at,COALESCE(a.chore_name,c.name) AS chore,COALESCE(a.user_name,u.name) AS assignee
                FROM assignments a LEFT JOIN chores c ON c.id=a.chore_id LEFT JOIN users u ON u.id=a.user_id
                WHERE a.status IN ('completed','missed','cancelled') ORDER BY a.due_date DESC,a.id DESC LIMIT 300''')
        return result
