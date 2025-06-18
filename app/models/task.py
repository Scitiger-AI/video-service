from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict
from bson import ObjectId


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PyObjectId(ObjectId):
    """用于Pydantic模型的ObjectId类型"""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class TaskModel:
    """任务模型类（用于MongoDB）"""
    
    @staticmethod
    def create_task(
        tenant_id: str,
        user_id: str,
        model: str,
        provider: str,
        parameters: Dict[str, Any],
        is_async: bool = True
    ) -> dict:
        """
        创建新任务
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID
            model: 模型名称
            provider: 提供商
            parameters: 模型参数
            is_async: 是否异步执行
            
        Returns:
            dict: 任务数据
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "status": TaskStatus.PENDING.value,
            "created_at": now,
            "updated_at": now,
            "model": model,
            "provider": provider,
            "parameters": parameters,
            "is_async": is_async,
            "result": None,
            "error": None
        }
    
    @staticmethod
    def update_status(task: dict, status: TaskStatus) -> dict:
        """
        更新任务状态
        
        Args:
            task: 任务数据
            status: 新状态
            
        Returns:
            dict: 更新数据
        """
        return {
            "status": status.value,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    @staticmethod
    def update_result(task: dict, result: Any) -> dict:
        """
        更新任务结果
        
        Args:
            task: 任务数据
            result: 任务结果
            
        Returns:
            dict: 更新数据
        """
        return {
            "status": TaskStatus.COMPLETED.value,
            "result": result,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    @staticmethod
    def update_error(task: dict, error: str) -> dict:
        """
        更新任务错误
        
        Args:
            task: 任务数据
            error: 错误信息
            
        Returns:
            dict: 更新数据
        """
        return {
            "status": TaskStatus.FAILED.value,
            "error": error,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        } 