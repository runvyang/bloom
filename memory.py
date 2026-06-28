from mem0 import MemoryClient

memory = MemoryClient(api_key="m0-Kb4jX7zmjjDvYYxvdVTxvNGxyEB3aCTxRyuNnpkW")


class MemoryManager:
    def add(self, user_id, text):
        memory.add(text, user_id=user_id)

    def search(self, user_id, query, top_k=5):
        return memory.search(query, filters=dict(user_id=user_id), top_k=top_k)