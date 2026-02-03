from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from .assets import MODEL_INFO_DATA
from .types import FileInfo, SessionState


def get_uploaded_files(
    files_info: dict[str, FileInfo],
    session: SessionState,
) -> list[FileInfo]:
    """Return selected file infos (or empty list) based on current tool selection.

    Args:
        files_info: Mapping of file IDs to FileInfo objects.
        session: Current SessionState used for tool selection.

    Returns:
        List of selected FileInfo objects; empty when file input is not selected.
        The list can include a "/back" sentinel when chosen in the UI.
    """
    if "file_input" in session.tools_selection:
        files_choices = [Choice(name=f"{info.filename}", value=info) for info in files_info.values()] + [
            Choice(name="<< Back", value="/back", enabled=False),
        ]

        _files_selection: list[FileInfo] = inquirer.checkbox(  # type: ignore
            message="Select the files/images as Inputs:",
            choices=files_choices,
            validate=lambda x: len(x) >= 1,
            invalid_message="Select at least 1 file.",
        ).execute()

        return _files_selection
    return []


def get_model_info() -> dict:
    """Prompt for model choice and reasoning effort, returning the merged config.

    Returns:
        Dictionary with the selected model config plus an "effort" key.
    """
    _model_info: dict = inquirer.select(  # type: ignore
        message="Select Openai model:",
        qmark="",
        amark="",
        choices=[Choice(name=k, value=v) for k, v in MODEL_INFO_DATA["models"].items()],
        default=MODEL_INFO_DATA["models"][MODEL_INFO_DATA["default"]],
        # transformer=lambda _: "",
    ).execute()
    _model_effort = inquirer.select(  # type: ignore
        message="Select model reasoning effort:",
        qmark="",
        amark="",
        choices=[Choice(name=value, value=value) for value in _model_info["available_reasoning_effort"]],
        default=_model_info["default_reasoning_effort"],
        # transformer=lambda _: "",
    ).execute()

    _model_info.update({"effort": _model_effort})
    return _model_info


def get_selected_tools(session: SessionState):
    """Prompt for tool selections, honoring defaults from the session.

    Args:
        session: Current SessionState used to populate default selections.

    Returns:
        List of selected tool identifiers.
    """
    _tools_selection = inquirer.checkbox(  # type: ignore
        message="Select tools:",
        qmark="",
        amark="",
        choices=[
            Choice(name="File/Image Input", value="file_input", enabled=bool("file_input" in session.tools_default)),
            Choice(name="Web Search", value="web_search", enabled=bool("web_search" in session.tools_default)),
            ###
            Choice(name="Code Interpreter", value="code_interpreter", enabled=bool("code_interpreter" in session.tools_selection)),
            Choice(name="<< Back to Model Selection", value="/back", enabled=False),
            ###
            # Choice(name="File Semantic Search", value="file_search", enabled=bool("file_search" in tools_default)),
        ],
        cycle=False,
        validate=lambda x: len(x) >= 0,
        transformer=lambda x: ", ".join(x) if x and "<< Back to Model Selection" not in x else "No tool selected",
    ).execute()

    return _tools_selection


def get_user_query():
    """Prompt the user for a query or command string.

    Returns:
        Trimmed user input string (may be a command like "/tool").
    """
    _user_query: str = inquirer.text(  # type: ignore
        message="",
        instruction="Ask anything:",
        qmark="",
        amark="",
        # default="",
        validate=lambda x: len(x) > 1,
        completer={"/back": None, "/tool": None, "/model": None, "/file": None, "/new": None, "/save": None},
        transformer=lambda _: "",
    ).execute()
    return _user_query.strip()
