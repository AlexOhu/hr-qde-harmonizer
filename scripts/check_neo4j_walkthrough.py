import sys
sys.path.insert(0, ".")
from app.graph import neo4j_client

driver = neo4j_client.get_driver("bolt://localhost:7687", "neo4j", "changeme123")
with driver.session() as s:
    for uri in [
        "http://data.bmbf.de/dqr/L6_Knowledge",
        "http://data.europa.eu/esco/skill/dad7e408-162f-46a4-8567-db560e19e2fc",
    ]:
        r = s.run("MATCH (n:Resource {uri: $u}) RETURN n", u=uri).single()
        print(uri, "->", "gefunden" if r else "NICHT gefunden")

    total_dqr = s.run(
        "MATCH (n:Resource) WHERE n.uri STARTS WITH 'http://data.bmbf.de/dqr/' RETURN count(n) AS c"
    ).single()["c"]
    print("DQR-Knoten (data.bmbf.de/dqr/) gesamt:", total_dqr)

driver.close()
