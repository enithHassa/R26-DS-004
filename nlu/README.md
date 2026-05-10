# NLU Workspace

Datasets, label guides, and experiment artifacts for intent/entity modeling.

**Phase 3 Step 11:** canonical **entity slot → Neo4j** resolution table lives in [`knowledge_graph/nlu_entity_graph_map_v1.json`](../knowledge_graph/nlu_entity_graph_map_v1.json) (validated by `scripts/kg_nlu_entity_map_lib.py`).

**Phase 3 Step 12:** **intent → graph entry** starters (parameterized Cypher templates) in [`knowledge_graph/nlu_intent_graph_map_v1.json`](../knowledge_graph/nlu_intent_graph_map_v1.json) (`scripts/kg_nlu_intent_map_lib.py`).
