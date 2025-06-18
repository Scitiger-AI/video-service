from fastapi import APIRouter
from . import health, tasks, models

api_router = APIRouter()

# 添加健康检查路由
api_router.include_router(health.router, prefix="/health", tags=["health"])

# 添加任务管理路由
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

# 添加模型查询路由
api_router.include_router(models.router, prefix="/models", tags=["models"]) 