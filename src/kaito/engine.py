import json
import os
import time
from typing import cast

from openai import OpenAI
from openai.types.responses.response_stream_event import ResponseStreamEvent

import kaito.datatypes as R

from .file_db import FileDB
from .vector_store import VectorStoreEngine


def print_class(event):
    if not isinstance(event, R.ResponseTextDeltaEvent):
        print(type(event))


PRINT_STATUS: bool = os.getenv("PRINT_STATUS", default="FALSE").lower() in ("true", "1")
MAX_TOOL_CALLS: int = int(os.getenv("MAX_TOOL_CALLS", default=5))
WRITE_TO_FILE: bool = os.getenv("WRITE_TO_FILE", default="FALSE").lower() in ("true", "1")


class EventEngine:
    def __init__(
        self,
        client: OpenAI,
        history: list[dict] = [],
    ) -> None:
        self._client = client
        self._history = history
        self._all_tools: dict[str, dict] = {
            "web_search": {"type": "web_search"},  # , "search_context_size": "low"},
            "code_interpreter": {"type": "code_interpreter", "container": {"type": "auto", "memory_limit": "1g"}},
            "file_search": {"type": "file_search", "vector_store_ids": []},
            "image_generation": {"type": "image_generation"},  # not available
        }

        self._file_db = FileDB(client=client)
        self._vec = VectorStoreEngine(client=client)

    def create_response(
        self,
        model_info: dict,
        user_query: str,
        tools_selection: list[str],
        vector_store_ids: list[str] = [],
        # **kwargs,
    ):
        if "file_search" in tools_selection and vector_store_ids:
            self._all_tools["file_search"]["vector_store_ids"] = vector_store_ids

        _tools: list = [self._all_tools[tool] for tool in tools_selection if tool in self._all_tools]
        self._history += [{"role": "user", "content": user_query}]
        model: str = model_info["name"]
        effort: str = model_info["effort"]

        return self._client.responses.create(
            model=model,
            input=self._history,  # type: ignore
            tools=_tools,
            max_tool_calls=MAX_TOOL_CALLS,
            stream=True,
            reasoning={"effort": effort},  # type: ignore
            # **kwargs
        )

    def stream_event(self, stream: list[ResponseStreamEvent]):
        output_index = -1
        t_s = time.time()

        for _, event in enumerate(stream):
            match type(event):
                case R.ResponseCreatedEvent | R.ResponseInProgressEvent | R.ResponseFailedEvent | R.ResponseIncompleteEvent:
                    ...
                    # print_class(event)

                case R.ResponseCompletedEvent:
                    event = cast(R.ResponseCompletedEvent, event)
                    _output = event.response.output
                    self._history += [{"role": el.role, "content": el.content} for el in _output if isinstance(el, R.ResponseOutputMessage)]

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
                            if PRINT_STATUS:
                                print(f"{time.time() - t_s:.2f} | @{_status_type[2]} | {event.item.type}: {_item.status}")

                # File Search
                # status - file search
                case R.ResponseFileSearchCallInProgressEvent | R.ResponseFileSearchCallSearchingEvent | R.ResponseFileSearchCallCompletedEvent:
                    event = cast(
                        R.ResponseFileSearchCallInProgressEvent | R.ResponseFileSearchCallSearchingEvent | R.ResponseFileSearchCallCompletedEvent,
                        event,
                    )
                    _status_type = event.type.split(".")
                    if PRINT_STATUS:
                        print(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")

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
                    if PRINT_STATUS:
                        print(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")
                ## status - code interpreter
                case R.ResponseCodeInterpreterCallCodeDoneEvent:
                    event = cast(R.ResponseCodeInterpreterCallCodeDoneEvent, event)
                    _status_type = event.type.split(".")
                    if PRINT_STATUS:
                        print(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")
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
                    if PRINT_STATUS:
                        print(f"{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")

                # Text Output
                # status - text
                case R.ResponseTextDoneEvent:
                    event = cast(R.ResponseTextDoneEvent, event)
                    _status_type = event.type.split(".")
                    # FIXME
                    if PRINT_STATUS:
                        print(f"\n{time.time() - t_s:.2f} | {_status_type[1]}: {_status_type[2]}")
                # status - **text** content_part - Emitted when a new output item is added
                case R.ResponseContentPartAddedEvent | R.ResponseContentPartDoneEvent:
                    event = cast(R.ResponseContentPartAddedEvent | R.ResponseContentPartDoneEvent, event)
                    _status_type = event.type.split(".")
                    if PRINT_STATUS:
                        print(f"{time.time() - t_s:.2f} | @{_status_type[2]} | {event.part.type}: {_status_type[1]}")
                # output - text
                case R.ResponseTextDeltaEvent:
                    event = cast(R.ResponseTextDeltaEvent, event)
                    print(event.delta, end="")
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
                with open(f"tests/streaming_results_{int(time.time())}.json", "a") as file:
                    json_line = json.dumps(event.model_dump(), indent=2)
                    file.write(json_line + "\n")
