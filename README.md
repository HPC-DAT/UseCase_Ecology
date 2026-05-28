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

There's a local copy reduced to 10 COPC URLs.

Note, for geoJSON file, use:
AHNx -> Puntenwolk -> Puntenwolk (1x1 km) -> Selectie exporteren (GeoJSON, RD)

However, PDAL_wrench works with the txt file.

# Run PDAL_wrench

```(bash)
pdal_wrench build_vpc --output=ahn5.vpc --input-file-list=selectie.txt
```

Note, could also work on list of local files:
pdal_wrench build_vpc --output=ahn5.vpc 65DN1_07.LAZ 65DN1_08.LAZ 65DN1_12.LAZ 65DN1_13.LAZ

# Run geoParquet

```(bash)
rustac translate -i json ahn5.vpc ahn5.parquet
```


