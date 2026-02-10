from typing import Any, Literal

from pydantic import BaseModel, Field

import kaito.openai_datatypes as R


class FileInfo(BaseModel):
    """Metadata for a local or uploaded file.

    Attributes:
        filename: File name without path.
        filepath: Absolute or relative path to the file.
        filetype: File type classification.
        bytes: File size in bytes.
        hash: Content hash used as a local identifier.
        id: Remote file ID when uploaded.
        purpose: OpenAI file purpose.
        status: Remote status, if available.
        created_at: Remote creation timestamp, if available.
        expires_at: Remote expiration timestamp, if available.
    """

    filename: str
    filepath: str
    filetype: Literal["file", "image", "not_identified"] = "not_identified"
    bytes: int
    hash: str
    id: str = ""
    purpose: str = "user_data"
    status: str | None = None
    created_at: int | None = None
    expires_at: int | None = None


class FileIDs(BaseModel):
    """File ID collections for different file types.

    Attributes:
        file: Mapping of file IDs to FileInfo for regular files.
        image: Mapping of file IDs to FileInfo for images.
    """

    file: dict[str, FileInfo] = {}
    image: dict[str, FileInfo] = {}


class SessionState(BaseModel):
    """Session state for the CLI interaction loop."""

    tools_default: tuple[str, ...] = Field(
        default_factory=lambda: ("web_search",),
        description="*Immutable* default tool identifiers to preselect.",
        frozen=True,
    )
    model_info: dict = Field(
        default_factory=dict,
        description="Selected model configuration.",
    )
    user_query: str = Field(default="", description="Most recent user input or command.")
    
    tools_selection: list[str] = Field(
        default_factory=list,
        description="Currently selected tool identifiers.",
    )
    file_ids: FileIDs = Field(
        default_factory=FileIDs,
        description="Uploaded file tracking structure.",
    )
    vector_store_ids: list[str] = Field(
        default_factory=list,
        description="Vector store identifiers for file search.",
    )
    full_history: list[R.ResponseOutputItem | R.EasyInputMessage] = Field(
        default_factory=list,
        description="Full response history for the session.",
    )
    compact_history: list[R.ResponseOutputItem | R.EasyInputMessage] = Field(
        default_factory=list,
        description="Compacted response history for the session.",
    )
    usage: R.ResponseUsage | None = Field(
        default=None,
        description="Usage records accumulated during the session.",
    )
    current_output: list[Any] | None = Field(
        default=None,
        description="Most recent response output items, if available.",
    )
