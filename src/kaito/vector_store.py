from typing import Literal, Optional

import httpx
from loguru import logger
from openai import OpenAI
from openai._types import Body, Headers, NotGiven, Omit, Query, SequenceNotStr, not_given, omit
from openai.pagination import SyncCursorPage

# from openai.pagination import AsyncCursorPage, AsyncPage, SyncPage
# from openai.resources.files import Files as OpenAIFiles
from openai.resources.vector_stores import (
    Files as OpenAIVecStoreFiles,
    VectorStores as OpenAIVectorStores,
)
from openai.types import FileChunkingStrategyParam, vector_store_create_params
from openai.types.shared_params.metadata import Metadata
from openai.types.vector_store import VectorStore
from openai.types.vector_stores.vector_store_file import VectorStoreFile


class KaitoVectorStoreFiles(OpenAIVecStoreFiles):
    """Extended vector store file operations with full pagination."""

    def list_all(
        self,
        vector_store_id: str,
        *,
        filter: Literal["in_progress", "completed", "failed", "cancelled"] | Omit = omit,
        # order: Literal["asc", "desc"] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncCursorPage[VectorStoreFile]:
        """List all files in a vector store with pagination handled internally.

        Args:
            vector_store_id: Vector store identifier.
            filter: Optional filter for file status.
            extra_headers: Optional HTTP headers.
            extra_query: Optional query parameters.
            extra_body: Optional request body overrides.
            timeout: Optional request timeout.

        Returns:
            A SyncCursorPage containing all VectorStoreFile entries.
        """
        files: list[VectorStoreFile] = []
        has_more = True
        last_id: str = ""
        while has_more:
            _payload: dict = {
                "vector_store_id": vector_store_id,
                "filter": filter,
                "order": "desc",
                "extra_headers": extra_headers,
                "extra_query": extra_query,
                "extra_body": extra_body,
                "timeout": timeout,
            }
            if last_id:
                _payload.update({"after": last_id})
            res = self.list(**_payload)
            files.extend(res.data)
            last_id = res.last_id  # type: ignore
            has_more = res.has_more
        return SyncCursorPage(data=files, has_more=False)


class KaitoVectorStores(OpenAIVectorStores):
    """Extended vector store operations with convenience helpers."""

    def get_or_create(
        self,
        *,
        chunking_strategy: FileChunkingStrategyParam | Omit = omit,
        description: str | Omit = omit,
        expires_after: vector_store_create_params.ExpiresAfter | Omit = omit,
        file_ids: SequenceNotStr[str] | Omit = omit,
        metadata: Optional[Metadata] | Omit = omit,
        name: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> VectorStore:
        """Return the most recent vector store or create a new one.

        Args:
            chunking_strategy: Optional chunking strategy for file ingestion.
            description: Optional description for the vector store.
            expires_after: Optional expiration policy.
            file_ids: Optional initial file IDs.
            metadata: Optional metadata for the vector store.
            name: Optional name for the vector store.
            extra_headers: Optional HTTP headers.
            extra_query: Optional query parameters.
            extra_body: Optional request body overrides.
            timeout: Optional request timeout.

        Returns:
            An existing VectorStore if present, otherwise a newly created one.
        """
        vector_stores = self.list_all()

        # TODO: just get the latest one
        if vector_stores.data:
            vs_id = vector_stores.data[0].id
            logger.debug(f"Found vector store: {vs_id}")
            return self.retrieve(vector_store_id=vs_id)
        else:
            logger.debug("No vector stores found.")
            # create a new one
            return self._client.vector_stores.create(
                chunking_strategy=chunking_strategy,
                description=description,
                expires_after=expires_after,
                file_ids=file_ids,
                metadata=metadata,
                name=name,
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
            )

    def list_all(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SyncCursorPage[VectorStore]:
        """List all vector stores with pagination handled internally.

        Args:
            extra_headers: Optional HTTP headers.
            extra_query: Optional query parameters.
            extra_body: Optional request body overrides.
            timeout: Optional request timeout.

        Returns:
            A SyncCursorPage containing all VectorStore entries.
        """
        vector_stores: list[VectorStore] = []
        has_more = True
        last_id: str = ""
        while has_more:
            _payload: dict = {
                "order": "desc",
                "extra_headers": extra_headers,
                "extra_query": extra_query,
                "extra_body": extra_body,
                "timeout": timeout,
            }
            if last_id:
                _payload.update({"after": last_id})
            res = self.list(**_payload)
            vector_stores.extend(res.data)
            last_id = res.last_id  # type: ignore
            has_more = res.has_more
        return SyncCursorPage(data=vector_stores, has_more=False)


if __name__ == "__main__":
    client = OpenAI()
    vs_engine = KaitoVectorStoreFiles(client)
