from dotenv import load_dotenv
from openai import OpenAI

#
load_dotenv()


class VectorStoreEngine:
    def __init__(self, client: OpenAI):
        self._client = client

    def get_or_create_vector_store(self):
        vector_stores = self._client.vector_stores.list(order="desc")
        # TODO: just get the latest one
        if vector_stores.data:
            vs_id = vector_stores.data[0].id
            vector_store = self._client.vector_stores.retrieve(vector_store_id=vs_id)
            print(f"Found vector store: {vector_store.id}")
        else:
            print("No vector stores found.")
            # create a new one
            vector_store = self._client.vector_stores.create()

        return vector_store

    def retrieve_vector_store(self, vs_id: str):
        vector_store = self._client.vector_stores.retrieve(vector_store_id=vs_id)
        return vector_store

    def list_vector_store_files(self, vs_id: str):
        vector_store_files = self._client.vector_stores.files.list(vector_store_id=vs_id)
        return vector_store_files

    def create_vector_store_file(
        self,
        vs_id: str,
        file_id: str,
        attributes: dict = {},
    ):
        vs_file = self._client.vector_stores.files.create(
            vector_store_id=vs_id,
            file_id=file_id,
            attributes=attributes,
        )
        return vs_file

    def delete_vector_store_file(self):
        raise NotImplementedError


if __name__ == "__main__":
    from kaito.file_db import FileDB

    client = OpenAI()
    file_db = FileDB(client=client)

    print(file_db.db)

    vs_engine = VectorStoreEngine(client)

    vs = vs_engine.get_or_create_vector_store()
    files = vs_engine.list_vector_store_files(vs.id)

    for file in files.data:
        print(file.id)
