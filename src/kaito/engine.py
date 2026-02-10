import base64
import json
import os
import time
from pathlib import Path
from typing import AsyncGenerator, Generator, cast

from loguru import logger
from openai import AsyncOpenAI, OpenAI

import kaito.openai_datatypes as R

# from .vector_store import # KaitoVectorStoreFiles, KaitoVectorStores
from .local_file_engine import LocalFileEngine

# from .prompts import system_prompt
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
        async_client: AsyncOpenAI,
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
        self._async_client: AsyncOpenAI = async_client
        self._file_engine = LocalFileEngine(client=client, db_path=db_path)
        self._built_in_tools: dict[str, dict] = built_in_tools

        # self._vs = KaitoVectorStores(client=client)
        # self._vs_files = KaitoVectorStoreFiles(client=client)

    async def astream(
        self,
        session: SessionState,
    ) -> AsyncGenerator:
        """Yield incremental text deltas while updating internal history and usage.

        Args:
            session: Current SessionState to update.

        Yields:
            Text deltas emitted by the model as they arrive.
        """
        stream = await self._create_response_stream(session=session)

        output_index = -1
        t_s = time.time()

        async for event in stream:
            output_index, status, delta = self._process_stream_event(
                event=event,
                session=session,
                output_index=output_index,
                start_time=t_s,
            )
            yield delta, status
            
            if WRITE_TO_FILE:
                with open(f"tests/streaming_results_{int(t_s)}.json", "a") as file:
                    json_line = json.dumps(event.model_dump(), indent=2)
                    file.write(json_line + "\n")

        self._try_compact(session=session)

    def _process_stream_event(
        self,
        event: R.ResponseStreamEvent,
        session: SessionState,
        output_index: int,
        start_time: float,
    ) -> tuple[int, str, str | None]:
        """Handle one stream event and return updated state plus any text delta.

        Args:
            event: Stream event from the OpenAI client.
            session: Current SessionState to update.
            output_index: Current output index tracker.
            start_time: Stream start timestamp for logging.

        Returns:
            Updated output index and optional text delta.
        """
        if isinstance(event, (R.ResponseCreatedEvent, R.ResponseInProgressEvent, R.ResponseFailedEvent, R.ResponseIncompleteEvent)):
            return output_index, event.type, None

        if isinstance(event, R.ResponseCompletedEvent):
            self._handle_response_completed(event, session=session)
            return output_index, event.type, None

        if isinstance(event, (R.ResponseOutputItemAddedEvent, R.ResponseOutputItemDoneEvent)):
            output_index = self._handle_output_item_event(event, output_index=output_index, start_time=start_time)
            return output_index, event.type, None

        if isinstance(
            event,
            (
                R.ResponseFileSearchCallInProgressEvent,
                R.ResponseFileSearchCallSearchingEvent,
                R.ResponseFileSearchCallCompletedEvent,
                R.ResponseWebSearchCallInProgressEvent,
                R.ResponseWebSearchCallSearchingEvent,
                R.ResponseWebSearchCallCompletedEvent,
                R.ResponseCodeInterpreterCallInProgressEvent,
                R.ResponseCodeInterpreterCallInterpretingEvent,
                R.ResponseCodeInterpreterCallCompletedEvent,
                R.ResponseCodeInterpreterCallCodeDoneEvent,
                R.ResponseImageGenCallInProgressEvent,
                R.ResponseImageGenCallGeneratingEvent,
                R.ResponseImageGenCallCompletedEvent,
                R.ResponseImageGenCallPartialImageEvent,
            ),
        ):
            status_ = self._log_tool_status(event, start_time=start_time)
            return output_index, status_, None

        if isinstance(event, R.ResponseCodeInterpreterCallCodeDeltaEvent):
            status_ = self._log_tool_status(event, start_time=start_time)
            return output_index, status_, None

        if isinstance(event, R.ResponseTextDoneEvent):
            status_ = self._log_text_status(event, start_time=start_time)
            return output_index, status_, None

        if isinstance(event, (R.ResponseContentPartAddedEvent, R.ResponseContentPartDoneEvent)):
            status_ = self._log_content_part_status(event, start_time=start_time)
            return output_index, status_, None

        if isinstance(event, R.ResponseTextDeltaEvent):
            return output_index, event.type, event.delta

        if isinstance(event, R.ResponseImageGenCallPartialImageEvent):
            event: R.ResponseImageGenCallPartialImageEvent = cast(R.ResponseImageGenCallPartialImageEvent, event)
            image_base64_str: str = event.partial_image_b64
            _image_bytes: bytes = base64.b64decode(image_base64_str)  # Note that as set `partial_images` to be 0 already
            return output_index, event.type, image_base64_str

        if isinstance(event, R.ResponseOutputTextAnnotationAddedEvent):
            _annotation = self._handle_annotation_event(event)  # TODO
            return output_index, event.type, None

        print_class(event)
        return output_index, event.type, None

    def _handle_response_completed(self, event: R.ResponseCompletedEvent, session: SessionState) -> None:
        """Update session state when a response completes.

        Args:
            event: Completed response event.
            session: Current SessionState to update.
        """
        output = event.response.output
        session.current_output = output
        session.usage = event.response.usage
        session.full_history += output
        session.compact_history += output

    def _handle_output_item_event(
        self,
        event: R.ResponseOutputItemAddedEvent | R.ResponseOutputItemDoneEvent,
        output_index: int,
        start_time: float,
    ) -> int:
        """Track output indices and log item status.

        Args:
            event: Output item status event.
            output_index: Current output index tracker.
            start_time: Stream start timestamp for logging.

        Returns:
            Updated output index.
        """
        if output_index != event.output_index:
            output_index += 1
        assert output_index == event.output_index, f"output_index does not align - count:{output_index}|event:{event.output_index}"

        if event.item.type in {"message", "reasoning", "web_search_call", "code_interpreter_call", "file_search_call"}:
            _item = cast(
                R.ResponseOutputMessage
                | R.ResponseReasoningItem
                | R.ResponseFunctionWebSearch
                | R.ResponseCodeInterpreterToolCall
                | R.ResponseFileSearchToolCall,
                event.item,
            )
            _status_type = event.type.split(".")
            logger.debug(f"{time.time() - start_time:.2f} | @{_status_type[2]} | {event.item.type}: {_item.status}")

        return output_index

    def _log_tool_status(self, event: R.ResponseStreamEvent, start_time: float) -> str:
        """Log tool status transitions for file search, web search, and code interpreter.

        Args:
            event: Tool status stream event.
            start_time: Stream start timestamp for logging.
        """
        _status_type = event.type.split(".")
        logger.debug(f"{time.time() - start_time:.2f} | {_status_type[1]}: {_status_type[2]}")
        return f"{_status_type[1]}: {_status_type[2]}"

    def _log_text_status(self, event: R.ResponseTextDoneEvent, start_time: float) -> str:
        """Log completion of a text output item.

        Args:
            event: Text done event.
            start_time: Stream start timestamp for logging.
        """
        _status_type = event.type.split(".")
        logger.debug(f"\n{time.time() - start_time:.2f} | {_status_type[1]}: {_status_type[2]}")
        return f"{_status_type[1]}: {_status_type[2]}"

    def _log_content_part_status(
        self,
        event: R.ResponseContentPartAddedEvent | R.ResponseContentPartDoneEvent,
        start_time: float,
    ) -> str:
        """Log content part status changes.

        Args:
            event: Content part status event.
            start_time: Stream start timestamp for logging.
        """
        _status_type = event.type.split(".")
        logger.debug(f"{time.time() - start_time:.2f} | @{_status_type[2]} | {event.part.type}: {_status_type[1]}")
        return f"@{_status_type[2]} | {event.part.type}: {_status_type[1]}"

    def _handle_annotation_event(self, event: R.ResponseOutputTextAnnotationAddedEvent):
        """Handle text annotation events for citations and file paths.

        Args:
            event: Annotation added event.
        """
        annotation: dict = cast(dict, event.annotation)
        annot = annotation
        match annotation.get("type", None):
            case "url_citation":
                annot = R.AnnotationURLCitation(**annotation)
            case "file_citation":
                annot = R.AnnotationFileCitation(**annotation)
            case "container_file_citation":
                annot = R.AnnotationContainerFileCitation(**annotation)
            case "file_path":
                annot = R.AnnotationFilePath(**annotation)
        
        return annot

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

    async def _create_response_stream(
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
        # if "file_search" in session.tools_selection and session.vector_store_ids:
        #     self._built_in_tools["file_search"]["vector_store_ids"] = session.vector_store_ids

        _tools: list = [self._built_in_tools[tool] for tool in session.tools_selection if tool in self._built_in_tools]
        content: list = [R.ResponseInputText(type="input_text", text=session.user_query)]
        content += [R.ResponseInputFile(type="input_file", file_id=file_id) for file_id in session.file_ids.file.keys()]
        content += [R.ResponseInputImage(type="input_image", file_id=file_id, detail="high") for file_id in session.file_ids.image.keys()]

        user_input = R.EasyInputMessage(role="user", content=content)
        session.full_history += [user_input]
        session.compact_history += [user_input]

        _model: str = session.model_info["name"]
        _effort: str = session.model_info["effort"]

        return await self._async_client.responses.create(  # type: ignore
            model=_model,
            input=session.compact_history,
            # instructions=system_prompt,  # TODO
            tools=_tools,
            include=["web_search_call.action.sources", "reasoning.encrypted_content", "file_search_call.results"],
            max_tool_calls=MAX_TOOL_CALLS,
            stream=True,
            reasoning={"effort": _effort},
            store=False,  # ZDR policy
            # **kwargs
        )
