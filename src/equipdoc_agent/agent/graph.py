from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from ..config import Settings
from ..rag import KnowledgeRetriever
from ..tools import analyze_bearing_signal
from .policy import should_run_diagnosis
from .reporting import render_diagnosis_report


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    signal_path: str
    review_result: str


SYSTEM_PROMPT = """你是机电装备智能运维辅助 Agent。
不得编造设备编号、采样位置、维修历史、运行工况或剩余寿命。
只有用户提供了有效信号且明确要求诊断时，才能调用 diagnose_bearing。
高风险维修建议必须保留人工确认，不得声称已经控制或维修真实设备。
"""


def _last_human_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _parse_tool_result(content) -> dict:
    if isinstance(content, dict):
        return content
    try:
        parsed = json.loads(str(content))
    except (TypeError, json.JSONDecodeError):
        return {"status": "error", "error": str(content)}
    return parsed if isinstance(parsed, dict) else {"status": "error", "error": str(parsed)}


def _fault_filter(fault_type: str) -> dict[str, str] | None:
    if "外圈" in fault_type:
        return {"equipment": "bearing", "fault_type": "outer_race"}
    if "内圈" in fault_type:
        return {"equipment": "bearing", "fault_type": "inner_race"}
    if "滚动体" in fault_type:
        return {"equipment": "bearing", "fault_type": "ball"}
    return None


def _review_call_payload(call: dict) -> dict:
    """Build a reviewer-facing tool call without exposing server filesystem paths."""
    args = dict(call.get("args") or {})
    signal_path = args.pop("signal_path", None)
    if signal_path:
        normalized = str(signal_path).replace("\\", "/")
        args["signal_file"] = normalized.rsplit("/", 1)[-1]
    return {"name": call.get("name"), "args": args}


def build_graph(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    retriever_holder: dict[str, KnowledgeRetriever] = {}

    def get_retriever() -> KnowledgeRetriever | None:
        if not settings.rag_enabled or not settings.rag_chunks_path.exists():
            return None
        if "retriever" not in retriever_holder:
            retriever_holder["retriever"] = KnowledgeRetriever(settings)
        return retriever_holder["retriever"]

    @tool
    def diagnose_bearing(signal_path: str) -> dict:
        """Analyze a sandboxed .npy bearing vibration signal after human review."""
        return analyze_bearing_signal(signal_path, settings)

    tools = [diagnose_bearing]
    tools_by_name = {item.name: item for item in tools}
    llm_with_tools = None
    if not settings.demo_mode:
        llm = ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_seconds,
            temperature=0,
        )
        llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        messages = state.get("messages", [])
        if messages and isinstance(messages[-1], ToolMessage):
            result = _parse_tool_result(messages[-1].content)
            if result.get("status") == "error":
                return {"messages": [AIMessage(content=f"诊断工具执行失败：{result.get('error')}")]}
            signal_path = state.get("signal_path", "")
            evidence = []
            retriever = get_retriever()
            if retriever is not None:
                fault_type = str(result.get("fault_type", ""))
                query = f"{fault_type} 故障机理 振动特征 维修建议 风险提示"
                evidence = retriever.search(query, filters=_fault_filter(fault_type), top_k=3)
                evidence.extend(
                    retriever.search("维修决策 风险提示 不能推断剩余寿命", top_k=2)
                )
                unique = {}
                for item in evidence:
                    unique[item.get("chunk_id")] = item
                evidence = list(unique.values())[:5]
            report = render_diagnosis_report(
                result,
                signal_name=Path(signal_path).name if signal_path else "未提供",
                evidence=evidence,
            )
            return {"messages": [AIMessage(content=report)]}

        user_text = _last_human_text(messages)
        signal_path = state.get("signal_path")
        if should_run_diagnosis(user_text, signal_path):
            return {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "diagnose_bearing",
                                "args": {"signal_path": signal_path},
                                "id": f"diagnose_{uuid4().hex}",
                            }
                        ],
                    )
                ]
            }

        if settings.demo_mode:
            retriever = get_retriever()
            hits = retriever.search(user_text, top_k=3) if retriever and user_text else []
            if hits:
                snippets = "\n".join(
                    f"- {item.get('doc_id')}#{item.get('chunk_id')}：{str(item.get('text', ''))[:180]}"
                    for item in hits
                )
                content = (
                    "当前为 Demo 模式，不调用7B模型。以下是词法检索命中的项目知识片段：\n\n"
                    f"{snippets}\n\n完整生成回答需要将 EQUIPDOC_DEMO_MODE 设为 false 并配置模型服务。"
                )
            else:
                content = "当前为 Demo 模式。请上传 .npy 信号进行固定案例演示，或配置模型服务后进行知识问答。"
            return {"messages": [AIMessage(content=content)]}

        assert llm_with_tools is not None
        response = llm_with_tools.invoke([SystemMessage(content=SYSTEM_PROMPT), *messages])
        return {"messages": [response]}

    def should_continue(state: AgentState):
        last_message = state.get("messages", [])[-1]
        if getattr(last_message, "tool_calls", None):
            return "review"
        return END

    def review_node(state: AgentState) -> dict:
        calls = state.get("messages", [])[-1].tool_calls
        decision = interrupt(
            {
                "type": "tool_review",
                "requested_tools": [_review_call_payload(item) for item in calls],
                "notice": "Approve runs a read-only diagnostic tool; Reject cancels the call.",
            }
        )
        return {"review_result": decision}

    def after_review(state: AgentState):
        return "tools" if state.get("review_result") == "approve" else "cancel"

    def tool_node(state: AgentState) -> dict:
        outputs = []
        for call in state.get("messages", [])[-1].tool_calls:
            name = call.get("name")
            if name not in tools_by_name:
                payload = {"status": "error", "error": f"Unknown tool: {name}"}
            else:
                try:
                    payload = tools_by_name[name].invoke(call.get("args") or {})
                except Exception as exc:
                    payload = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            outputs.append(
                ToolMessage(
                    content=json.dumps(payload, ensure_ascii=False),
                    tool_call_id=call.get("id", f"tool_{uuid4().hex}"),
                )
            )
        return {"messages": outputs}

    def cancel_node(_: AgentState) -> dict:
        return {"messages": [AIMessage(content="已根据人工审核取消本次诊断工具调用。")]} 

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("review", review_node)
    graph.add_node("tools", tool_node)
    graph.add_node("cancel", cancel_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_conditional_edges("review", after_review)
    graph.add_edge("tools", "agent")
    graph.add_edge("cancel", END)
    return graph.compile(checkpointer=MemorySaver())
