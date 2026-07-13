"""统一响应格式工具"""
from typing import Any, Optional
from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "success", code: int = 200) -> JSONResponse:
    """
    统一成功响应格式
    
    Args:
        data: 响应数据
        message: 响应消息
        code: 状态码（默认 200）
    
    Returns:
        JSONResponse: 统一格式的 JSON 响应
    """
    return JSONResponse(
        status_code=200,
        content={
            "code": code,
            "message": message,
            "data": data
        }
    )


def error_response(message: str = "error", code: int = 400, data: Any = None) -> JSONResponse:
    """
    统一错误响应格式
    
    Args:
        message: 错误消息
        code: 错误码
        data: 附加数据
    
    Returns:
        JSONResponse: 统一格式的 JSON 响应
    """
    return JSONResponse(
        status_code=200,  # 始终返回 200，通过 code 区分
        content={
            "code": code,
            "message": message,
            "data": data
        }
    )
