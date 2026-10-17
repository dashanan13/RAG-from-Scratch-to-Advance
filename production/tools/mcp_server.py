"""MCP server exposing the retrieve_evidence tool over the Model Context Protocol (MCP)."""
from __future__ import annotations


def build_server():
    """Construct and return an MCP server exposing ``retrieve_evidence``.

    Requires the optional ``mcp`` package; install it to serve the tool over MCP.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # optional dependency; the HTTP tool in llm_tool.py needs nothing extra
        raise RuntimeError("The 'mcp' package is required for the MCP server. Install it with 'pip install mcp'.") from exc

    from .llm_tool import retrieve_evidence

    server = FastMCP("shakespeare-evidence-desk")

    @server.tool()
    def retrieve_evidence_tool(query: str, top_k: int = 5) -> dict:
        """Retrieve cited passages from the Shakespeare corpus for a query."""
        return retrieve_evidence(query, top_k=top_k)

    return server
