from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

c = QdrantClient(url="http://qdrant:6333")
c.delete_collection("epc_documents")
c.create_collection(
    "epc_documents",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
)
print("Collection reset.")