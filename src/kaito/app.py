import os

# from loguru import logger
from openai import AsyncOpenAI, OpenAI
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from .assets import BUILT_IN_TOOLS_INFO
from .engine import EventEngine
from .types import SessionState
from .ui import get_model_info, get_selected_tools, get_uploaded_files, get_user_query


async def _ensure_model_info(
    session: SessionState,
    console: Console,
) -> bool:
    """Ensure the session has model info, prompting the user if needed.

    Args:
        session: Current SessionState to update.
        console: Rich console for UI output.

    Returns:
        None.
    """
    if not session.model_info or session.user_query == "/model":
        # layout["lower"].update("WTF")
        # layout.refresh_screen(console, "lower")
        # layout["lower"].update("[bold italic red]Model Info")
        # with console.screen():
        console.rule("[bold italic red]Model Info")
        session.model_info = await get_model_info()
        return True
    return False


async def _ensure_tools_selection(session: SessionState, console: Console) -> bool:
    """Ensure tool selection is set, optionally rerouting to model selection.

    Args:
        session: Current SessionState to update.
        console: Rich console for UI output.

    Returns:
        True if the caller should restart the main loop, otherwise False.
    """
    if not session.tools_selection or session.user_query == "/tool":
        console.rule("[bold italic red]Tools Info")
        session.tools_selection = await get_selected_tools(session=session)

        if "/back" in session.tools_selection:
            session.tools_selection = []
            session.user_query = "/model"
            return True
    return False


async def _handle_file_inputs(engine: EventEngine, session: SessionState, console: Console) -> bool:
    """Handle optional file uploads for the current session.

    Args:
        session: Current SessionState to update.
        engine: EventEngine used to query and upload files.
        console: Rich console for UI output.

    Returns:
        True if the caller should restart the main loop, otherwise False.
    """
    if "file_input" not in session.tools_selection and session.user_query != "/file":
        return False

    console.rule("[bold italic red]File Info")
    files_info: dict = engine.list_files(location="local")

    files_selection = await get_uploaded_files(
        files_info=files_info,
        session=session,
    )
    if "/back" in files_selection:
        session.user_query = "/tool"
        return True

    for file_info in files_selection:
        if file_info.id:
            console.print(f"⚠️ Uploading skipped: File [italic blue]{file_info.filename}[/] existed in OpenAI Files.")
        else:
            console.print(f"✅ Uploading file: [italic blue]{file_info.filename}[/]...")
            file_info = engine.ensure_upload_file(file_info)

        if file_info.filetype == "image":
            session.file_ids.image.update({file_info.id: file_info})
        elif file_info.filetype == "file":
            session.file_ids.file.update({file_info.id: file_info})

    return False


def _save_history(session: SessionState, file_path: str, console: Console) -> None:
    """Persist the full conversation history to disk.

    Args:
        session: Current SessionState containing the full history.
        file_path: Destination path for the JSON output.
        console: Rich console for UI output.

    Returns:
        None.
    """
    import json

    with open(file_path, "w") as file:
        json_line = json.dumps([ele.model_dump() for ele in session.full_history], indent=2)
        file.write(json_line + "\n")
    console.rule(f"[bold green]Saving Dialog to {file_path}")


def _handle_command(session: SessionState, console: Console) -> str | None:
    """Handle slash commands and return a control action, if any.

    Args:
        session: Current SessionState to update.
        engine: EventEngine used for history operations.
        console: Rich console for UI output.

    Returns:
        "continue" to skip response generation, "new" to reset session,
        or None when input is not a command.
    """
    if not session.user_query.startswith("/"):
        return None

    if session.user_query in {"/tool", "/model", "/file"}:
        return "continue"
    if session.user_query == "/back":
        session.user_query = "/tool"
        return "continue"
    if session.user_query == "/new":
        session = SessionState()
        console.rule("[bold green]New Chat Started")
        return "new"
    if session.user_query == "/save":
        _save_history(session=session, file_path="tests/xxx.json", console=console)
        return "continue"

    raise ValueError("Unknown command")


async def _render_response(engine: EventEngine, session: SessionState, console: Console) -> None:
    """Render a streaming assistant response to the console.

    Args:
        engine: EventEngine used to create and stream responses.
        session: Current SessionState for request context.
        console: Rich console for UI output.

    Returns:
        None.
    """
    console.rule("[bold blue]Assistant")
    full_markdown: str = ""
    with Live(
        Markdown(full_markdown, justify="full"),
        console=console,
        screen=False,
        vertical_overflow="visible",
        refresh_per_second=10,
    ) as live:
        async for chunk, status in engine.astream(session=session):
            if chunk:
                full_markdown += chunk
                live.update(Markdown(full_markdown))


async def run():
    """Run the interactive CLI session loop."""
    os.system("clear||cls")
    console = Console()
    console.rule("[bold green] ✨ Kaito ✨ ")

    try:
        engine = EventEngine(
            client=OpenAI(),
            async_client=AsyncOpenAI(),
            built_in_tools=BUILT_IN_TOOLS_INFO["buildin_tools"],
        )

        session = SessionState()
        while True:
            if not session.user_query or session.user_query in {"/tool", "/model", "/file"}:
                with console.screen():
                    await _ensure_model_info(session=session, console=console)
                    
                    if await _ensure_tools_selection(session=session, console=console):
                        continue

                    if await _handle_file_inputs(engine=engine, session=session, console=console):
                        continue

            console.rule("[bold italic green]User")
            session.user_query = await get_user_query()
            console.print(Markdown(session.user_query), style="green")

            command_action = _handle_command(session=session, console=console)
            if command_action == "continue":
                continue
            if command_action == "new":
                session = SessionState()
                continue

            await _render_response(engine=engine, session=session, console=console)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting...")
