from pathlib import Path
from typing import Dict

import geopandas as gpd
import pandas as pd

from ..config import settings
from ..indicators import BaseIndicator
from ..utils.sessions import SessionData


def load_admin_boundaries(country_code: str, admin_level: int) -> gpd.GeoDataFrame:
    """
    Load admin boundary polygons for a given country and admin level.

    Files are expected to follow the convention:
        {ADMIN_BOUNDARIES_ROOT}/{country_code}/ADM{admin_level}.gpkg

    This keeps spatial datasets separate from microdata and allows
    deployment-specific configuration without changing code.
    """

    root = Path(settings.ADMIN_BOUNDARIES_ROOT)
    path = root / country_code.upper() / f"ADM{admin_level}.gpkg"
    if not path.exists():
        raise FileNotFoundError(f"Admin boundary file not found: {path}")

    return gpd.read_file(path)


def aggregate_indicator_by_admin(
    session: SessionData,
    indicator: BaseIndicator,
    group_by_column: str,
    admin_gdf: gpd.GeoDataFrame,
    admin_id_column: str,
) -> gpd.GeoDataFrame:
    """
    Compute an indicator by admin unit and attach results to polygons.

    Steps:
    - Use the indicator's grouped computation over the session DataFrame
      with `group_by_column` (e.g. admin code in microdata).
    - Merge the resulting table into `admin_gdf` using `admin_id_column`.
    """

    grouped_df = indicator.compute_grouped(session.df, group_by=group_by_column)

    merged = admin_gdf.merge(
        grouped_df,
        left_on=admin_id_column,
        right_on=group_by_column,
        how="left",
    )
    return merged


def geodf_to_choropleth_geojson(
    gdf: gpd.GeoDataFrame,
    value_column: str = "estimate",
    id_column: str = "admin_id",
) -> Dict:
    """
    Convert a GeoDataFrame into choropleth-ready GeoJSON.

    The resulting FeatureCollection exposes:
    - geometry: polygon geometry
    - properties: at minimum `id` and `value`, plus any other attributes.
    """

    # Create a copy to control property names.
    df = gdf.copy()
    df["id"] = df[id_column]
    # Coerce NaN to None so JSON serialization produces null (NaN is invalid in JSON).
    if value_column not in df.columns:
        raise ValueError(f"Value column '{value_column}' not in GeoDataFrame.")
    df["value"] = df[value_column].apply(lambda x: None if pd.isna(x) else x)

    import json

    geojson_str = df.to_json()
    return json.loads(geojson_str)
