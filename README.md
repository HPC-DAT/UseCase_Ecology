# UseCase_Ecology
Repository for the Ecology use case



# Install dependencies

PDAL >= 2.5 and GDAL >= 3.0
PDAL_wrench
rustac

```(bash)
conda update -n base -c conda-forge conda
conda create -n eecolidar -y
conda activate eecolidar
conda install -c conda-forge pdal python-pdal gdal pdal_wrench rustac
```

test:
```(bash)
pdal_wrench --version
rustac --version
```

# Download list of CPOC files

from https://basisdata.nl/hwh-portal/download/index.html
AHNx -> Puntenwolk -> Puntenwolk (1x1 km) -> Selectie exporteren (txt)

Note, for geoJSON file, use:
AHNx -> Puntenwolk -> Puntenwolk (1x1 km) -> Selectie exporteren (GeoJSON, RD)

However, PDAL_wrench works with the txt file.

Example provided of 9 COPC URLs: `selectie.txt`.

# Convert to VPC

```(bash)
pdal_wrench build_vpc --output=ahn5.vpc --input-file-list=selectie.txt
```

Note, could also work on list of local files:
pdal_wrench build_vpc --output=ahn5.vpc 65DN1_07.LAZ 65DN1_08.LAZ 65DN1_12.LAZ 65DN1_13.LAZ

# Convert to geoParquet

```(bash)
rustac translate -i json ahn5.vpc ahn5.parquet
```

# Define area of interest

Define the area of interest as a GeoJSON polygon.
Some notes on creating your own:
* The shape must be closed (first point = last point).
* Use x,y coordinates (or lon,lat), instead of the common lat,lon order.                Requires WGS84 ???
* Right hand rule: counter-clockwise order to define interior.
* Exterior boundary, then holes.
You can test your shape on `GeoJSON.io` 

Example provided: `aoi.json'.

# Filter STAC by area of interest

Note that this could output the filtered dataset in various formats.
Cropping the COPC files using PDAL expects a JSON STAC endpoint.

```(bash)
rustac search --intersects "$(cat aoi.json)" ahn5.parquet ahn5_aoi.json
```

# Filter COPC by area of interest

```(bash)
pdal pipeline pdal_pipeline.json
```

Note, PDAL has a couple peculiarities that make it awkward to work with:
* It cannot correctly detect the input CRS from the STAC WKT (at least for Amersfoort / RD New + NAP height); the CRS should be supplied manually.
* It cannot read .json files for the crop polygon; this must manually be reformatted to a `POLYGON((...))` string.
* It does not automatically set the CRS for the output COPC; this must be set manually.

However, it can read and write COPC files.


