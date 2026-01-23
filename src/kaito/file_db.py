# import glob
# import os
import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_file_hash_fast(filename, algorithm="md5"):
    """
    Computes the hash of a file using hashlib.file_digest (Python 3.11+).
    Use 'md5' or 'sha1' for potentially faster, but less secure, hashes.
    """
    try:
        with open(filename, "rb") as f:
            digest = hashlib.file_digest(f, algorithm)
        return digest.hexdigest()
    except FileNotFoundError:
        return "File not found"
    except ValueError as e:
        return f"Error: {e}"


class FileDB:
    def __init__(self, db_path: Path | None = None, client: OpenAI | None = None,) -> None:
        project_dir: Path = Path(__file__).parent.parent.parent.absolute()

        self.db_path = project_dir / "user_data"
        self._client = client
        self.db: dict = self._load_db()
        self.get_all_files_info()

    def _load_db(self) -> dict:
        with open( self.db_path / "files.json", "r") as f:
            file_info = json.load(f)
        
        return file_info
    
    def _save_db(self) -> None:
        with open(self.db_path / "files.json", "w") as f:
            json.dump(self.db, f, indent=2)

    def update_file_info(self, file_info: dict):
        self.db.update(file_info)
        self._save_db()

    def get_all_files_info(self):
        # Get the absolute path of the current file's directory        
        # Get all files in the current directory
        files_in_dir = list((self.db_path / "files").glob("*"))

        # TODO: replace with FMS API
        openai_files_dict = {}
        if self._client:
            openai_files_list = self._client.files.list(purpose="user_data", order="desc").model_dump()
            openai_files_dict = {f["id"]: f for f in openai_files_list["data"]}

        for filepath in files_in_dir:
            _hash = get_file_hash_fast(filepath)
            if _hash not in self.db:
                self.db.update({
                    _hash: {
                        "filename": filepath.name,
                        "filepath": filepath.as_posix(),
                        "bytes": filepath.stat().st_size,
                        "hash": _hash,
                        "id": None,
                        "purpose": "user_data",
                        "status": None
                    }
                })
                f_id = None
            else:
                f_id = self.db[_hash]["id"]

            
            if f_id in openai_files_dict:
                self.db.update({
                    _hash: {
                        **self.db[_hash],
                        **openai_files_dict[f_id]
                    }
                })

        self._save_db()

        return self.db

if __name__ == "__main__":
    from openai import OpenAI
    file_db = FileDB(client=OpenAI())
    print(file_db.db)