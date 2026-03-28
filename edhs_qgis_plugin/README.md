# EDHS Hybrid Plugin for QGIS

Choropleth maps for DHS/EDHS indicators in QGIS.

## Install the plugin

### 1. Find your QGIS plugins folder

- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`
- **Windows:** `C:\Users\YOUR_USERNAME\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`

Or in QGIS: **Settings → User profiles → Open active profile folder** → go to `python/plugins`.

### 2. Copy the plugin

Copy the entire `edhs_qgis_plugin` folder into the plugins folder so you have:

```
.../python/plugins/edhs_qgis_plugin/
    __init__.py
    edhs_qgis_plugin.py
    metadata.txt
    README.md
```

### 3. Enable in QGIS

1. Open QGIS
2. Go to **Plugins → Manage and Install Plugins**
3. Open the **Installed** tab
4. Search for **EDHS Hybrid**
5. Check the box to enable it

### 4. Open the plugin

- **Menu:** Plugins → DHS Hybrid Plugin Platform
- **Toolbar:** Click the EDHS icon (if visible)

## Requirements

- QGIS 3.16 or newer
- FastAPI backend running (e.g. `uvicorn edhs_core.main:app --reload`)
- Admin boundaries in `data/admin_boundaries/{country}/ADM{level}.gpkg`
