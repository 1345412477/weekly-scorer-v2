"""统一异常处理模块"""
from fastapi import HTTPException, status
from typing import Optional


class AppException(Exception):
    """应用基础异常"""
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationException(AppException):
    """数据验证异常"""
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class ResourceNotFoundException(AppException):
    """资源不存在异常"""
    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource}不存在"
        if identifier:
            message += f"（ID: {identifier}）"
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class BusinessRuleException(AppException):
    """业务规则异常"""
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class ExternalServiceException(AppException):
    """外部服务异常"""
    def __init__(self, service: str, message: str):
        super().__init__(f"{service}服务调用失败: {message}", status.HTTP_503_SERVICE_UNAVAILABLE)


class DatabaseException(AppException):
    """数据库操作异常"""
    def __init__(self, message: str):
        super().__init__(f"数据库操作失败: {message}", status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_exception(e: Exception) -> HTTPException:
    """统一异常处理函数"""
    if isinstance(e, AppException):
        return HTTPException(status_code=e.code, detail=e.message)
    
    if isinstance(e, HTTPException):
        return e
    
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="服务器内部错误，请稍后重试"
    )