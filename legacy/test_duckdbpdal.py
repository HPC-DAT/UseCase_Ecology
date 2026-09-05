from rustac import DuckdbClient
import geopandas as gpd 
import pandas as pd
import duckdb

import json
import shapely as sp

import pyarrow.compute as pc



def extract_copc_url(asset_row):

    if asset_row is None:
        return None

    #STRING SUPPORT DOESN"T WORK    
    if isinstance(asset_row, str):
        asset_dict = json.loads(asset_row)

    elif isinstance(asset_row, dict):
        asset_dict = asset_row

    else:
        asset_dict = dict(asset_row)

    return asset_dict.get("data", {}).get("href")

def format_shapely_for_pdal(geometry):
    """
    Transforms a Shapely geometry into optimized strings 
    compatible with PDAL's spatial filtering parameters.
    """
    # 1. Generate the 'bounds' string for the initial COPC octree pruning
    minx, miny, maxx, maxy = geometry.bounds
    pdal_bounds = f"([{minx}, {maxx}], [{miny}, {maxy}])"
    
    # 2. Generate the 'polygon' WKT string for the exact vector boundary clip
    # PDAL expects standard Well-Known Text (WKT)
    pdal_polygon_wkt = geometry.wkt
    
    return {
        "bounds": pdal_bounds,
        "polygon_wkt": pdal_polygon_wkt
    }


def main():
    
    conn = duckdb.connect(database=":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    conn.execute("INSTALL pdal FROM community; LOAD pdal;")
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute("SET threads=1;")


    with open("aoi.json") as f:
        aoi = json.load(f)
        f.close()

    aoi_geom = sp.geometry.shape(aoi)

    client = DuckdbClient()
    copc_table = client.search_to_arrow(
    "ahn5.parquet",
    intersects=aoi,
    )

    assets = copc_table.column("assets").to_pylist()

    matched_copc_files = [
        u for u in map(extract_copc_url, assets)
        if u is not None
    ]

    pdal_geom = format_shapely_for_pdal(aoi_geom)

    pdal_bounds = pdal_geom["bounds"]
    pdal_wkt = pdal_geom["polygon_wkt"]

    pipeline = {
        "type":"readers.copc",
        "bounds": pdal_bounds,
    }

    pipeline_json = json.dumps(pipeline)

    pipeline_json_sql = pipeline_json.replace("'", "''")

    table = []

    for fp in matched_copc_files:
        fp = "AHN5_C_124000_485000.COPC.LAZ"
        print(fp)
        query = f"""
        SELECT *
        FROM PDAL_Read('{fp}')
        LIMIT 1;
        """

        #query = f"""
        #SELECT *
        #FROM PDAL_Pipeline('{fp}','[{pipeline_json}]')
        #LIMIT 10;
        #"""

        rows = conn.execute(query).fetchall()

        print(rows)

        #query = f"""
        #SELECT *
        #FROM PDAL_Pipeline('{fp}','[{pipeline_json}]');
        #"""
        #arrow_table = conn.execute(query).arrow()
        #print(f"Loaded {len(arrow_table)} points directly into PyArrow table.")
        #table.append(arrow_table)

    #print(len(table))

if __name__ == "__main__":
    main()