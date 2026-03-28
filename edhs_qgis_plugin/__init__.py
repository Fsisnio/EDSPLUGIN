"""
QGIS plugin entry point for the DHS Hybrid Plugin Platform.

This plugin connects a running local FastAPI backend (EDHS core engine)
to QGIS, allowing users to:
- Upload DHS/EDHS survey datasets to the backend (session-based only)
- Select an indicator and admin level
- Request a choropleth-ready GeoJSON from the backend
- Render the result as a map layer and export outputs

To use it in QGIS, copy the `edhs_qgis_plugin` directory into your
QGIS Python plugins folder and enable it from the Plugin Manager.
"""


def classFactory(iface):  # type: ignore[override]
    """
    QGIS calls this to instantiate the plugin.

    Parameters
    ----------
    iface:
        The QGIS interface instance.
    """

    from .edhs_qgis_plugin import EdhsQgisPlugin

    return EdhsQgisPlugin(iface)

