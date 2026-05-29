import geopandas as gpd
import numpy as np
import laspy
from shapely.geometry import Point #, Polygon



def create_query(header):
    querys = []

    sizes = header.maxs - header.mins

    # Bottom left
    query_bounds = laspy.Bounds(mins=header.mins, maxs=header.mins + sizes / 2)
    query_bounds.maxs[2] = header.maxs[2]
    querys.append(query_bounds)

    # Top Right
    # Bounds can also be 2D (then all Z are considered)
    query_bounds = laspy.Bounds(mins=(header.mins + sizes / 2)[:2], maxs=header.maxs[:2])
    querys.append(query_bounds)

    return querys



# Load crop geometry from a local GeoJSON file
gdf = gpd.read_file("aoi.geojson")
poly_gdf = gpd.GeoDataFrame(index=[0], geometry=gdf.geometry)



# Note, currently selected COPC files are hardcoded. TODO: collect from aHN5_aoi.json.
paths = [
        "https://fsn1.your-objectstorage.com/hwh-ahn/AHN5_KM/01_LAZ/AHN5_C_124000_485000.COPC.LAZ",
        "https://fsn1.your-objectstorage.com/hwh-ahn/AHN5_KM/01_LAZ/AHN5_C_125000_484000.COPC.LAZ",
        "https://fsn1.your-objectstorage.com/hwh-ahn/AHN5_KM/01_LAZ/AHN5_C_125000_485000.COPC.LAZ",
        "https://fsn1.your-objectstorage.com/hwh-ahn/AHN5_KM/01_LAZ/AHN5_C_126000_484000.COPC.LAZ",
        "https://fsn1.your-objectstorage.com/hwh-ahn/AHN5_KM/01_LAZ/AHN5_C_126000_485000.COPC.LAZ"
    ]

create = True

for path in paths:
    with laspy.CopcReader.open(path) as crdr:
        print("copc_reader_ready")



        if create:
            # Create empty output file.
            new_header = laspy.LasHeader(
                version=crdr.header.version,
                point_format=crdr.header.point_format
            )
            new_header.offsets = crdr.header.offsets
            new_header.scales = crdr.header.scales
            with laspy.open(f"output_laspy.laz", mode="w", header=new_header, do_compress=True) as f:
                print("created: output_laspy.laz")
                create = False


        querys = create_query(crdr.header)
        for i, query_bounds in enumerate(querys):
            resolution = None
            points = crdr.query(query_bounds, resolution=resolution)
            print("Spatial Query gave:", points)
            print(len(points) / crdr.header.point_count * 100);

            # 3. Create a GeoDataFrame from LAS X and Y coordinates
            coords = np.vstack((points.x, points.y)).T
            point_gdf = gpd.GeoDataFrame(geometry=[Point(xy) for xy in coords])
            point_gdf.set_crs(epsg=7415, inplace=True)

            # 4. Perform a spatial join to find points within the polygon
            # (Ensure CRS matches between the polygon and the point cloud)
            joined = gpd.sjoin(point_gdf, poly_gdf, predicate="within", how="inner")
            valid_indices = joined.index.to_numpy()

            print("Cropped points:", len(valid_indices))


            if len(valid_indices) > 0:
                new_header = laspy.LasHeader(
                    version=crdr.header.version,
                    point_format=crdr.header.point_format
                )
                new_header.offsets = crdr.header.offsets
                new_header.scales = crdr.header.scales
                with laspy.open(f"output_laspy.laz", mode="a", header=new_header, do_compress=True) as f:
                    f.append_points(points[valid_indices])



