def build_graph(*args, **kwargs):
    """Import LangGraph dependencies only when the application builds a graph."""
    from .graph import build_graph as _build_graph

    return _build_graph(*args, **kwargs)


__all__ = ["build_graph"]
