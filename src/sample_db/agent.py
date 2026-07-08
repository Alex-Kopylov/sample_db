"""LangGraph SQL agent that answers questions against the sample database."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig  # noqa: TC002 - LangGraph inspects config annotations at runtime.
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

from sample_db.config import get_config, get_settings
from sample_db.prompts import render_prompt
from sample_db.tools import sql_db_list_tables, sql_db_query, sql_db_schema

_prompt_config = get_config()

GENERATE_QUERY_SYSTEM_PROMPT = render_prompt(
    "generate_query_system.j2",
    dialect=_prompt_config.dialect,
    top_k=_prompt_config.top_k,
)
CHECK_QUERY_SYSTEM_PROMPT = render_prompt("check_query_system.j2", dialect=_prompt_config.dialect)


def build_agent() -> CompiledStateGraph:
    """Build and compile the SQL agent state graph."""
    settings = get_settings()
    model = init_chat_model(f"openai:{settings.model}")

    get_schema_node = ToolNode([sql_db_schema], name="get_schema")
    run_query_node = ToolNode([sql_db_query], name="run_query")

    def list_tables(
        state: MessagesState,
        config: RunnableConfig,
    ) -> dict[str, list[BaseMessage]]:
        _ = state
        tool_call = {
            "name": sql_db_list_tables.name,
            "args": {},
            "id": "call_sql_db_list_tables",
            "type": "tool_call",
        }
        tool_call_message = AIMessage(content="", tool_calls=[tool_call])
        tool_message = sql_db_list_tables.invoke(tool_call, config=config)

        return {"messages": [tool_call_message, tool_message]}

    def call_get_schema(state: MessagesState) -> dict[str, list[BaseMessage]]:
        model_with_tools = model.bind_tools([sql_db_schema], tool_choice="any")
        response = model_with_tools.invoke(state["messages"])

        return {"messages": [response]}

    def generate_query(state: MessagesState) -> dict[str, list[BaseMessage]]:
        model_with_tools = model.bind_tools([sql_db_query])
        response = model_with_tools.invoke([SystemMessage(content=GENERATE_QUERY_SYSTEM_PROMPT), *state["messages"]])

        return {"messages": [response]}

    def check_query(state: MessagesState) -> dict[str, list[BaseMessage]]:
        last_message = cast("AIMessage", state["messages"][-1])
        tool_call = last_message.tool_calls[0]
        original_tool_call_id = tool_call["id"]
        user_message = HumanMessage(content=str(tool_call["args"]["query"]))

        model_with_tools = model.bind_tools([sql_db_query], tool_choice="any")
        response = model_with_tools.invoke([SystemMessage(content=CHECK_QUERY_SYSTEM_PROMPT), user_message])
        response.id = last_message.id

        if response.tool_calls and original_tool_call_id is not None:
            response.tool_calls[0]["id"] = original_tool_call_id
            _preserve_raw_tool_call_id(response, original_tool_call_id)

        return {"messages": [response]}

    def should_continue(state: MessagesState) -> Literal["check_query", "__end__"]:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "check_query"
        return "__end__"

    # ty false positive (astral-sh/ty#2826): ty cannot yet see that TypedDict
    # classes such as MessagesState carry the __required_keys__/__optional_keys__
    # ClassVars that LangGraph's TypedDictLikeV1 protocol requires, so the
    # canonical StateGraph(MessagesState) call is rejected. A cast would erase
    # the state schema to Any; suppress narrowly until ty supports the pattern.
    builder = StateGraph(MessagesState)  # ty: ignore[invalid-argument-type]
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

    return cast("CompiledStateGraph", builder.compile())


def _preserve_raw_tool_call_id(message: AIMessage, tool_call_id: str) -> None:
    raw_tool_calls = message.additional_kwargs.get("tool_calls")
    if isinstance(raw_tool_calls, list) and raw_tool_calls:
        raw_tool_call = raw_tool_calls[0]
        if isinstance(raw_tool_call, dict):
            raw_tool_call["id"] = tool_call_id


graph = build_agent()
