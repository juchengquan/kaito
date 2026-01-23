from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from .engine import EventEngine


def sync_vector_store_files(
    engine: EventEngine,
    tools_selection: list[str],
) -> list[str]:
    vector_store_ids: list[str] = []
    if "file_search" in tools_selection:
        files_info = engine._file_db.get_all_files_info()
        files_choices = [
            Choice(name=f"{info['filename']}", value=info)
            for info in files_info.values()
            # if info['id'] is not None
        ]
        files_selection = inquirer.checkbox(  # type: ignore
            message="Select the files to use for File Search tool:",
            choices=files_choices,
            cycle=False,
            validate=lambda x: len(x) >= 1,
            invalid_message="Select at least 1 file.",
        ).execute()

        vs = engine._vec.get_or_create_vector_store()
        vs_files = engine._vec.list_vector_store_files(vs.id)
        vs_files_ids = [file.id for file in vs_files.data]

        for file_info in files_selection:
            if file_info["id"]:
                print(f"File '{file_info['filename']}' existed in OpenAI Files. Skipped uploading")
            else:
                print(f"Uploading file: {file_info['filename']}...")

                with open(file_info["filepath"], "rb") as file_content:
                    file_info_uploaded = engine._client.files.create(file=(file_info["filename"], file_content), purpose="user_data")
                file_info = {
                    **file_info,
                    **file_info_uploaded.model_dump(),
                }
                engine._file_db.update_file_info({file_info["hash"]: file_info})
            if file_info["id"] not in vs_files_ids:
                print(f"Creating vector store file for '{file_info['filename']}'...")
                _ = engine._vec.create_vector_store_file(vs.id, file_info["id"])  # type: ignore
                # print(vs_file)
        vector_store_ids = [vs.id]

    def _check_ready():
        all([check_all_files_ready(engine, vs_id) for vs_id in vector_store_ids])
        
    if vector_store_ids:
        _ = inquirer.select(  # type: ignore
            message="Check if vector store is ready...",
            choices=[
                Choice(name="Check Readiness", value="Ready!"),
            ],
            default="Ready!",
            validate=_check_ready(),
            invalid_message="Vector store is not ready yet.",
        ).execute()

    return vector_store_ids


def check_all_files_ready(engine: EventEngine, vs_id: str) -> bool:
    vector_store = engine._vec.retrieve_vector_store(vs_id)
    return vector_store.status == "completed"
