# Video Service

视频模型调用服务是 SciTiger AI模型调用微服务体系的一部分，支持通过API调用各种视频生成模型，包括阿里云通义万相、智谱AI等。

## 功能特性

- 支持多种视频生成模型
- 异步任务处理
- 任务状态跟踪和结果获取
- 统一的API接口
- 集成认证系统
- 自动下载和保存生成的视频

## 支持的模型

### 阿里云通义万相视频模型

- wanx2.1-t2v-turbo：通义万相文本生成视频-快速版
- wanx2.1-t2v-plus：通义万相文本生成视频-高质量版
- wanx2.1-i2v-turbo：通义万相图生视频(基于首帧)-快速版
- wanx2.1-i2v-plus：通义万相图生视频(基于首帧)-高质量版
- wanx2.1-kf2v-plus：通义万相首尾帧生成视频

### 智谱AI视频模型

- cogvideox-2：CogVideoX文本生成视频-标准版
- cogvideox-flash：CogVideoX文本生成视频-快速版
- viduq1-text：Vidu文本生成视频
- viduq1-image：Vidu图像生成视频
- viduq1-start-end：Vidu首尾帧生成视频
- vidu2-image：Vidu V2图像生成视频
- vidu2-start-end：Vidu V2首尾帧生成视频
- vidu2-reference：Vidu V2参考主体生成视频

## 实现说明

本服务使用异步方式调用各种视频生成API。流程如下：

1. 服务接收用户请求并创建任务记录
2. 使用异步方式调用相应提供商的API
3. 获取API返回的任务ID
4. 轮询任务状态直到完成或失败
5. 下载生成的视频并保存到本地 `data/videos` 目录
6. 返回处理结果给用户，包括原始视频URL和本地保存路径

### 视频保存

- 生成的视频会自动下载并保存到 `data/videos` 目录
- 文件名格式：`{提供商}_{时间戳}_{索引}_{随机ID}.mp4`
- 任务结果中会包含视频的原始URL和本地保存路径
- 提供商返回的视频URL有效期有限，但本地保存的视频永久有效

## 快速开始

### 环境准备

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量

复制`.env.example`为`.env`，并根据实际情况修改配置：

```bash
cp .env.example .env
```

主要配置项：

- `MONGODB_URL`：MongoDB连接地址
- `REDIS_URL`：Redis连接地址（用于Celery）
- `ALIYUN_API_KEY`：阿里云API密钥
- `ZHIPUAI_API_KEY`：智谱AI API密钥

### 启动服务

1. 启动API服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002  --reload
```

2. 启动Celery Worker

```bash
celery -A app.core.celery_app worker --loglevel=info
```

## API使用

### 创建视频生成任务 - 阿里云通义万相文本生成视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx2.1-t2v-turbo",
    "provider": "aliyun",
    "parameters": {
      "prompt": "一只可爱的小猫咪在草地上玩耍",
      "negative_prompt": "模糊, 扭曲, 低质量",
      "duration": 5,
      "resolution": "720P"
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 阿里云通义万相高质量视频生成

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx2.1-t2v-plus",
    "provider": "aliyun",
    "parameters": {
      "prompt": "宇航员在月球上行走，高清，写实风格",
      "negative_prompt": "模糊, 低质量",
      "duration": 5,
      "resolution": "720P",
      "prompt_extend": true
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 阿里云通义万相图像生成视频(基于首帧)

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx2.1-i2v-turbo",
    "provider": "aliyun",
    "parameters": {
      "prompt": "使图片动起来，高清效果",
      "img_url": "https://example.com/source-image.jpg",
      "duration": 5,
      "resolution": "720P"
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 阿里云通义万相首尾帧生成视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx2.1-kf2v-plus",
    "provider": "aliyun",
    "parameters": {
      "prompt": "一个女孩从森林中漫步而出，脸上洋溢着喜悦的笑容",
      "first_frame_url": "https://example.com/first-frame.jpg",
      "last_frame_url": "https://example.com/last-frame.jpg",
      "resolution": "720P",
      "obj_or_bg": ["obj", "bg"]
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 智谱AI CogVideoX文本生成视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cogvideox-2",
    "provider": "zhipuai",
    "parameters": {
      "prompt": "一只狗狗在海边奔跑，阳光明媚，细节丰富，4K",
      "quality": "quality",
      "size": "1080x1920",
      "fps": 30
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 智谱AI CogVideoX图生视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cogvideox-2",
    "provider": "zhipuai",
    "parameters": {
      "prompt": "让图片动起来，高品质动态效果",
      "image_url": "https://example.com/source-image.jpg",
      "quality": "quality",
      "size": "1080x1920",
      "fps": 30
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 智谱AI Vidu文生视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "viduq1-text",
    "provider": "zhipuai",
    "parameters": {
      "prompt": "比得兔开小汽车，游走在马路上，脸上的表情充满开心喜悦",
      "style": "anime",
      "duration": "5",
      "size": "1080x1920",
      "movement_amplitude": "auto"
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 智谱AI Vidu图生视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vidu2-image",
    "provider": "zhipuai",
    "parameters": {
      "image_url": "https://example.com/source-image.jpg",
      "prompt": "增加动态效果，高质量",
      "duration": "4",
      "size": "1080x1920",
      "movement_amplitude": "auto"
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 智谱AI Vidu首尾帧生成视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vidu2-start-end",
    "provider": "zhipuai",
    "parameters": {
      "image_url": ["https://example.com/first-frame.jpg", "https://example.com/last-frame.jpg"],
      "prompt": "平滑过渡，高质量生成",
      "duration": "4",
      "size": "720x480",
      "movement_amplitude": "medium",
      "with_audio": true
    },
    "is_async": true
  }'
```

### 创建视频生成任务 - 智谱AI Vidu参考主体生成视频

```bash
curl -X POST "http://localhost:8002/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vidu2-reference",
    "provider": "zhipuai",
    "parameters": {
      "image_url": ["https://example.com/reference-image1.jpg", "https://example.com/reference-image2.jpg"],
      "prompt": "根据参考图像生成视频，保持角色特征",
      "duration": "4",
      "aspect_ratio": "16:9",
      "size": "720x480",
      "movement_amplitude": "auto",
      "with_audio": true
    },
    "is_async": true
  }'
```

### 查询任务状态

```bash
curl "http://localhost:8002/api/v1/tasks/{task_id}/status"
```

### 获取任务结果

```bash
curl "http://localhost:8002/api/v1/tasks/{task_id}/result"
```

任务结果示例：

```json
{
  "success": true,
  "message": "获取任务结果成功",
  "results": {
    "task_id": "685008a3404376ca4660b24a",
    "status": "completed",
    "result": {
      "id": "d9d2877c-06b8-9df5-8246-2dadbedcf9ba",
      "model": "wanx2.1-t2v-turbo",
      "created": "2025-06-16 20:08:58",
      "videos": [
        {
          "index": 0,
          "url": "https://dashscope-result.oss-cn-beijing.aliyuncs.com/videos/2025/06/16/xxxx-xxxx-xxxx.mp4",
          "local_path": "/Users/alanfu/Documents/projects/sciTigerService/video-service/data/videos/aliyun_20250616_200858_0_a1b2c3d4.mp4",
          "duration": 5
        }
      ],
      "prompt": "宇航员在月球上行走，高清，写实风格",
      "actual_prompt": "宇航员在月球上行走，写实风格，高清画质，太空探索，严肃氛围，细节丰富，专业视频效果",
      "resolution": "720P",
      "usage": {
        "video_count": 1,
        "video_duration": 5,
        "video_ratio": "standard"
      }
    },
    "error": null
  }
}
```

## 开发指南

### 项目结构

```
video-service/
├── app/                           # 应用主目录
│   ├── api/                       # API路由定义
│   │   ├── __init__.py            # API路由注册
│   │   ├── health.py              # 健康检查接口
│   │   └── tasks.py               # 任务管理接口
│   ├── core/                      # 核心功能模块
│   │   ├── __init__.py
│   │   ├── config.py              # 配置管理
│   │   ├── security.py            # 安全和认证
│   │   ├── celery_app.py          # Celery应用实例
│   │   └── logging.py             # 日志配置
│   ├── db/                        # 数据库相关
│   │   ├── __init__.py
│   │   ├── mongodb.py             # MongoDB连接和操作
│   │   └── repositories/          # 数据访问层
│   │       ├── __init__.py
│   │       └── task_repository.py # 任务数据访问
│   ├── models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── task.py                # 任务模型
│   │   └── user.py                # 用户模型
│   ├── schemas/                   # Pydantic模式
│   │   ├── __init__.py
│   │   ├── task.py                # 任务相关模式
│   │   └── common.py              # 通用模式
│   ├── services/                  # 业务逻辑服务
│   │   ├── __init__.py
│   │   ├── task_service.py        # 任务管理服务
│   │   └── model_providers/       # 模型提供商实现
│   │       ├── __init__.py
│   │       ├── base.py            # 基础接口
│   │       └── [provider_name].py # 具体提供商实现
│   ├── utils/                     # 工具函数
│   │   ├── __init__.py
│   │   └── helpers.py             # 辅助函数
│   │   └── response.py            # 统一响应格式
│   ├── worker/                    # 后台任务处理
│   │   ├── __init__.py
│   │   └── tasks.py               # Celery任务定义
│   ├── middleware/                # 中间件
│   │   ├── __init__.py
│   │   └── auth.py                # 认证中间件
│   └── main.py                    # 应用入口
├── .env.example                   # 环境变量示例
├── .gitignore                     # Git忽略文件
├── requirements.txt               # 依赖列表
└── README.md                      # 项目说明
```

### 添加新的模型提供商

要添加新的模型提供商，请执行以下步骤：

1. 在 `app/services/model_providers` 目录中创建新的提供商类
2. 实现 `ModelProvider` 抽象类定义的接口
3. 在 `app/services/model_providers/__init__.py` 中导入和注册新的提供商

示例：

```python
# app/services/model_providers/new_provider.py
from .base import ModelProvider, register_provider

@register_provider
class NewProvider(ModelProvider):
    @property
    def provider_name(self) -> str:
        return "new_provider"
    
    @property
    def supported_models(self) -> List[str]:
        return ["new-model-1", "new-model-2"]
    
    async def call_model(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # 实现模型调用逻辑
        pass
    
    async def validate_parameters(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # 实现参数验证逻辑
        pass
```

然后在 `app/services/model_providers/__init__.py` 中添加导入：

```python
# 添加到文件末尾
from . import new_provider  # 新提供商
```

