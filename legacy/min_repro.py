import duckdb

conn = duckdb.connect()

conn.execute("INSTALL pdal FROM community;")
conn.execute("LOAD pdal;")

query = """
SELECT *
FROM PDAL_Read('AHN5_C_124000_485000.COPC.LAZ')
LIMIT 1;  
"""

print(conn.execute(query).fetchall())