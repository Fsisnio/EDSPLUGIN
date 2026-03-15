from typing import Literal

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def clusters_from_dataframe(
    df: pd.DataFrame,
    cluster_id_col: str,
    lon_col: str,
    lat_col: str,
    crs: str = "EPSG:4326",
) -> gpd.GeoDataFrame:
    """
    Build a GeoDataFrame of cluster points from a DHS-like DataFrame.

    Parameters
    ----------
    df:
        DataFrame containing at least cluster id, longitude, and latitude.
    cluster_id_col:
        Column with cluster identifiers (e.g. v001 or hv001).
    lon_col:
        Longitude column in decimal degrees.
    lat_col:
        Latitude column in decimal degrees.
    crs:
        Coordinate reference system for the output GeoDataFrame.
    """

    if cluster_id_col not in df.columns:
        raise ValueError(f"Cluster id column '{cluster_id_col}' not found.")
    if lon_col not in df.columns or lat_col not in df.columns:
        raise ValueError("Longitude/latitude columns not found.")

    geometry = [Point(xy) for xy in zip(df[lon_col].astype(float), df[lat_col].astype(float))]
    gdf = gpd.GeoDataFrame(df[[cluster_id_col]].copy(), geometry=geometry, crs=crs)
    return gdf


def spatial_join_clusters_to_admin(
    clusters_gdf: gpd.GeoDataFrame,
    admin_gdf: gpd.GeoDataFrame,
    how: Literal["left", "right", "inner"] = "left",
    admin_id_col: str = "admin_id",
) -> gpd.GeoDataFrame:
    """
    Spatially join cluster points to admin polygons.

    The resulting GeoDataFrame contains cluster ids with an attached
    admin identifier suitable for further aggregation.
    """

    if admin_gdf.crs != clusters_gdf.crs:
        admin_gdf = admin_gdf.to_crs(clusters_gdf.crs)

    joined = gpd.sjoin(clusters_gdf, admin_gdf[[admin_id_col, "geometry"]], how=how)
    return joined
