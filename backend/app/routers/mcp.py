"""
Reserved stub for a future MCP server integration. Intentionally empty:
no logic until the integration is scoped.
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("")
def mcp_placeholder():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="MCP server integration is reserved and not implemented yet.",
    )
