"""LangGraph SQL agent that answers questions against the sample database."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

from sample_db import db
from sample_db.config import get_settings
from sample_db.tools import sql_db_list_tables, sql_db_query, sql_db_schema

GENERATE_QUERY_SYSTEM_PROMPT = """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct SQLite query to run,
then look at the results of the query and return the answer. Unless the user
specifies a specific number of examples they wish to obtain, always limit your
query to at most 5 results.
You can order the results by a relevant column to return the most interesting
examples in the database. Never query for all the columns from a specific table,
only ask for the relevant columns given the question.

NEVER make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
""".strip()

CHECK_QUERY_SYSTEM_PROMPT = """
You are a SQL expert with a strong attention to detail.
Double check the SQLite query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no
mistakes, reproduce the original query.

You will call the appropriate tool to execute the query after running this check.
""".strip()


def build_agent() -> CompiledStateGraph:
    """Build and compile the SQL agent state graph."""
    settings = get_settings()
    model = init_chat_model(f"openai:{settings.model}")

    get_schema_node = ToolNode([sql_db_schema], name="get_schema")
    run_query_node = ToolNode([sql_db_query], name="run_query")

    def list_tables(_state: MessagesState) -> dict[str, list[BaseMessage]]:
        tool_call = {
            "name": sql_db_list_tables.name,
            "args": {},
            "id": "call_sql_db_list_tables",
            "type": "tool_call",
        }
        tool_call_message = AIMessage(content="", tool_calls=[tool_call])
        tool_message = sql_db_list_tables.invoke(tool_call)

        return {"messages": [tool_call_message, tool_message]}

    def call_get_schema(state: MessagesState) -> dict[str, list[BaseMessage]]:
        model_with_tools = model.bind_tools([sql_db_schema], tool_choice="any")
        response = model_with_tools.invoke(state["messages"])

        return {"messages": [response]}

    def generate_query(state: MessagesState) -> dict[str, list[BaseMessage]]:
        model_with_tools = model.bind_tools([sql_db_query])
        response = model_with_tools.invoke(
            [SystemMessage(content=GENERATE_QUERY_SYSTEM_PROMPT), *state["messages"]]
        )

        return {"messages": [response]}

    def check_query(state: MessagesState) -> dict[str, list[BaseMessage]]:
        last_message = cast("AIMessage", state["messages"][-1])
        tool_call = last_message.tool_calls[0]
        original_tool_call_id = tool_call["id"]
        user_message = HumanMessage(content=str(tool_call["args"]["query"]))

        model_with_tools = model.bind_tools([sql_db_query], tool_choice="any")
        response = cast(
            "AIMessage",
            model_with_tools.invoke(
                [SystemMessage(content=CHECK_QUERY_SYSTEM_PROMPT), user_message]
            ),
        )
        response.id = last_message.id

        if response.tool_calls:
            response.tool_calls[0]["id"] = original_tool_call_id
            _preserve_raw_tool_call_id(response, original_tool_call_id)

        return {"messages": [response]}

    def should_continue(state: MessagesState) -> Literal["check_query", "__end__"]:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "check_query"
        return END

    builder = StateGraph(MessagesState)
    builder.add_node("list_tables", list_tables)
    builder.add_node("call_get_schema", call_get_schema)
    builder.add_node("get_schema", get_schema_node)
    builder.add_node("generate_query", generate_query)
    builder.add_node("check_query", check_query)
    builder.add_node("run_query", run_query_node)

    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "call_get_schema")
    builder.add_edge("call_get_schema", "get_schema")
    builder.add_edge("get_schema", "generate_query")
    builder.add_conditional_edges("generate_query", should_continue)
    builder.add_edge("check_query", "run_query")
    builder.add_edge("run_query", "generate_query")

    return builder.compile()


def _preserve_raw_tool_call_id(message: AIMessage, tool_call_id: str) -> None:
    raw_tool_calls = message.additional_kwargs.get("tool_calls")
    if isinstance(raw_tool_calls, list) and raw_tool_calls:
        raw_tool_call = raw_tool_calls[0]
        if isinstance(raw_tool_call, dict):
            raw_tool_call["id"] = tool_call_id


settings = get_settings()
if not settings.db_path.exists():
    db.init_db(settings.db_path)

graph = build_agent()
