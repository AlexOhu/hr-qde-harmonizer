// Einmalige Neosemantics-Initialisierung (n10s) für den HR-QDE-Graphen.
// Ausführen z.B. über cypher-shell oder den Neo4j Browser (http://localhost:7474).

// Uniqueness-Constraint für importierte RDF-Ressourcen (Voraussetzung für n10s)
CREATE CONSTRAINT n10s_uniqueness IF NOT EXISTS
FOR (r:Resource) REQUIRE r.uri IS UNIQUE;

// Graph-Konfiguration: SKOS-Konzepte als Knoten, prefLabel als Anzeigename
CALL n10s.graphconfig.init({
  handleVocabUris: "MAP",
  handleMultival: "ARRAY",
  keepLangTag: true,
  handleRDFTypes: "LABELS"
});

// Namespace-Präfixe für HR-QDE und Standard-Vokabulare registrieren
CALL n10s.nsprefixes.add("skos", "http://www.w3.org/2004/02/skos/core#");
CALL n10s.nsprefixes.add("hrqde", "https://hrqde.example.org/ontology#");
