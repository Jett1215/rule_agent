"""Read stored Chroma records without invoking any model."""


def get_file_collection(client, knowledge_id):
    names = [item if isinstance(item, str) else item.name for item in client.list_collections()]
    if knowledge_id not in names:
        return None
    return client.get_collection(name=knowledge_id, embedding_function=None)


def browse_file_chunks(client, knowledge_id, file_id, page=1, page_size=10, search=""):
    collection = get_file_collection(client, knowledge_id)
    result = {"items": [], "total": 0, "content_count": 0, "summary_count": 0,
              "page": page, "page_size": page_size}
    if collection is None:
        return result
    where = {"file_id": file_id}
    metadata_rows = collection.get(where=where, include=["metadatas"])
    result["summary_count"] = sum(bool((m or {}).get("is_summary")) for m in metadata_rows["metadatas"])
    result["content_count"] = len(metadata_rows["ids"]) - result["summary_count"]
    filters = {"where": where}
    if search:
        filters["where_document"] = {"$contains": search}
        result["total"] = len(collection.get(**filters, include=[])["ids"])
    else:
        result["total"] = len(metadata_rows["ids"])
    rows = collection.get(**filters, limit=page_size, offset=(page - 1) * page_size,
                          include=["documents", "metadatas", "embeddings"])
    for i, record_id in enumerate(rows["ids"]):
        vector = rows["embeddings"][i]
        content = rows["documents"][i] or ""
        result["items"].append({
            "id": record_id, "content": content, "character_count": len(content),
            "metadata": rows["metadatas"][i] or {},
            "vector_dimension": len(vector), "vector_preview": vector[:8].tolist(),
        })
    return result


def get_chunk_vector(client, knowledge_id, file_id, record_id):
    collection = get_file_collection(client, knowledge_id)
    if collection is None:
        return None
    rows = collection.get(ids=[record_id], where={"file_id": file_id}, include=["embeddings"])
    if not rows["ids"]:
        return None
    return {"id": record_id, "embedding": rows["embeddings"][0].tolist()}


def export_file_chunks(client, knowledge_id, file_id):
    collection = get_file_collection(client, knowledge_id)
    if collection is None:
        return []
    items, offset = [], 0
    while True:
        rows = collection.get(where={"file_id": file_id}, limit=100, offset=offset,
                              include=["documents", "metadatas", "embeddings"])
        for i, record_id in enumerate(rows["ids"]):
            items.append({"id": record_id, "content": rows["documents"][i] or "",
                          "metadata": rows["metadatas"][i] or {},
                          "embedding": rows["embeddings"][i].tolist()})
        if len(rows["ids"]) < 100:
            return items
        offset += 100
