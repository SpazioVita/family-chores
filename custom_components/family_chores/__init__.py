"""Family Chores integration: authenticated websocket CRUD and scheduling."""
import logging
import sqlite3
from datetime import datetime, time, timedelta
from functools import partial
from pathlib import Path
from homeassistant.components import panel_custom
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
import voluptuous as vol
from .engine import Store, ChoreError

DOMAIN='family_chores'
_LOGGER=logging.getLogger(__name__)

async def async_setup(hass, config):
    """Allow discovery and setup through the Home Assistant UI."""
    return True

async def async_setup_entry(hass, entry):
    """Create a new empty database and set up the UI and WebSocket API."""
    if DOMAIN in hass.data:
        return True
    frontend = Path(__file__).parent / 'frontend'
    await hass.http.async_register_static_paths([
        StaticPathConfig('/family_chores_assets', str(frontend), False)
    ])
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name='family-chores-panel',
        frontend_url_path='family-chores',
        sidebar_title='Faccende',
        sidebar_icon='mdi:broom',
        module_url='/family_chores_assets/family-chores-panel.js?v=6',
        require_admin=False,
    )
    # Automatically load the two custom Lovelace cards on every dashboard.
    add_extra_js_url(hass, '/family_chores_assets/family-chores-cards.js?v=6')

    store=await hass.async_add_executor_job(Store,hass.config.path('.storage/family_chores.sqlite'))
    hass.data[DOMAIN]=store

    async def maintenance(now=None):
        today=dt_util.now().date()
        await hass.async_add_executor_job(store.expire,today)
        await hass.async_add_executor_job(store.plan,today)

    await maintenance()

    def notify_changed():
        hass.bus.async_fire(f"{DOMAIN}_updated")
    async def midnight(now):
        await maintenance(now)
        notify_changed()
    unsub=async_track_time_change(hass,midnight,hour=0,minute=0,second=0)
    hass.data[f'{DOMAIN}_unsub']=unsub

    def seconds_to_midnight():
        now=dt_util.now()
        next_day=now.date()+timedelta(days=1)
        next_midnight=datetime.combine(next_day,time.min,tzinfo=now.tzinfo)
        return max(0.1,(next_midnight-now).total_seconds())

    @websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/snapshot'})
    @websocket_api.async_response
    async def snapshot(hass,connection,msg):
        try:
            result=await hass.async_add_executor_job(store.snapshot,connection.user.id,connection.user.is_admin,dt_util.now().date())
            if connection.user.is_admin:
                # Return only free, real, active Home Assistant accounts. Existing
                # associations remain visible separately in result['users'].
                assigned={u['ha_user_id'] for u in result['users']}
                ha_users=await hass.auth.async_get_users()
                result['available_ha_users']=[
                    {'id': u.id, 'name': u.name or '(Senza nome)'}
                    for u in ha_users
                    if u.is_active and not u.system_generated and u.id not in assigned
                ]
                result['available_ha_users'].sort(key=lambda u:(u['name'].casefold(),u['id']))
                # Also resolve display names for currently associated accounts,
                # including inactive ones, so edit forms retain their selection.
                lookup={u.id:u for u in ha_users}
                for u in result['users']:
                    ha=lookup.get(u['ha_user_id'])
                    u['ha_display_name']=(ha.name or '(Senza nome)') if ha else '(Account HA non più presente)'
            result['seconds_to_midnight']=seconds_to_midnight()
            connection.send_result(msg['id'],result)
        except Exception:
            _LOGGER.exception('Snapshot failed')
            connection.send_error(msg['id'],'database_error','Impossibile caricare i dati')

    @websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/board'})
    @websocket_api.async_response
    async def board(hass,connection,msg):
        try:
            result=await hass.async_add_executor_job(store.board_snapshot,dt_util.now().date())
            result['seconds_to_midnight']=seconds_to_midnight()
            connection.send_result(msg['id'],result)
        except Exception:
            _LOGGER.exception('Board snapshot failed')
            connection.send_error(msg['id'],'database_error','Impossibile caricare la bacheca')

    @websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/complete',vol.Required('assignment_id'):vol.Coerce(int)})
    @websocket_api.async_response
    async def complete(hass,connection,msg):
        try:
            await hass.async_add_executor_job(store.complete,msg['assignment_id'],connection.user.id,dt_util.now().date(),False)
            connection.send_result(msg['id'],{'ok':True})
            notify_changed()
        except (ChoreError,ValueError) as exc:
            connection.send_error(msg['id'],'invalid',str(exc))

    @websocket_api.require_admin
    @websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/manage',vol.Required('action'):vol.In(['add_user','edit_user','add_chore','edit_chore','absence','acknowledge','replan','delete_user','delete_chore']) ,vol.Optional('data',default={}):dict})
    @websocket_api.async_response
    async def manage(hass,connection,msg):
        action=msg['action']; d=msg['data']
        try:
            if action in ('add_user','edit_user'):
                ha_user=await hass.auth.async_get_user(d['ha_user_id'])
                if not ha_user or not ha_user.is_active or ha_user.system_generated:
                    raise ChoreError('Seleziona un account Home Assistant attivo e non di sistema')
                target_id=int(d['id']) if action=='edit_user' else None
                used_by=await hass.async_add_executor_job(store.account_owner,d['ha_user_id'])
                if used_by is not None and used_by!=target_id:
                    raise ChoreError('Questo account Home Assistant è già associato a un ospite')
                if action=='add_user':
                    call=partial(store.add_user,d['name'],d['ha_user_id'])
                else:
                    call=partial(store.edit_user,target_id,d['name'],d['ha_user_id'],d['active'])
            elif action=='add_chore': call=partial(store.add_chore,d['name'],d['start_date'],int(d['frequency']))
            elif action=='edit_chore': call=partial(store.edit_chore,int(d['id']),d['name'],d['active'])
            elif action=='delete_user': call=partial(store.delete_user,int(d['id']),d['confirm_name'],dt_util.now().date())
            elif action=='delete_chore': call=partial(store.delete_chore,int(d['id']),d['confirm_name'],dt_util.now().date())
            elif action=='absence': call=partial(store.absence,int(d['user_id']),d['start_date'],d['end_date'])
            elif action=='acknowledge': call=partial(store.acknowledge,int(d['id']),connection.user.id)
            elif action=='replan': call=partial(store.refresh_future,dt_util.now().date())
            await hass.async_add_executor_job(call)
            if action in ('add_user','edit_user','add_chore','edit_chore','absence'):
                await hass.async_add_executor_job(store.refresh_future,dt_util.now().date())
            connection.send_result(msg['id'],{'ok':True})
            notify_changed()
        except (ChoreError,KeyError,ValueError,TypeError,OverflowError,sqlite3.IntegrityError) as exc:
            connection.send_error(msg['id'],'invalid',str(exc))
        except Exception:
            _LOGGER.exception('Manage failed: %s',action)
            connection.send_error(msg['id'],'database_error','Operazione non riuscita')

    for cmd in (snapshot,board,complete,manage): websocket_api.async_register_command(hass,cmd)
    return True
