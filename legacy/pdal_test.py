import pdal
import json

fp = "https://fsn1.your-objectstorage.com/hwh-ahn/AHN5_KM/01_LAZ/AHN5_C_124000_485000.COPC.LAZ"

pipeline = {
    "pipeline": [
        {
            "type": "readers.copc",
            "filename": fp
        }
    ]
}

print("Constructing pipeline")

p = pdal.Pipeline(json.dumps(pipeline))

print("Executing pipeline")

count = p.execute()

print("Point count:", count)