"""Proof of concept for AOI-driven, quasi-lazy access to remote COPC data."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import duckdb
from shapely.geometry import shape


DEFAULT_CATALOG = Path(__file__).with_name("ahn5.parquet")
DEFAULT_AOI = Path(__file__).with_name("aoi.json")


def load_aoi(aoi_path: Path):
    """Load the projected GeoJSON geometry used by both catalog and point filtering."""
    with aoi_path.open() as src:
        geojson = json.load(src)

    # Accept either a bare geometry, as used by aoi.json, or a GeoJSON Feature.
    geometry = shape(geojson["geometry"] if geojson.get("type") == "Feature" else geojson)
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"AOI must be a non-empty, valid geometry: {aoi_path}")

    # The catalog and AHN COPC coordinates are both RD New (EPSG:28992). GeoJSON
    # itself does not carry reliable projected CRS metadata, so that agreement is
    # an explicit precondition of this proof of concept.
    return geometry


def load_extensions(connection: duckdb.DuckDBPyConnection) -> None:
    """Install extensions when needed and load them into this connection."""
    connection.execute("INSTALL spatial; LOAD spatial;")
    connection.execute("INSTALL pdal FROM community; LOAD pdal;")


def select_intersecting_tiles(
    connection: duckdb.DuckDBPyConnection,
    catalog_path: Path,
    aoi_wkt: str,
) -> list[tuple[str, str]]:
    """Use DuckDB to intersect the AOI with each catalog bounding box."""
    query = """
        SELECT id, assets.data.href
        FROM read_parquet(?)
        WHERE ST_Intersects(
            ST_MakeEnvelope(bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax),
            ST_GeomFromText(?)
        )
        ORDER BY id
    """

    # Parameters are bound rather than interpolated into SQL. The GeoParquet
    # catalog is scanned here; no point-cloud files are opened at this stage.
    return connection.execute(query, [str(catalog_path), aoi_wkt]).fetchall()


def force_copc_reader_url(url: str) -> str:
    """Work around PDAL's case-sensitive `.copc.laz` reader inference."""
    parsed = urlsplit(url)
    if url.endswith(".copc.laz"):
        return url

    # AHN object names end in uppercase `.COPC.LAZ`. PDAL 2.10 otherwise
    # infers readers.las, which cannot prune the COPC hierarchy by polygon.
    # A URL fragment is not sent to the HTTP server, but makes the complete
    # string end in lowercase `.copc.laz`, selecting readers.copc correctly.
    fragment = f"{parsed.fragment}/.copc.laz" if parsed.fragment else "/.copc.laz"
    return urlunsplit(parsed._replace(fragment=fragment))


def summarize_copc_tile(
    connection: duckdb.DuckDBPyConnection,
    url: str,
    aoi_wkt: str,
    requests: int,
    resolution: float | None,
) -> tuple:
    """Read only AOI points from one COPC and return a compact SQL summary."""
    pipeline = json.dumps(
        [
            {
                "type": "filters.expression",
                "expression": "X == X",
            }
        ]
    )

    # The polygon is a reader option, not merely a downstream DuckDB predicate.
    # readers.copc can therefore use HTTP range requests and skip irrelevant
    # octree nodes before point records enter memory.
    options_sql = "MAP {'polygon': ?, 'requests': ?}"
    parameters: list[object] = [
        force_copc_reader_url(url),
        pipeline,
        aoi_wkt,
        str(requests),
    ]

    if resolution is not None:
        # COPC resolution limits the hierarchy depth for inexpensive previews.
        # Omitting it reads the selected polygon at full source resolution.
        options_sql = "MAP {'polygon': ?, 'requests': ?, 'resolution': ?}"
        parameters.append(str(resolution))

    query = f"""
        WITH points AS (
            SELECT *
            FROM PDAL_Pipeline(?, ?, options => {options_sql})
        )
        SELECT
            count(*) AS point_count,
            count_if(
                ST_Covers(ST_GeomFromText(?), ST_Point(X, Y))
            ) AS points_inside_aoi,
            min(X) AS min_x,
            max(X) AS max_x,
            min(Y) AS min_y,
            max(Y) AS max_y,
            min(Z) AS min_z,
            max(Z) AS max_z
        FROM points
    """

    # PDAL_Pipeline is used instead of PDAL_Read because the current community
    # extension records the pipeline's executed point count correctly after a
    # spatial COPC read. The no-op expression supplies the required filter
    # pipeline while all spatial pruning remains in readers.copc.
    parameters.append(aoi_wkt)
    return connection.execute(query, parameters).fetchone()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--aoi", type=Path, default=DEFAULT_AOI)
    parser.add_argument(
        "--requests",
        type=int,
        default=4,
        help="Concurrent HTTP requests used by each COPC reader (default: 4)",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        help="Optional COPC resolution in source units; omit for full resolution",
    )
    parser.add_argument(
        "--limit-tiles",
        type=int,
        help="Process only the first N matched tiles for a quick demonstration",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.requests < 1:
        raise ValueError("--requests must be at least 1")
    if args.resolution is not None and args.resolution <= 0:
        raise ValueError("--resolution must be positive")
    if args.limit_tiles is not None and args.limit_tiles < 1:
        raise ValueError("--limit-tiles must be at least 1")

    aoi = load_aoi(args.aoi)
    aoi_wkt = aoi.wkt

    connection = duckdb.connect(database=":memory:")
    load_extensions(connection)

    # Phase 1: query only the lightweight GeoParquet tile catalog.
    matched_tiles = select_intersecting_tiles(connection, args.catalog, aoi_wkt)
    print(f"Catalog matched {len(matched_tiles)} COPC tiles.")

    if args.limit_tiles is not None:
        matched_tiles = matched_tiles[: args.limit_tiles]
        print(f"Demonstration limited to {len(matched_tiles)} tiles.")

    # Phase 2: process one matched COPC at a time. This prevents a UNION ALL
    # query from retaining every tile's materialized PDAL PointView at once.
    total_points = 0
    for tile_id, url in matched_tiles:
        started = time.perf_counter()
        summary = summarize_copc_tile(
            connection,
            url,
            aoi_wkt,
            args.requests,
            args.resolution,
        )
        elapsed = time.perf_counter() - started
        point_count, points_inside, min_x, max_x, min_y, max_y, min_z, max_z = summary
        if points_inside != point_count:
            raise RuntimeError(
                f"Reader returned {point_count - points_inside} points outside the AOI"
            )
        total_points += point_count

        print(
            f"{tile_id}: {point_count:,} points in {elapsed:.2f}s; "
            f"XYZ bounds=({min_x}, {min_y}, {min_z}) to "
            f"({max_x}, {max_y}, {max_z})"
        )

    mode = f"resolution {args.resolution}" if args.resolution else "full resolution"
    print(f"Processed {total_points:,} AOI points at {mode}.")


if __name__ == "__main__":
    main()
