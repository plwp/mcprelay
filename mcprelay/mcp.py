"""
MCP protocol awareness and safeguards.
"""

import json
from typing import Dict, Any, List, Optional
import structlog
from pydantic import BaseModel, ValidationError

from .auth import AuthContext

logger = structlog.get_logger()


class MCPRequest(BaseModel):
    """MCP request structure."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class MCPResponse(BaseModel):
    """MCP response structure."""
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class MCPRequestValidator:
    """Validates and sanitizes MCP requests."""
    
    # Dangerous methods that require extra scrutiny
    DANGEROUS_METHODS = {
        "files/write",
        "files/delete", 
        "tools/call",
        "resources/write",
        "exec/command",
        "system/shutdown"
    }
    
    # Methods blocked for non-admin users
    ADMIN_ONLY_METHODS = {
        "system/shutdown",
        "system/restart", 
        "config/update",
        "users/create",
        "users/delete"
    }
    
    def __init__(self):
        self.blocked_patterns = [
            # Prevent path traversal
            "../",
            "..\\",
            "/etc/passwd",
            "/etc/shadow",
            # Prevent command injection
            "; rm -rf",
            "& del",
            "| rm",
            # Prevent script injection
            "<script>",
            "javascript:",
            "eval(",
        ]
    
    async def validate_and_sanitize(
        self, 
        request_body: bytes, 
        auth_context: AuthContext
    ) -> bytes:
        """Validate and sanitize MCP request."""
        
        try:
            # Parse JSON-RPC request
            request_data = json.loads(request_body)
            
            # Handle batch requests
            if isinstance(request_data, list):
                sanitized_requests = []
                for req in request_data:
                    sanitized_req = await self._validate_single_request(req, auth_context)
                    sanitized_requests.append(sanitized_req)
                return json.dumps(sanitized_requests).encode()
            else:
                sanitized_request = await self._validate_single_request(request_data, auth_context)
                return json.dumps(sanitized_request).encode()
                
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request")
        except Exception as e:
            logger.error("Request validation error", error=str(e))
            raise ValueError(f"Request validation failed: {e}")
    
    async def _validate_single_request(
        self, 
        request_data: Dict[str, Any], 
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Validate a single MCP request."""
        
        try:
            # Validate basic MCP structure
            mcp_request = MCPRequest(**request_data)
        except ValidationError as e:
            raise ValueError(f"Invalid MCP request structure: {e}")
        
        # Check method permissions
        if mcp_request.method in self.ADMIN_ONLY_METHODS:
            if not auth_context.is_admin:
                logger.warning(
                    "Blocked admin method",
                    method=mcp_request.method,
                    user=auth_context.user_id
                )
                raise ValueError(f"Method {mcp_request.method} requires admin privileges")
        
        # Check user's allowed actions
        if auth_context.allowed_mcp_actions != ["*"]:
            method_allowed = any(
                mcp_request.method.startswith(pattern.rstrip("*"))
                for pattern in auth_context.allowed_mcp_actions
            )
            if not method_allowed:
                logger.warning(
                    "Method not allowed for user",
                    method=mcp_request.method,
                    user=auth_context.user_id,
                    allowed=auth_context.allowed_mcp_actions
                )
                raise ValueError(f"Method {mcp_request.method} not allowed for user")
        
        # Sanitize dangerous methods
        if mcp_request.method in self.DANGEROUS_METHODS:
            logger.info(
                "Processing dangerous method",
                method=mcp_request.method,
                user=auth_context.user_id
            )
            mcp_request.params = await self._sanitize_dangerous_params(
                mcp_request.method, 
                mcp_request.params or {},
                auth_context
            )
        
        # Sanitize parameters for injection attacks
        if mcp_request.params:
            mcp_request.params = await self._sanitize_params(mcp_request.params)
        
        return mcp_request.model_dump(exclude_none=True)
    
    async def _sanitize_dangerous_params(
        self,
        method: str,
        params: Dict[str, Any],
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Sanitize parameters for dangerous methods."""
        
        sanitized = params.copy()
        
        if method == "files/write":
            # Validate file path
            file_path = params.get("path", "")
            if self._contains_dangerous_patterns(file_path):
                raise ValueError(f"Dangerous file path: {file_path}")
            
            # Restrict to user's directory if not admin
            if not auth_context.is_admin:
                if not file_path.startswith(f"/users/{auth_context.user_id}/"):
                    raise ValueError("File access restricted to user directory")
        
        elif method == "tools/call":
            # Validate tool name and arguments
            tool_name = params.get("name", "")
            if tool_name in ["system", "exec", "shell"]:
                if not auth_context.is_admin:
                    raise ValueError("System tools require admin privileges")
        
        return sanitized
    
    async def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters to prevent injection attacks."""
        
        def sanitize_value(value):
            if isinstance(value, str):
                # Check for dangerous patterns
                if self._contains_dangerous_patterns(value):
                    logger.warning("Blocked dangerous pattern in request", pattern=value[:100])
                    raise ValueError("Request contains potentially dangerous content")
                return value
            elif isinstance(value, dict):
                return {k: sanitize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value
        
        return sanitize_value(params)
    
    def _contains_dangerous_patterns(self, text: str) -> bool:
        """Check if text contains dangerous patterns."""
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in self.blocked_patterns)


class MCPResponseSanitizer:
    """Sanitizes MCP responses."""
    
    def __init__(self):
        self.sensitive_keys = {
            "password", "secret", "token", "key", "credential", 
            "auth", "session", "cookie", "private"
        }
    
    async def sanitize_response(
        self, 
        response_body: bytes, 
        auth_context: AuthContext
    ) -> bytes:
        """Sanitize MCP response."""
        
        try:
            response_data = json.loads(response_body)
            
            # Handle batch responses
            if isinstance(response_data, list):
                sanitized_responses = []
                for resp in response_data:
                    sanitized_resp = await self._sanitize_single_response(resp, auth_context)
                    sanitized_responses.append(sanitized_resp)
                return json.dumps(sanitized_responses).encode()
            else:
                sanitized_response = await self._sanitize_single_response(response_data, auth_context)
                return json.dumps(sanitized_response).encode()
                
        except json.JSONDecodeError:
            # Not JSON, return as-is
            return response_body
        except Exception as e:
            logger.error("Response sanitization error", error=str(e))
            return response_body
    
    async def _sanitize_single_response(
        self, 
        response_data: Dict[str, Any], 
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Sanitize a single MCP response."""
        
        try:
            mcp_response = MCPResponse(**response_data)
        except ValidationError:
            # Not a valid MCP response, return as-is
            return response_data
        
        # Sanitize result data
        if mcp_response.result:
            mcp_response.result = await self._sanitize_result_data(
                mcp_response.result, 
                auth_context
            )
        
        # Sanitize error data (remove sensitive info)
        if mcp_response.error:
            mcp_response.error = await self._sanitize_error_data(mcp_response.error)
        
        return mcp_response.model_dump(exclude_none=True)
    
    async def _sanitize_result_data(
        self, 
        result: Dict[str, Any], 
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Sanitize result data."""
        
        def sanitize_value(value):
            if isinstance(value, dict):
                sanitized = {}
                for k, v in value.items():
                    # Remove sensitive keys for non-admin users
                    if not auth_context.is_admin and any(
                        sensitive in k.lower() for sensitive in self.sensitive_keys
                    ):
                        sanitized[k] = "***REDACTED***"
                    else:
                        sanitized[k] = sanitize_value(v)
                return sanitized
            elif isinstance(value, list):
                return [sanitize_value(item) for item in value]
            else:
                return value
        
        return sanitize_value(result)
    
    async def _sanitize_error_data(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize error data to prevent information leakage."""
        
        # Remove potentially sensitive error details
        sanitized_error = {
            "code": error.get("code"),
            "message": error.get("message", "An error occurred")
        }
        
        # Keep data if it doesn't contain sensitive info
        error_data = error.get("data")
        if error_data and isinstance(error_data, dict):
            # Remove stack traces and file paths
            safe_data = {}
            for k, v in error_data.items():
                if k.lower() not in ["traceback", "stack", "filepath", "filename"]:
                    safe_data[k] = v
            if safe_data:
                sanitized_error["data"] = safe_data
        
        return sanitized_error