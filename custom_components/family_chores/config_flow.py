"""Browser-based setup of Family Chores."""
from homeassistant import config_entries

DOMAIN = "family_chores"

class FamilyChoresConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One installation per Home Assistant instance."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create an empty configuration with no external credentials."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Family Chores", data={})
        return self.async_show_form(step_id="user")
