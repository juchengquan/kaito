# import glob
import hashlib
import json
import os
from pathlib import Path

from openai import OpenAI
from pydantic import TypeAdapter

from .types import FileInfo

# from .vector_store import KaitoVectorStoreFiles

DBFileInfo = TypeAdapter(dict[str, FileInfo])


def _get_file_hash_fast(filename, algorithm="md5"):
    """
    Computes the hash of a file using hashlib.file_digest (Python 3.11+).
    Use 'md5' or 'sha1' for potentially faster, but less secure, hashes.

    Args:
        filename: Path to the file to hash.
        algorithm: Hash algorithm name (e.g., "md5" or "sha1").

    Returns:
        Hex digest string or an error message string.
    """
    try:
        with open(filename, "rb") as f:
            digest = hashlib.file_digest(f, algorithm)
        return digest.hexdigest()
    except FileNotFoundError:
        return "File not found"
    except ValueError as e:
        return f"Error: {e}"


class LocalFileEngine:
    """Manage local file metadata and uploads to OpenAI."""

    def __init__(
        self,
        client: OpenAI,
        db_path: Path | None = None,
        # vector_store_engine: KaitoVectorStoreFiles | None = None,
    ) -> None:
        """Initialize the file engine and load the local DB.

        Args:
            client: OpenAI client instance.
            db_path: Optional path to the local file DB directory.
        """
        if db_path:
            self.db_path = db_path
        else:
            db_path_env = os.getenv("FILE_DB_PATH", "").strip()
            db_path = Path(db_path_env) if db_path_env else None
            self.db_path = db_path / "user_data" if db_path else Path(__file__).parent.parent.parent.absolute() / "user_data"
        self._client = client
        # self._vs_files = vector_store_engine
        self.db: dict[str, FileInfo] = self._load_db()
        self.list_files()

    def ensure_upload_file(self, file_info: FileInfo) -> FileInfo:
        """Upload the file if needed and return the updated FileInfo.

        Args:
            file_info: FileInfo record to ensure is uploaded.

        Returns:
            Updated FileInfo with upload metadata populated.
        """
        if file_info.id:
            return file_info
        return self._upload_file(file_info)

    def list_files(self) -> dict[str, FileInfo]:
        """Sync local files with OpenAI metadata and return the DB.

        Returns:
            Mapping of file hashes to FileInfo objects.
        """
        # Get the absolute path of the current file's directory
        # Get all files in the current directory
        files_in_dir = list((self.db_path / "files").glob("*"))

        # TODO: replace with FMS API
        openai_files_list: dict = self._client.files.list(purpose="user_data", order="desc").model_dump()
        openai_files_dict: dict = {f["id"]: f for f in openai_files_list["data"]}

        for filepath in files_in_dir:
            _hash = _get_file_hash_fast(filepath)
            _static_dt: FileInfo = FileInfo(
                filename=filepath.name,
                filepath=filepath.as_posix(),
                filetype="image" if filepath.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".gif"] else "file",
                bytes=filepath.stat().st_size,
                hash=_hash,
                purpose="user_data",
            )
            if _hash not in self.db:
                self.db[_hash] = _static_dt
                f_id = None
            else:
                f_id = self.db[_hash].id

            if not f_id:
                continue
            # Otherwise, update
            if f_id in openai_files_dict:
                self.db[_hash] = self.db[_hash].model_copy(
                    update={
                        **openai_files_dict[f_id],
                    }
                )
            else:  # File is no longer in OpenAI
                self.db[_hash] = FileInfo(
                    **self.db[_hash].model_dump(),
                )
        self._save_db()

        return self.db

    def _load_db(self) -> dict[str, FileInfo]:
        """Load file metadata from the local JSON database.

        Returns:
            Mapping of file hashes to FileInfo objects.
        """
        with open(self.db_path / "files.json", "r") as f:
            file_info = json.load(f)

        return {k: FileInfo(**v) for k, v in file_info.items()}

    def _save_db(self) -> None:
        """Persist the in-memory DB to disk.

        Returns:
            None.
        """
        with open(self.db_path / "files.json", "w") as f:
            f.write(DBFileInfo.dump_json(self.db, indent=2).decode())

    def _upload_file(self, file_info: FileInfo) -> FileInfo:
        """Upload a local file to OpenAI and update the DB.

        Args:
            file_info: FileInfo record describing the local file.

        Returns:
            Updated FileInfo with upload metadata populated.
        """
        with open(file_info.filepath, "rb") as file_content:
            file_info_uploaded = self._client.files.create(
                file=(file_info.filename, file_content),
                purpose="user_data",
                expires_after={"anchor": "created_at", "seconds": 86400 * 3},  # TODO: expire after 3 days
            )
            updated_file_info: FileInfo = file_info.model_copy(
                update={
                    **file_info_uploaded.model_dump(),
                }
            )
            self._update_file_info({updated_file_info.hash: updated_file_info})

        return updated_file_info

    def _update_file_info(self, file_info: dict[str, FileInfo]):
        """Update the DB with new file metadata and persist it.

        Args:
            file_info: Mapping of file hashes to FileInfo objects.

        Returns:
            None.
        """
        self.db.update(file_info)
        self._save_db()
