import sys
sys.path.insert(0, ".")
from app.services import kqr_service

for kqr_id in ["dqr_l6_walkthrough_slice", "esco_ikt_walkthrough_slice"]:
    emb = kqr_service.get_embeddings(kqr_id)
    concepts = kqr_service.get_concepts(kqr_id)
    print(kqr_id, "-> Konzepte:", len(concepts), "| Embeddings:", len(emb))
