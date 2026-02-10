from datetime import datetime
from typing import cast
from uuid import uuid4

from openai import AsyncOpenAI, OpenAI
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import (
    # Button,
    DataTable,
    Footer,
    Header,
    Markdown,
    # Pretty,
    # RadioButton,
    # RadioSet,
    # RichLog,
    Select,
    SelectionList,
    # Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from kaito.assets import BUILT_IN_TOOLS_INFO, MODEL_INFO_DATA
from kaito.engine import EventEngine
from kaito.types import FileInfo, SessionState


class BindedTextArea(TextArea):
    BINDINGS = TextArea.BINDINGS + [Binding("shift+enter", "submit", "Submit", show=True)]

    async def action_submit(self) -> None:
        """Undo the edits since the last checkpoint (the most recent batch of edits)."""
        # self.app.query_one(selector="#input-box", expect_type=TextArea).clear()
        _app = cast("MainApp", self.app)
        sess: SessionState = cast("SessionState", _app.sess)
        if not self.text.strip():
            _app.notify("Error: The text area cannot be empty.", severity="error")
            return

        model_name = _app.query_one("#model", Select).value
        model_effort = _app.query_one("#effort", Select).value

        model: dict = MODEL_INFO_DATA["models"][model_name]
        model.update({"effort": model_effort})

        sess.model_info = model

        sess.tools_selection = _app.query_one("#tool_selection_list", SelectionList).selected

        files_selection: list[str] = _app.query_one(f"#{_app.file_sel_id}", SelectionList).selected

        files_info: dict = _app.engine.list_files(location="local")
        files_selection_obj: list[FileInfo] = [files_info[f] for f in files_selection]

        for file_info in files_selection_obj:
            file_info: FileInfo = _app.engine.ensure_upload_file(file_info)

            if file_info.filetype == "image":
                sess.file_ids.image.update({file_info.id: file_info})
            elif file_info.filetype == "file":
                sess.file_ids.file.update({file_info.id: file_info})

        # info = f"Model: {model}; Effort: {model_effort}; Tools selection: {sess.tools_selection}"
        # sel = [v.model_dump() for v in files_selection_obj]
        # info += json.dumps(sel)
        # info += f"\nUser query: {self.text}"
        # info += f"\n\n{sess.model_dump_json(indent=2)}"
        # _app.query_one(Pretty).update(info)

        sess.user_query = self.text

        # _app.query_one(RichLog).write(Text(f"{self.text}\n", style="white"))
        markdown_delta = Markdown(classes="assistant-box")
        markdown_full = Markdown(classes="assistant-box")
        _app.query_one("#main-chat").mount(Markdown(self.text, classes="user-box"))
        self.clear()
        _app.query_one("#main-chat").mount(markdown_delta)
        table = _app.query_one(DataTable)

        full_content = ""
        _h = uuid4().hex[:4]
        stream = Markdown.get_stream(markdown_delta)

        async for chunk, status in _app.engine.astream(session=sess):
            table.add_row(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), _h, status)
            if isinstance(chunk, str):
                await stream.write(chunk)
                # markdown_delta.append(chunk)
                full_content += chunk
                # markdown_full.append(chunk)
            # elif chunk is None:
            #     break
            # else:
            #     print(chunk)
        stream.stop()
        markdown_delta.remove()
        _app.query_one("#main-chat").mount(markdown_full)
        markdown_full.append(full_content)


class MainApp(App):
    CSS_PATH = "textual.tcss"

    def __init__(self):
        super().__init__()

        self.file_sel_id = "f" + uuid4().hex[:4]
        self.title = "✨ Kaito ✨"
        self.engine = EventEngine(
            client=OpenAI(),
            async_client=AsyncOpenAI(),
            built_in_tools=BUILT_IN_TOOLS_INFO["buildin_tools"],
        )

        self.sess = SessionState()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            with VerticalScroll(id="left-pane"):
                yield Select(
                    options=[(k, k) for k, _ in MODEL_INFO_DATA["models"].items()],
                    type_to_search=True,
                    id="model",
                    prompt="Select Model",
                    allow_blank=False,
                )
                yield Select(
                    options=[(k, k) for k in MODEL_INFO_DATA["models"][MODEL_INFO_DATA["default"]]["available_reasoning_effort"]],
                    type_to_search=True,
                    id="effort",
                    prompt="Select Reasoning Effort",
                    allow_blank=False,
                )

                tools = BUILT_IN_TOOLS_INFO["buildin_tools"]
                tools_sel: list = [("File/Image Input", "File/Image Input", False)] + [(tool_name, tool_name, False) for tool_name in tools]
                yield SelectionList[int](*tools_sel, id="tool_selection_list")

                # yield SelectionList[str](
                #     *[(val.filename, _hash, False) for _hash, val in self.engine._file_engine.list_files().items()],
                #     id="local_files",
                #     name="Local Files",
                # )
                # yield Button(
                #     "Refresh Files List",
                #     id="refresh_files_list",
                # )
                # yield Pretty([])

            with Container(id="chat-container"):
                with TabbedContent(initial="chat-box"):
                    with TabPane("ChatBox", id="chat-box"):
                        with VerticalScroll(id="main-chat"):
                            ...
                            # yield RichLog()
                            # yield ImageViewer(Image.open(Path("./user_data/files/cat.jpg")))
                            # yield Static("\n".join([val.filepath for s, val in self.engine._file_engine.list_files().items()]))
                    with TabPane(title="LogBox", id="log-box"):
                        with VerticalScroll():
                            yield DataTable(id="logger-table")

            # with Container(id="bottom-pane"):
            with Horizontal(id="bottom-pane"):
                yield BindedTextArea(placeholder="Ask Me Anything!", id="input-box")

        yield Footer()

    # @on(Mount)
    # @on(SelectionList.SelectedChanged)
    # def update_selected_view(self) -> None:
    #     self.query_one(Pretty).update(self.query_one(SelectionList).selected)

    def on_mount(self) -> None:
        # self.title = "✨ Kaito ✨"
        file_sel_list = SelectionList[str](
            *[(val.filename, _hash, False) for _hash, val in self.engine._file_engine.list_files().items()],
            id=self.file_sel_id,
            name="Local Files",
            classes="file_sel_id",
        )
        self.query_one("#left-pane").mount(file_sel_list)
        self.query_one(f"#{self.file_sel_id}").border_title = "Files Selection"
        self.query_one(f"#{self.file_sel_id}").visible = False

        self.query_one("#input-box").focus()
        self.query_one("#tool_selection_list").border_title = "Tools Selection"

        table = self.query_one(DataTable)
        table.add_columns("Time", "Level", "Message")

    @on(Select.Changed, selector="#model")
    def select_model_changed(self, event: Select.Changed) -> None:
        self.query_one("#effort", expect_type=Select).set_options((e, e) for e in MODEL_INFO_DATA["models"][str(event.value)]["available_reasoning_effort"])

    # @on(Select.Changed, selector="#effort")
    # def select_effort_changed(self, event: Select.Changed) -> None:
    #     self.bell()

    @on(message_type=SelectionList.SelectedChanged, selector="#tool_selection_list")
    def handle_tool_selection(self, event: SelectionList.SelectedChanged) -> None:
        obj: SelectionList = self.query_one("#tool_selection_list", expect_type=SelectionList)
        if "File/Image Input" in obj.selected:
            self.query_one(f"#{self.file_sel_id}").visible = True
            # self.query_one("#refresh_files_list").visible = True
        else:
            self.query_one(f"#{self.file_sel_id}").remove()
            self.file_sel_id = "f" + uuid4().hex[:4]
            file_sel_list = SelectionList[str](
                *[(val.filename, _hash, False) for _hash, val in self.engine._file_engine.list_files().items()],
                id=self.file_sel_id,
                name="Local Files",
                classes="file_sel_id",
            )
            self.query_one("#left-pane").mount(file_sel_list)
            self.query_one(f"#{self.file_sel_id}").border_title = "Files Selection"
            self.query_one(f"#{self.file_sel_id}").visible = False

    # @on(message_type=SelectionList.SelectedChanged, selector="#local_files")
    # def handle_file_selection(self, event: SelectionList.SelectedChanged) -> None:
    #     self.bell()
    # self.query_one(Pretty).update(
    #     f"Selected Files: {self.query_one('#local_files', expect_type=SelectionList).selected}",
    # )
    # self.query_one(Pretty).update(f"Selected Files: {event.value}")

    # @on(message_type=Button.Pressed, selector="#refresh_files_list")
    # def on_button_pressed(self, event: Button.Pressed) -> None:
    #     files_info: dict = self.engine.list_files(location="local")
    #     files_selection: list[str] = self.query_one("#local_files", SelectionList).selected

    #     files_selection_obj: list[FileInfo] = [files_info[f] for f in files_selection]

    #     for file_info in files_selection_obj:
    #         file_info: FileInfo = self.engine.ensure_upload_file(file_info)

    # if file_info.filetype == "image":
    #     sess.file_ids.image.update({file_info.id: file_info})
    # elif file_info.filetype == "file":
    #     sess.file_ids.file.update({file_info.id: file_info})

    # self.query_one("#local_files").clear()
    # self.exit(str(event.button))

if __name__ == "__main__":
    app = MainApp()
    app.run()
