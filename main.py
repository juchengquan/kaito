from dotenv import load_dotenv
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from openai import OpenAI

load_dotenv()


if __name__ == "__main__":
    from kaito.engine import EventEngine
    from kaito.ui_helper import check_all_files_ready, sync_vector_store_files

    model_info = inquirer.select(  # type: ignore
        message="Select the model:",
        choices=[
            Choice(name="gpt-5-nano", value={"name": "gpt-5-nano", "efforts": ['minimal', 'low', 'medium', 'high'], "effort": "minimal"}),
            Choice(name="gpt-5.1", value={"name": "gpt-5.1", "efforts": ['none', 'low', 'medium', 'high'], "effort": "none"}),
        ],
        default={"name": "gpt-5.1", "efforts": ['none', 'low', 'medium', 'high'], "effort": "none"},
    ).execute()

    model_effort = inquirer.select(  # type: ignore
        message="Select model reasoning effort:",
        choices=[
            Choice(name=value, value=value) for value in model_info["efforts"][:]  # TODO
        ],
        default=model_info["effort"],
    ).execute()

    model_info.update({"effort": model_effort})

    history: list[dict] = []
    engine = EventEngine(client=OpenAI(), history=history)

    tools_selection = inquirer.checkbox(  # type: ignore
        message="Select the tools:",
        choices=[
            Choice(name="Web Search", value="web_search", enabled=True),
            Choice(name="File Search", value="file_search", enabled=True),
            Choice(name="Code Interpreter", value="code_interpreter", enabled=True)
        ],
        cycle=False,
        validate=lambda x: len(x) >= 0
    ).execute()
    # tools_selection = ["web_search", "file_search", "code_interpreter"]

    while True:
        vector_store_ids: list[str] = sync_vector_store_files(
            engine=engine,
            tools_selection=tools_selection,
        )

        def _check_ready():
            all([check_all_files_ready(engine, vs_id) for vs_id in vector_store_ids])
        check_vec = inquirer.select(  # type: ignore
            message="Check if vector store is ready...",
            choices=[
                Choice(name="Check", value="Ready!"),
            ],
            default="Ready!",
            validate=_check_ready(),
            invalid_message="Vector store is not ready yet.",
        ).execute()
        user_query = inquirer.text(  # type: ignore
            message="Enter your query:",
            # default="",
            validate=lambda x: x
        ).execute()

        stream = engine.create_response(
            model_info=model_info,
            user_query=user_query,
            vector_store_ids=vector_store_ids,
            tools_selection=tools_selection,
        )

        engine.stream_event(stream=stream)

        print("\n\n")
