from typing import TYPE_CHECKING

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from loguru import logger

from .types import FileIDs

if TYPE_CHECKING:
    from .engine import EventEngine


def sync_uploaded_files(
    engine: "EventEngine",
    tools_selection: list[str],
) -> tuple[FileIDs, str]:
    """Collect file selections and ensure uploads are complete.

    Args:
        engine: EventEngine used to query and upload files.
        tools_selection: Current list of selected tool identifiers.

    Returns:
        Tuple of FileIDs and a status string ("/back" when the user navigates back).
    """
    file_ids: FileIDs = FileIDs()

    if "file_input" in tools_selection:
        files_info = engine.list_files()
        files_choices = [
            Choice(name=f"{info.filename}", value=info)
            for info in files_info.values()  # if info['id'] is not None
        ] + [Choice(name="<< Back", value="/back", enabled=False)]

        files_selection = inquirer.checkbox(
            message="Select the files/images as Inputs:",
            choices=files_choices,
            cycle=False,
            validate=lambda x: len(x) >= 1,
            invalid_message="Select at least 1 file.",
        ).execute()
        if "/back" in files_selection:
            return file_ids, "/back"

        for file_info in files_selection:
            if file_info.id:
                logger.info(f"Skipped uploading: File '{file_info.filename}' existed in OpenAI Files.")
            else:
                logger.info(f"Uploading file: {file_info.filename}...")
                file_info = engine.ensure_upload_file(file_info)

            if file_info.filetype == "image":
                file_ids.image.update({file_info.id: file_info})
            elif file_info.filetype == "file":
                file_ids.file.update({file_info.id: file_info})

    return file_ids, ""


# def sync_vector_store_files_bakup(
#     engine: "EventEngine",
#     tools_selection: list[str],
# ) -> tuple[list[str], list[str]]:
#     vector_store_ids: list[str] = []
#     file_ids: list[str] = []

#     if "file_input" in tools_selection or "file_search" in tools_selection:
#         files_info = engine._file_info_db.list_local_files()
#         files_choices = [
#             Choice(name=f"{info.filename}", value=info)
#             for info in files_info.values()  # if info['id'] is not None
#         ]
#         # [
#         #     Choice(name="Back", value={})
#         # ]
#         files_selection = inquirer.checkbox(
#             message="Select the files/images as Inputs:",
#             choices=files_choices,
#             cycle=False,
#             validate=lambda x: len(x) >= 1,
#             invalid_message="Select at least 1 file.",
#         ).execute()

#         vs_files_ids = []
#         vs_id: str = ""  # TODO: better logic

#         if "file_search" in tools_selection:
#             logger.debug("Getting/creating vector store for file search...")
#             vs = engine._vs.get_or_create(expires_after={"anchor": "created_at", "days": 86400 * 7})
#             vs_id = vs.id
#             vs_files_ids = [file.id for file in engine._vs_files.list(vector_store_id=vs_id).data]
#             vector_store_ids = [vs_id]

#         for file_info in files_selection:
#             if file_info["id"]:
#                 logger.info(f"Skipped uploading: File '{file_info['filename']}' existed in OpenAI Files.")
#             else:
#                 logger.info(f"Uploading file: {file_info['filename']}...")
#                 file_info = engine._file_info_db.upload_file(file_info)

#             if "file_search" in tools_selection:
#                 if file_info.id not in vs_files_ids:
#                     logger.info(f"Creating vector store file for '{file_info.filename}'...")
#                     _ = engine._vs_files.create_and_poll(file_id=file_info.id, vector_store_id=vs_id)  # TODO: status check

#                 logger.info(f"File {file_info.filename}-{file_info.id} is ready in Vector Store {vs_id}.")

#             file_ids.append(file_info.id)

#     # def _check_ready():
#     #     all([check_all_files_ready(engine, vs_id) for vs_id in vector_store_ids])
#     # if vector_store_ids:
#     #     _ = inquirer.select(
#     #         message="Check if vector store is ready...",
#     #         choices=[
#     #             Choice(name="Check Readiness", value="Ready!"),
#     #         ],
#     #         default="Ready!",
#     #         validate=_check_ready(),
#     #         invalid_message="Vector store is not ready yet.",
#     #     ).execute()

#     return vector_store_ids, file_ids


# def check_all_files_ready(engine: "EventEngine", vs_id: str) -> bool:
#     vector_store = engine._vs.retrieve(vs_id)
#     return vector_store.status == "completed"
