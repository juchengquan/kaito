import json
import os
import time
from pathlib import Path
from typing import Generator, cast

from loguru import logger
from openai import OpenAI

import kaito.openai_datatypes as R

# from .vector_store import # KaitoVectorStoreFiles, KaitoVectorStores
from .local_file_engine import LocalFileEngine
from .prompts import system_prompt
from .types import FileInfo, SessionState

MAX_TOOL_CALLS: int = int(os.getenv("MAX_TOOL_CALLS", default=5))
WRITE_TO_FILE: bool = os.getenv("WRITE_TO_FILE", default="FALSE").lower() in ("true", "1")


def print_class(event):
    """Log the event type when it is not a text delta.

    Args:
        event: Stream event to inspect.

    Returns:
        None.
    """
    if not isinstance(event, R.ResponseTextDeltaEvent):
        logger.info(type(event))


class EventEngine:
    """Coordinate responses, tool calls, and conversation history for the CLI app."""

    def __init__(
        self,
        client: OpenAI,
        built_in_tools: dict[str, dict],
        db_path: Path | None = None,
    ):
        """Engine as interface with an OpenAI client, File Engine and tools registy.

        Args:
            client: OpenAI client instance.
            built_in_tools: Registry of tool definitions by name.
            history: Optional initial history to seed the session.
            db_path: Optional path to the local file DB directory.
        """
        self._client = client
        self._file_engine = LocalFileEngine(client=client, db_path=db_path)
        self._built_in_tools: dict[str, dict] = built_in_tools

        # self._vs = KaitoVectorStores(client=client)
        # self._vs_files = KaitoVectorStoreFiles(client=client)

    def stream(
        self,
        session: SessionState,
    ) -> Generator[str]:
        """Yield incremental text deltas while updating internal history and usage.

        Args:
            session: Current SessionState to update.

        Yields:
            Text deltas emitted by the model as they arrive.
        """
        stream: list[R.ResponseStreamEvent] = self._create_response_stream(session=session)

        output_index = -1
        t_s = time.time()

        for _, event in enumerate(stream):
            match type(event):
                case R.ResponseCreatedEvent | R.ResponseInProgressEvent:
                    ...
                    # TODO
                    # print_class(event)

                case R.ResponseFailedEvent | R.ResponseIncompleteEvent:
                    ...
                    # TODO
                    # print_class(event)

                case R.ResponseCompletedEvent:
                    event = cast(R.ResponseCompletedEvent, event)
                    _output = event.response.output
                    session.current_output = _output
                    session.usage = event.response.usage
                    session.full_history += _output
                    session.compact_history += _output

                # status (main) - Output Item
                case R.ResponseOutputItemAddedEvent | R.ResponseOutputItemDoneEvent:
                    event = cast(R.ResponseOutputItemAddedEvent | R.ResponseOutputItemDoneEvent, event)
                    if output_index != event.output_index:
                        output_index += 1
                    assert output_index == event.output_index, f"output_index does not align - count:{output_index}|event:{event.output_index}"

                    match event.item.type:
                        case "message" | "reasoning" | "web_search_call" | "code_interpreter_call" | "file_search_call":
                            _item = cast(
                                R.ResponseOutputMessage
                                | R.ResponseReasoningItem
                                | R.ResponseFunctionWebSearch
                                | R.ResponseCodeInterpreterToolCall
                                | R.ResponseFileSearchToolCall,  # noqa: E501
                                event.item,
                            )
                            _status_type = event.type.split(".")
                            logger.debug(f"{time.time() - t_s:.2f} | @{_status_type[2]} | {event.item.type}: {_item.status}")

                # File Search
                # status - file search
                case R.ResponseFileSearchCallInProgressEvent | R.ResponseFileSearchCallSearchingEvent | R.ResponseFileSearchCallCompletedEvent:
                    event = cast(
                        R.ResponseFileSearchCallInProgressEvent | R.ResponseFileSearchCallSearchingEvent | R.ResponseFileSearchCallCompletedEvent,
                        event,
                    )
                    _status_type = event.type.split(".")
                    logger.debug(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")

                # Code Interpreter
                ## status - code interpreter
                case (
                    R.ResponseCodeInterpreterCallInProgressEvent | R.ResponseCodeInterpreterCallInterpretingEvent | R.ResponseCodeInterpreterCallCompletedEvent
                ):
                    event = cast(
                        R.ResponseCodeInterpreterCallInProgressEvent
                        | R.ResponseCodeInterpreterCallInterpretingEvent
                        | R.ResponseCodeInterpreterCallCompletedEvent,
                        event,
                    )
                    _status_type = event.type.split(".")
                    logger.debug(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")
                ## status - code interpreter
                case R.ResponseCodeInterpreterCallCodeDoneEvent:
                    event = cast(R.ResponseCodeInterpreterCallCodeDoneEvent, event)
                    _status_type = event.type.split(".")
                    logger.debug(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")
                ## content - code interpreter
                case R.ResponseCodeInterpreterCallCodeDeltaEvent:
                    event = cast(R.ResponseCodeInterpreterCallCodeDeltaEvent, event)
                    # TODO

                # Web Search
                ## status - web search
                case R.ResponseWebSearchCallInProgressEvent | R.ResponseWebSearchCallSearchingEvent | R.ResponseWebSearchCallCompletedEvent:
                    event = cast(
                        R.ResponseWebSearchCallInProgressEvent | R.ResponseWebSearchCallSearchingEvent | R.ResponseWebSearchCallCompletedEvent,
                        event,
                    )
                    _status_type = event.type.split(".")
                    logger.debug(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")

                # Text Output
                # status - text
                case R.ResponseTextDoneEvent:
                    event = cast(R.ResponseTextDoneEvent, event)
                    _status_type = event.type.split(".")
                    # FIXME
                    logger.debug(f"\n{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")
                # status - **text** content_part - Emitted when a new output item is added
                case R.ResponseContentPartAddedEvent | R.ResponseContentPartDoneEvent:
                    event = cast(R.ResponseContentPartAddedEvent | R.ResponseContentPartDoneEvent, event)
                    _status_type = event.type.split(".")
                    logger.debug(f"{time.time() - t_s:.2f} | @{_status_type[2]} | {event.part.type}: {_status_type[1]}")
                # output - text
                case R.ResponseTextDeltaEvent:
                    event = cast(R.ResponseTextDeltaEvent, event)
                    # print(event.delta, end="")
                    yield event.delta
                # output - annotation
                case R.ResponseOutputTextAnnotationAddedEvent:
                    event = cast(R.ResponseOutputTextAnnotationAddedEvent, event)
                    R.Annotation
                    annotation = cast(dict, event.annotation)
                    match annotation.get("type", None):
                        case "url_citation":
                            url_citation = R.AnnotationURLCitation(**annotation)  # noqa: F841
                        case "file_citation":
                            file_citation = R.AnnotationFileCitation(**annotation)  # noqa: F841
                        case "container_file_citation":
                            container_file_citation = R.AnnotationContainerFileCitation(**annotation)  # noqa: F841
                        case "file_path":
                            file_path = R.AnnotationFilePath(**annotation)  # noqa: F841

                case _:
                    print_class(event)

            if WRITE_TO_FILE:
                with open(f"tests/streaming_results_{int(t_s)}.json", "a") as file:
                    json_line = json.dumps(event.model_dump(), indent=2)
                    file.write(json_line + "\n")

        self._try_compact(session=session)

    def list_files(self, location: str = "local") -> dict[str, FileInfo]:
        """Return metadata for local files tracked in the file DB.

        Returns:
            Mapping of file hashes to FileInfo objects.
        """
        if location == "local":
            return self._file_engine.list_files()
        raise NotImplementedError("NotImplementedError: Only local files are supported at this time.")

    def ensure_upload_file(self, file_info: FileInfo) -> FileInfo:
        """Upload the file if needed and return the updated FileInfo.

        Args:
            file_info: FileInfo record to ensure is uploaded.

        Returns:
            Updated FileInfo with upload metadata populated.
        """
        return self._file_engine.ensure_upload_file(file_info)

    def _try_compact(self, session: SessionState):
        """Compact the conversation history if total token usage exceeds the threshold."""
        _threshold = int(os.environ.get("COMPACT_TOKENS_THRESHOLD", 180000))

        if session.usage:
            logger.debug(f"Total Tokens Used: {session.usage.total_tokens}")

            if session.usage.total_tokens > _threshold:
                logger.debug("Compacting history...")
                response = self._client.responses.compact(
                    model="gpt-5.2",
                    # instructions=system_prompt,  # TODO
                    input=session.compact_history,  # type: ignore
                )
                session.compact_history = cast(list[R.ResponseOutputItem | R.EasyInputMessage], response.output)  # TODO
                session.usage = response.usage

        # t_s = time.time()
        # compacted_response = self.compact()
        # print("Time for compaction: ", time.time() - t_s)
        # with open("compacted.json", "w") as file:
        #     json.dump(compacted_response.model_dump(), file, indent=2)

    def _create_response_stream(
        self,
        session: SessionState,
    ):
        """Build a streaming OpenAI response request from the current session.

        Args:
            session: Current SessionState for request context.

        Returns:
            Streaming response iterator from the OpenAI client.
        """
        # TODO: cqju: only search via file input
        if "file_search" in session.tools_selection and session.vector_store_ids:
            self._built_in_tools["file_search"]["vector_store_ids"] = session.vector_store_ids

        _tools: list = [self._built_in_tools[tool] for tool in session.tools_selection if tool in self._built_in_tools]
        content = [R.ResponseInputText(type="input_text", text=session.user_query)]
        content += [R.ResponseInputFile(type="input_file", file_id=file_id) for file_id in session.file_ids.file.keys()]
        content += [R.ResponseInputImage(type="input_image", file_id=file_id, detail="high") for file_id in session.file_ids.image.keys()]

        user_input = R.EasyInputMessage(role="user", content=content)
        session.full_history += [user_input]
        session.compact_history += [user_input]

        _model: str = session.model_info["name"]
        _effort: str = session.model_info["effort"]

        return self._client.responses.create(
            model=_model,
            input=session.compact_history,  # type: ignore
            # instructions=system_prompt,  # TODO
            tools=_tools,
            include=["web_search_call.action.sources", "reasoning.encrypted_content", "file_search_call.results"],
            max_tool_calls=MAX_TOOL_CALLS,
            stream=True,
            reasoning={"effort": _effort},  # type: ignore
            store=False,  # ZDR policy
            # **kwargs
        )
