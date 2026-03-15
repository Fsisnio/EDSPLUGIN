import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsClassificationEqualInterval,
    QgsGraduatedSymbolRenderer,
    QgsProject,
    QgsRendererRange,
    QgsSymbol,
    QgsVectorLayer,
)
from qgis.utils import iface


@dataclass
class ApiConfig:
    """
    Configuration for connecting to the EDHS FastAPI backend.
    """

    base_url: str = "http://127.0.0.1:8000/api/v1"
    tenant_id: str = "demo-tenant"
    bearer_token: Optional[str] = None


class ApiClient:
    """
    Thin HTTP client for the EDHS FastAPI backend.

    Uses `requests` to:
    - Upload datasets
    - List indicators
    - Request spatial aggregations
    """

    def __init__(self, config: ApiConfig) -> None:
        self.config = config

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"X-Tenant-ID": self.config.tenant_id}
        if self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"
        return headers

    def upload_dataset(self, path: Path) -> str:
        url = f"{self.config.base_url}/sessions/upload"
        with path.open("rb") as f:
            files = {"file": (path.name, f)}
            resp = requests.post(url, headers=self._headers(), files=files, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["session_id"]

    def list_indicators(self) -> List[Dict[str, Any]]:
        url = f"{self.config.base_url}/indicators"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("indicators", [])

    def spatial_aggregate(
        self,
        session_id: str,
        indicator_id: str,
        country_code: str,
        admin_level: int,
        microdata_admin_column: str,
        boundary_admin_column: str,
        use_weights: bool = True,
        weight_var: str = "v005",
    ) -> Dict[str, Any]:
        url = f"{self.config.base_url}/spatial/aggregate"
        payload = {
            "session_id": session_id,
            "indicator_id": indicator_id,
            "country_code": country_code,
            "admin_level": admin_level,
            "microdata_admin_column": microdata_admin_column,
            "boundary_admin_column": boundary_admin_column,
            "use_weights": use_weights,
            "weight_var": weight_var,
            "extra_indicator_params": {},
        }
        resp = requests.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def dhs_api_indicators(
        self,
        country_ids: Optional[str] = None,
        indicator_ids: Optional[str] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetch indicators from DHS Program API (via backend proxy)."""
        url = f"{self.config.base_url}/dhs-api/indicators"
        params: Dict[str, Any] = {}
        if country_ids:
            params["country_ids"] = country_ids
        if indicator_ids:
            params["indicator_ids"] = indicator_ids
        if per_page is not None:
            params["perpage"] = per_page
        resp = requests.get(url, headers=self._headers(), params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def dhs_api_data(
        self,
        country_ids: str,
        indicator_ids: str,
        survey_year_start: Optional[int] = None,
        survey_year_end: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetch indicator data from DHS Program API (via backend proxy)."""
        url = f"{self.config.base_url}/dhs-api/data"
        params: Dict[str, Any] = {
            "country_ids": country_ids,
            "indicator_ids": indicator_ids,
        }
        if survey_year_start is not None:
            params["survey_year_start"] = survey_year_start
        if survey_year_end is not None:
            params["survey_year_end"] = survey_year_end
        resp = requests.get(url, headers=self._headers(), params=params, timeout=90)
        resp.raise_for_status()
        return resp.json()


class EdhsDialog(QDialog):
    """
    Main dialog for the EDHS QGIS plugin.

    Provides:
    - Dataset upload (.dta/.sav)
    - Indicator selection
    - Admin level & code configuration
    - Choropleth rendering and export
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("DHS Hybrid Plugin Plateform")
        self.setMinimumWidth(480)

        self.api_config = ApiConfig()
        self.api_client = ApiClient(self.api_config)

        self._session_id: Optional[str] = None
        self._last_geojson: Optional[Dict[str, Any]] = None
        self._dhs_api_data: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._wire_signals()
        self._load_indicators()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        tabs = QTabWidget()

        # API / Tenant configuration (shared)
        api_box = QGroupBox("Backend connection")
        api_group = QGridLayout()
        row = 0
        api_group.addWidget(QLabel("API base URL:"), row, 0)
        self.base_url_edit = QLineEdit(self.api_config.base_url)
        api_group.addWidget(self.base_url_edit, row, 1)

        row += 1
        api_group.addWidget(QLabel("Tenant ID:"), row, 0)
        self.tenant_edit = QLineEdit(self.api_config.tenant_id)
        api_group.addWidget(self.tenant_edit, row, 1)

        row += 1
        api_group.addWidget(QLabel("JWT access token (optional):"), row, 0)
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Paste Bearer token for secured deployments…")
        api_group.addWidget(self.token_edit, row, 1)

        api_box.setLayout(api_group)
        layout.addWidget(api_box)

        # --- Tab 1: Compute from microdata ---
        compute_tab = QWidget()
        compute_layout = QVBoxLayout(compute_tab)

        # Dataset upload
        upload_layout = QHBoxLayout()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("Select DHS/EDHS .dta or .sav file...")
        self.browse_button = QPushButton("Browse…")
        self.upload_button = QPushButton("Upload dataset")
        upload_layout.addWidget(self.dataset_path_edit)
        upload_layout.addWidget(self.browse_button)
        upload_layout.addWidget(self.upload_button)
        upload_box = QGroupBox("Dataset & indicator")
        upload_group = QVBoxLayout()
        upload_group.addLayout(upload_layout)

        # Indicator + weighting
        ind_group = QGridLayout()
        row = 0
        ind_group.addWidget(QLabel("Indicator:"), row, 0)
        self.indicator_combo = QComboBox()
        ind_group.addWidget(self.indicator_combo, row, 1)

        row += 1
        self.use_weights_check = QCheckBox("Use DHS weights (v005 / 1,000,000)")
        self.use_weights_check.setChecked(True)
        ind_group.addWidget(self.use_weights_check, row, 0, 1, 2)

        row += 1
        ind_group.addWidget(QLabel("Weight variable:"), row, 0)
        self.weight_var_edit = QLineEdit("v005")
        ind_group.addWidget(self.weight_var_edit, row, 1)

        upload_group.addLayout(ind_group)
        upload_box.setLayout(upload_group)
        compute_layout.addWidget(upload_box)

        # Spatial aggregation settings
        spatial_box = QGroupBox("Spatial aggregation")
        spatial_group = QGridLayout()
        row = 0
        spatial_group.addWidget(QLabel("Country code (ISO):"), row, 0)
        self.country_edit = QLineEdit("ETH")
        spatial_group.addWidget(self.country_edit, row, 1)

        row += 1
        spatial_group.addWidget(QLabel("Admin level:"), row, 0)
        self.admin_level_spin = QSpinBox()
        self.admin_level_spin.setMinimum(0)
        self.admin_level_spin.setMaximum(5)
        self.admin_level_spin.setValue(1)
        spatial_group.addWidget(self.admin_level_spin, row, 1)

        row += 1
        spatial_group.addWidget(QLabel("Microdata admin column:"), row, 0)
        self.micro_admin_edit = QLineEdit("admin1_code")
        spatial_group.addWidget(self.micro_admin_edit, row, 1)

        row += 1
        spatial_group.addWidget(QLabel("Boundary admin column:"), row, 0)
        self.boundary_admin_edit = QLineEdit("admin_id")
        spatial_group.addWidget(self.boundary_admin_edit, row, 1)

        spatial_box.setLayout(spatial_group)
        compute_layout.addWidget(spatial_box)

        # Action buttons
        button_layout = QHBoxLayout()
        self.compute_button = QPushButton("Compute & Render Choropleth")
        self.export_geojson_button = QPushButton("Export GeoJSON…")
        self.export_csv_button = QPushButton("Export CSV…")
        self.export_geojson_button.setEnabled(False)
        self.export_csv_button.setEnabled(False)
        button_layout.addWidget(self.compute_button)
        button_layout.addWidget(self.export_geojson_button)
        button_layout.addWidget(self.export_csv_button)
        compute_layout.addLayout(button_layout)

        # Log console
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(120)
        compute_layout.addWidget(self.log_edit)

        tabs.addTab(compute_tab, "Compute from microdata")

        # --- Tab 2: DHS Program API ---
        dhs_tab = QWidget()
        dhs_layout = QVBoxLayout(dhs_tab)

        dhs_box = QGroupBox("DHS Program API – Indicators & Data Export")
        dhs_group = QGridLayout()
        row = 0
        dhs_group.addWidget(QLabel("Country codes (comma-separated):"), row, 0)
        self.dhs_country_edit = QLineEdit("ET")
        self.dhs_country_edit.setPlaceholderText("e.g. ET,BJ,EG")
        dhs_group.addWidget(self.dhs_country_edit, row, 1)

        row += 1
        dhs_group.addWidget(QLabel("Indicator IDs (comma-separated):"), row, 0)
        self.dhs_indicator_edit = QLineEdit("FE_FRTR_W_A15")
        self.dhs_indicator_edit.setPlaceholderText("e.g. FE_FRTR_W_A15, CN_ANMC_C_ANY")
        dhs_group.addWidget(self.dhs_indicator_edit, row, 1)

        row += 1
        dhs_group.addWidget(QLabel("Survey year from:"), row, 0)
        self.dhs_year_start_spin = QSpinBox()
        self.dhs_year_start_spin.setRange(1990, 2030)
        self.dhs_year_start_spin.setValue(2000)
        dhs_group.addWidget(self.dhs_year_start_spin, row, 1)

        row += 1
        dhs_group.addWidget(QLabel("Survey year to:"), row, 0)
        self.dhs_year_end_spin = QSpinBox()
        self.dhs_year_end_spin.setRange(1990, 2030)
        self.dhs_year_end_spin.setValue(2024)
        dhs_group.addWidget(self.dhs_year_end_spin, row, 1)

        dhs_box.setLayout(dhs_group)
        dhs_layout.addWidget(dhs_box)

        dhs_btn_layout = QHBoxLayout()
        self.dhs_fetch_button = QPushButton("Fetch DHS Program data")
        self.dhs_export_csv_button = QPushButton("Export DHS data (CSV)…")
        self.dhs_export_json_button = QPushButton("Export DHS data (JSON)…")
        self.dhs_export_csv_button.setEnabled(False)
        self.dhs_export_json_button.setEnabled(False)
        dhs_btn_layout.addWidget(self.dhs_fetch_button)
        dhs_btn_layout.addWidget(self.dhs_export_csv_button)
        dhs_btn_layout.addWidget(self.dhs_export_json_button)
        dhs_layout.addLayout(dhs_btn_layout)

        tabs.addTab(dhs_tab, "DHS Program API")

        layout.addWidget(tabs)
        self.setLayout(layout)

    def _wire_signals(self) -> None:
        self.browse_button.clicked.connect(self._on_browse_clicked)
        self.upload_button.clicked.connect(self._on_upload_clicked)
        self.compute_button.clicked.connect(self._on_compute_clicked)
        self.export_geojson_button.clicked.connect(self._on_export_geojson_clicked)
        self.export_csv_button.clicked.connect(self._on_export_csv_clicked)
        self.dhs_fetch_button.clicked.connect(self._on_dhs_fetch_clicked)
        self.dhs_export_csv_button.clicked.connect(self._on_dhs_export_csv_clicked)
        self.dhs_export_json_button.clicked.connect(self._on_dhs_export_json_clicked)

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _log(self, message: str) -> None:
        self.log_edit.append(message)

    def _set_api_config_from_ui(self) -> None:
        self.api_config.base_url = self.base_url_edit.text().strip()
        self.api_config.tenant_id = self.tenant_edit.text().strip() or "default"
        token = self.token_edit.text().strip()
        self.api_config.bearer_token = token or None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _load_indicators(self) -> None:
        try:
            self._set_api_config_from_ui()
            indicators = self.api_client.list_indicators()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "EDHS – Indicators", f"Failed to load indicators:\n{exc}")
            self._log(f"Failed to load indicators: {exc}")
            return

        self.indicator_combo.clear()
        for ind in indicators:
            label = f"{ind['id']} – {ind['name']}"
            self.indicator_combo.addItem(label, ind["id"])
        self._log(f"Loaded {len(indicators)} indicators from backend.")

    def _on_browse_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select DHS/EDHS dataset",
            "",
            "Stata/SPA files (*.dta *.sav);;All files (*)",
        )
        if path:
            self.dataset_path_edit.setText(path)

    def _on_upload_clicked(self) -> None:
        path_text = self.dataset_path_edit.text().strip()
        if not path_text:
            QMessageBox.information(self, "EDHS – Upload", "Please select a dataset file first.")
            self._log("Please select a dataset file first.")
            return

        path = Path(path_text)
        if not path.exists():
            QMessageBox.warning(self, "EDHS – Upload", f"File does not exist:\n{path}")
            self._log(f"File does not exist: {path}")
            return

        try:
            self._set_api_config_from_ui()
            self._log(f"Uploading dataset: {path} …")
            session_id = self.api_client.upload_dataset(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "EDHS – Upload", f"Upload failed:\n{exc}")
            self._log(f"Upload failed: {exc}")
            return

        self._session_id = session_id
        self._log(f"Upload complete. Session ID: {session_id}")

    def _on_compute_clicked(self) -> None:
        if not self._session_id:
            QMessageBox.information(
                self,
                "EDHS – Compute",
                "No active session.\nUpload a dataset or create a backend mock session first.",
            )
            self._log("No session. Upload a dataset or use a backend mock session first.")
            return

        indicator_id = self.indicator_combo.currentData()
        if not indicator_id:
            QMessageBox.information(self, "EDHS – Compute", "No indicator selected.")
            self._log("No indicator selected.")
            return

        self._set_api_config_from_ui()

        try:
            result = self.api_client.spatial_aggregate(
                session_id=self._session_id,
                indicator_id=indicator_id,
                country_code=self.country_edit.text().strip(),
                admin_level=int(self.admin_level_spin.value()),
                microdata_admin_column=self.micro_admin_edit.text().strip(),
                boundary_admin_column=self.boundary_admin_edit.text().strip(),
                use_weights=self.use_weights_check.isChecked(),
                weight_var=self.weight_var_edit.text().strip() or "v005",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "EDHS – Spatial aggregation", f"Spatial aggregation failed:\n{exc}")
            self._log(f"Spatial aggregation failed: {exc}")
            return

        self._last_geojson = result["geojson"]
        self._log("Spatial aggregation succeeded. Rendering choropleth layer…")

        self._render_geojson_layer(
            geojson=self._last_geojson,
            layer_name=f"EDHS {indicator_id}",
        )
        self.export_geojson_button.setEnabled(True)
        self.export_csv_button.setEnabled(True)

    def _render_geojson_layer(self, geojson: Dict[str, Any], layer_name: str) -> None:
        # Write GeoJSON to a temporary file so QGIS can load it via OGR.
        tmp_path = Path(QgsProject.instance().homePath() or str(Path.home())) / "edhs_choropleth_tmp.geojson"
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(geojson, f)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "EDHS – Rendering", f"Failed to write temporary GeoJSON:\n{exc}")
            self._log(f"Failed to write temporary GeoJSON: {exc}")
            return

        uri = str(tmp_path)
        layer = QgsVectorLayer(uri, layer_name, "ogr")
        if not layer.isValid():
            QMessageBox.critical(self, "EDHS – Rendering", "Failed to load GeoJSON as a QGIS layer.")
            self._log("Failed to load GeoJSON as a QGIS layer.")
            return

        # Apply a simple graduated renderer on the `value` field.
        value_field = "value"
        idx = layer.fields().indexOf(value_field)
        if idx != -1:
            self._apply_graduated_style(layer, value_field)

        QgsProject.instance().addMapLayer(layer)
        self._log(f"Added choropleth layer: {layer_name}")

    def _apply_graduated_style(self, layer: QgsVectorLayer, field_name: str) -> None:
        # Collect min/max from the field.
        values = [
            f[field_name]
            for f in layer.getFeatures()
            if f[field_name] is not None
        ]
        if not values:
            return

        vmin, vmax = min(values), max(values)
        if vmin == vmax:
            vmax = vmin + 1.0

        num_classes = 5
        interval = (vmax - vmin) / num_classes

        ranges: List[QgsRendererRange] = []
        for i in range(num_classes):
            lower = vmin + i * interval
            upper = vmin + (i + 1) * interval if i < num_classes - 1 else vmax
            label = f"{lower:.2f} – {upper:.2f}"
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setOpacity(0.8)
            rng = QgsRendererRange(lower, upper, symbol, label)
            ranges.append(rng)

        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
        renderer.setMode(QgsGraduatedSymbolRenderer.EqualInterval)
        layer.setRenderer(renderer)

    def _on_export_geojson_clicked(self) -> None:
        if not self._last_geojson:
            QMessageBox.information(self, "EDHS – Export GeoJSON", "No GeoJSON to export.")
            self._log("No GeoJSON to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export GeoJSON",
            "",
            "GeoJSON (*.geojson *.json);;All files (*)",
        )
        if not path:
            return

        try:
            with Path(path).open("w", encoding="utf-8") as f:
                json.dump(self._last_geojson, f)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "EDHS – Export GeoJSON", f"Failed to export GeoJSON:\n{exc}")
            self._log(f"Failed to export GeoJSON: {exc}")
            return

        self._log(f"Exported GeoJSON to {path}")

    def _on_export_csv_clicked(self) -> None:
        if not self._last_geojson:
            QMessageBox.information(self, "EDHS – Export CSV", "No GeoJSON to export.")
            self._log("No GeoJSON to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return

        features = self._last_geojson.get("features", [])
        if not features:
            QMessageBox.information(self, "EDHS – Export CSV", "GeoJSON has no features to export.")
            self._log("GeoJSON has no features to export.")
            return

        # Extract admin id and value from feature properties.
        rows = []
        for feat in features:
            props = feat.get("properties", {})
            rows.append(
                {
                    "admin_id": props.get("admin_id"),
                    "value": props.get("value"),
                },
            )

        try:
            import csv

            with Path(path).open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["admin_id", "value"])
                writer.writeheader()
                writer.writerows(rows)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "EDHS – Export CSV", f"Failed to export CSV:\n{exc}")
            self._log(f"Failed to export CSV: {exc}")
            return

        self._log(f"Exported CSV to {path}")

    def _on_dhs_fetch_clicked(self) -> None:
        country_ids = self.dhs_country_edit.text().strip()
        indicator_ids = self.dhs_indicator_edit.text().strip()
        if not country_ids or not indicator_ids:
            QMessageBox.information(
                self,
                "DHS Program API",
                "Enter at least one country code and one indicator ID.",
            )
            self._log("DHS API: Enter country and indicator IDs.")
            return

        try:
            self._set_api_config_from_ui()
            self._log("Fetching DHS Program data…")
            result = self.api_client.dhs_api_data(
                country_ids=country_ids,
                indicator_ids=indicator_ids,
                survey_year_start=self.dhs_year_start_spin.value(),
                survey_year_end=self.dhs_year_end_spin.value(),
            )
            self._dhs_api_data = result
            rows = result.get("Data", [])
            self._log(f"DHS Program API: Retrieved {len(rows)} records.")
            self.dhs_export_csv_button.setEnabled(bool(rows))
            self.dhs_export_json_button.setEnabled(bool(rows))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "DHS Program API",
                f"Fetch failed:\n{exc}",
            )
            self._log(f"DHS API fetch failed: {exc}")

    def _on_dhs_export_csv_clicked(self) -> None:
        if not self._dhs_api_data:
            QMessageBox.information(self, "DHS Export", "No DHS data to export. Fetch data first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export DHS data (CSV)",
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return

        rows = self._dhs_api_data.get("Data", [])
        if not rows:
            QMessageBox.information(self, "DHS Export", "No data rows to export.")
            return

        try:
            import csv as csv_module

            fieldnames = list(rows[0].keys())
            with Path(path).open("w", encoding="utf-8", newline="") as f:
                writer = csv_module.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            self._log(f"Exported DHS data to CSV: {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "DHS Export", f"Export failed:\n{exc}")

    def _on_dhs_export_json_clicked(self) -> None:
        if not self._dhs_api_data:
            QMessageBox.information(self, "DHS Export", "No DHS data to export. Fetch data first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export DHS data (JSON)",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return

        try:
            with Path(path).open("w", encoding="utf-8") as f:
                json.dump(self._dhs_api_data, f, indent=2)
            self._log(f"Exported DHS data to JSON: {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "DHS Export", f"Export failed:\n{exc}")


class EdhsQgisPlugin:
    """
    QGIS plugin wrapper integrating the EDHS dialog into QGIS.
    """

    def __init__(self, iface_) -> None:
        self.iface = iface_
        self._action: Optional[QPushButton] = None
        self._dialog: Optional[EdhsDialog] = None

    def initGui(self) -> None:  # noqa: N802
        """
        Called by QGIS to set up the plugin GUI (toolbar/menu).
        """

        from qgis.PyQt.QtWidgets import QAction  # Imported lazily for QGIS environment

        self._action = QAction("DHS Hybrid Plugin Plateform", self.iface.mainWindow())
        self._action.triggered.connect(self._show_dialog)
        self.iface.addPluginToMenu("&DHS Hybrid Plugin Plateform", self._action)
        self.iface.addToolBarIcon(self._action)

    def unload(self) -> None:
        """
        Called by QGIS when the plugin is unloaded.
        """

        if self._action is not None:
            self.iface.removePluginMenu("&DHS Hybrid Plugin Plateform", self._action)
            self.iface.removeToolBarIcon(self._action)
        self._action = None
        self._dialog = None

    def _show_dialog(self) -> None:
        if self._dialog is None:
            self._dialog = EdhsDialog(self.iface.mainWindow())
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

