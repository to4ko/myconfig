"""Custom panel for UI Logs"""


async def async_setup(hass, config):
    """Set up this integration using yaml."""
    url = "/api/panel_custom/uilogs"
    location = hass.config.path("custom_components/uilogs/uilogs.js.gz")
    hass.http.register_static_path(url, location)
    hass.components.frontend.async_register_built_in_panel(
        component_name="custom",
        sidebar_title="Logs",
        sidebar_icon="mdi:math-log",
        frontend_url_path="uilogs",
        config={
            "_panel_custom": {
                "name": "ui-logs",
                "embed_iframe": False,
                "trust_external": False,
                "js_url": url,
            }
        },
        require_admin=True,
    )
    return True
