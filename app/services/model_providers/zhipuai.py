import asyncio
import time
import uuid
import httpx
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from ...core.config import settings
from ...core.logging import logger
from .base import ModelProvider
from . import register_provider


@register_provider
class ZhipuAIProvider(ModelProvider):
    """智谱AI视频模型提供商"""
    
    @property
    def provider_name(self) -> str:
        return "zhipuai"
    
    @property
    def supported_models(self) -> List[str]:
        """从配置文件中获取支持的模型列表"""
        return settings.PROVIDER_SUPPORTED_MODELS.get("zhipuai", [
            "cogvideox-2",       # 文本生成视频-标准版
            "cogvideox-flash",   # 文本生成视频-快速版
            "viduq1-text",       # 文本生成视频
            "viduq1-image",      # 图像生成视频
            "viduq1-start-end",  # 首尾帧生成视频
            "vidu2-image",       # 图像生成视频V2
            "vidu2-start-end",   # 首尾帧生成视频V2
            "vidu2-reference"    # 参考主体生成视频V2
        ])
    
    async def validate_parameters(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证模型参数"""
        # 复制参数，避免修改原始参数
        validated = parameters.copy()
        
        # 检查模型是否支持
        if model not in self.supported_models:
            supported = ", ".join(self.supported_models)
            raise ValueError(f"Model '{model}' not supported. Supported models: {supported}")
        
        # 检查是什么类型的模型
        is_cogvideox = model.startswith("cogvideox")
        is_vidu_text = model == "viduq1-text"
        is_vidu_image = model in ["viduq1-image", "vidu2-image"]
        is_vidu_start_end = model in ["viduq1-start-end", "vidu2-start-end"]
        is_vidu_reference = model == "vidu2-reference"
        
        # 根据模型类型检查必要参数
        if is_cogvideox:
            # CogVideoX 模型需要提示词
            if "prompt" not in validated:
                raise ValueError("Parameter 'prompt' is required for CogVideoX models")
        
        elif is_vidu_text:
            # 文本生成视频需要提示词
            if "prompt" not in validated:
                raise ValueError("Parameter 'prompt' is required for text-to-video models")
        
        elif is_vidu_image:
            # 图像生成视频需要图像
            if "image_url" not in validated and "source_image" not in validated:
                raise ValueError("Parameter 'image_url' is required for image-to-video models")
            
            # 兼容性处理，将source_image转为image_url
            if "source_image" in validated and "image_url" not in validated:
                validated["image_url"] = validated.pop("source_image")
            
            # 确保image_url是字符串(单图)或列表(多图)
            if isinstance(validated.get("image_url"), list) and len(validated["image_url"]) == 0:
                raise ValueError("'image_url' must not be an empty list")
        
        elif is_vidu_start_end:
            # 首尾帧生成视频需要两张图片
            if "image_url" not in validated or not isinstance(validated["image_url"], list) or len(validated["image_url"]) != 2:
                raise ValueError("Parameter 'image_url' must be a list containing exactly 2 images for start-end frame models")
        
        elif is_vidu_reference:
            # 参考主体生成视频需要参考图片
            if "image_url" not in validated or not isinstance(validated["image_url"], list) or len(validated["image_url"]) == 0:
                raise ValueError("Parameter 'image_url' must be a non-empty list of images for reference model")
            
            if len(validated["image_url"]) > 3:
                raise ValueError("Parameter 'image_url' can contain at most 3 images for reference model")
        
        return validated
    
    async def call_model(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用智谱AI视频生成模型
        
        Args:
            model: 模型名称
            parameters: 模型参数
            
        Returns:
            Dict[str, Any]: 模型调用结果
        """
        # 验证参数
        validated_params = await self.validate_parameters(model, parameters)
        
        # 获取API密钥
        api_key = settings.ZHIPUAI_API_KEY
        
        if not api_key:
            raise ValueError("ZhipuAI API key not configured")
        
        # 视频生成API URL - 统一使用官方文档中的地址
        api_url = "https://open.bigmodel.cn/api/paas/v4/videos/generations"
        
        # 准备请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # 根据不同模型准备请求数据
        is_cogvideox = model.startswith("cogvideox")
        is_vidu = model.startswith("vidu")
        
        logger.info(f"调用智谱AI视频模型: {model}")
        logger.info(f"API URL: {api_url}")
        
        try:
            # 准备请求数据
            request_data = {"model": model}
            
            if is_cogvideox:
                # CogVideoX 模型
                request_data["prompt"] = validated_params["prompt"]
                
                # 可选参数
                if "quality" in validated_params:
                    request_data["quality"] = validated_params["quality"]
                
                if "with_audio" in validated_params:
                    request_data["with_audio"] = validated_params["with_audio"]
                
                if "image_url" in validated_params:
                    request_data["image_url"] = validated_params["image_url"]
                
                if "size" in validated_params:
                    request_data["size"] = validated_params["size"]
                
                if "fps" in validated_params:
                    request_data["fps"] = validated_params["fps"]
                
                if "request_id" in validated_params:
                    request_data["request_id"] = validated_params["request_id"]
                
                if "user_id" in validated_params:
                    request_data["user_id"] = validated_params["user_id"]
            
            elif is_vidu:
                if model == "viduq1-text":
                    # 文本生成视频
                    request_data["prompt"] = validated_params["prompt"]
                    
                    # 可选参数
                    if "style" in validated_params:
                        request_data["style"] = validated_params["style"]
                    
                    if "duration" in validated_params:
                        request_data["duration"] = validated_params["duration"]
                    
                    if "aspect_ratio" in validated_params:
                        request_data["aspect_ratio"] = validated_params["aspect_ratio"]
                    
                    if "size" in validated_params:
                        request_data["size"] = validated_params["size"]
                    
                    if "movement_amplitude" in validated_params:
                        request_data["movement_amplitude"] = validated_params["movement_amplitude"]
                
                elif model in ["viduq1-image", "vidu2-image"]:
                    # 图像生成视频
                    if "image_url" in validated_params:
                        request_data["image_url"] = validated_params["image_url"]
                    
                    if "prompt" in validated_params:
                        request_data["prompt"] = validated_params["prompt"]
                    
                    if "duration" in validated_params:
                        request_data["duration"] = validated_params["duration"]
                    
                    if "size" in validated_params:
                        request_data["size"] = validated_params["size"]
                    
                    if "movement_amplitude" in validated_params:
                        request_data["movement_amplitude"] = validated_params["movement_amplitude"]
                    
                    if "with_audio" in validated_params:
                        request_data["with_audio"] = validated_params["with_audio"]
                
                elif model in ["viduq1-start-end", "vidu2-start-end"]:
                    # 首尾帧生成视频
                    if "image_url" in validated_params:
                        request_data["image_url"] = validated_params["image_url"]
                    
                    if "prompt" in validated_params:
                        request_data["prompt"] = validated_params["prompt"]
                    
                    if "duration" in validated_params:
                        request_data["duration"] = validated_params["duration"]
                    
                    if "size" in validated_params:
                        request_data["size"] = validated_params["size"]
                    
                    if "movement_amplitude" in validated_params:
                        request_data["movement_amplitude"] = validated_params["movement_amplitude"]
                    
                    if "with_audio" in validated_params:
                        request_data["with_audio"] = validated_params["with_audio"]
                
                elif model == "vidu2-reference":
                    # 参考主体生成视频
                    if "image_url" in validated_params:
                        request_data["image_url"] = validated_params["image_url"]
                    
                    if "prompt" in validated_params:
                        request_data["prompt"] = validated_params["prompt"]
                    
                    if "duration" in validated_params:
                        request_data["duration"] = validated_params["duration"]
                    
                    if "aspect_ratio" in validated_params:
                        request_data["aspect_ratio"] = validated_params["aspect_ratio"]
                    
                    if "size" in validated_params:
                        request_data["size"] = validated_params["size"]
                    
                    if "movement_amplitude" in validated_params:
                        request_data["movement_amplitude"] = validated_params["movement_amplitude"]
                    
                    if "with_audio" in validated_params:
                        request_data["with_audio"] = validated_params["with_audio"]
                
                # 通用参数
                if "request_id" in validated_params:
                    request_data["request_id"] = validated_params["request_id"]
                
                if "user_id" in validated_params:
                    request_data["user_id"] = validated_params["user_id"]
            
            # 记录完整的请求参数
            logger.info(f"Request data for ZhipuAI API: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 调用API创建任务
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    api_url,
                    json=request_data,
                    headers=headers
                )
                
                # 检查响应状态
                response.raise_for_status()
                task_result = response.json()
                
                # 记录完整的响应
                logger.info(f"Task creation response: {json.dumps(task_result, ensure_ascii=False)}")
                
                # 获取任务ID
                task_id = task_result.get("id")
                
                if not task_id:
                    raise ValueError(f"Failed to get task_id from response: {task_result}")
                
                # 轮询任务结果
                max_retries = 180  # 最多等待30分钟 (180次*10秒)
                retry_interval = 15  # 每次等待10秒
                
                # 任务结果查询API
                result_url = f"https://open.bigmodel.cn/api/paas/v4/async-result/{task_id}"
                
                for i in range(max_retries):
                    await asyncio.sleep(retry_interval)
                    
                    # 查询任务状态
                    status_response = await client.get(
                        result_url,
                        headers=headers
                    )
                    
                    status_response.raise_for_status()
                    task_status = status_response.json()
                    
                    logger.info(f"Task {task_id} status response: {json.dumps(task_status, ensure_ascii=False)}")
                    
                    # 检查任务状态
                    status = task_status.get("task_status")
                    
                    if status == "SUCCESS":
                        # 格式化响应结果并下载视频
                        result = await self._format_response_and_download_video(task_status, validated_params)
                        return result
                    elif status == "FAIL":
                        # 提取错误信息
                        error_msg = task_status.get("error", {}).get("message", "Unknown error")
                        raise ValueError(f"Task failed: {error_msg}")
                    elif status == "PROCESSING":
                        # 任务处理中，继续等待
                        logger.info(f"Task {task_id} is still processing, waiting...")
                    else:
                        # 未知状态
                        logger.warning(f"Unknown task status: {status}")
                
                # 超过最大重试次数
                raise ValueError(f"Task {task_id} did not complete within expected time")
                
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"message": e.response.text}
                
            error_msg = f"ZhipuAI API HTTP error: {e.response.status_code}, {error_detail}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        except Exception as e:
            logger.error(f"Error calling ZhipuAI model: {str(e)}")
            raise ValueError(f"ZhipuAI API error: {str(e)}")
    
    async def download_video(self, url: str, save_path: str) -> str:
        """
        下载视频并保存到本地
        
        Args:
            url: 视频URL
            save_path: 保存路径
            
        Returns:
            str: 本地文件路径
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 下载视频
            async with httpx.AsyncClient(timeout=600.0) as client:  # 增加超时时间，视频文件较大
                response = await client.get(url)
                response.raise_for_status()
                
                # 保存视频
                with open(save_path, "wb") as f:
                    f.write(response.content)
                    
                logger.info(f"Video downloaded and saved to {save_path}")
                return save_path
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            return ""
    
    async def _format_response_and_download_video(self, api_response: Dict[str, Any], original_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化智谱AI API响应并下载视频
        
        Args:
            api_response: API原始响应
            original_params: 原始参数
            
        Returns:
            Dict[str, Any]: 格式化的响应，包含本地视频路径
        """
        # 构建统一格式的响应
        formatted_response = {
            "id": api_response.get("request_id", str(uuid.uuid4())),
            "model": api_response.get("model", original_params.get("model", "")),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "videos": []
        }
        
        # 从响应中获取视频结果
        video_results = api_response.get("video_result", [])
        
        if not video_results:
            logger.error(f"Failed to find video results in response: {json.dumps(api_response, ensure_ascii=False)}")
            raise ValueError("Failed to find video results in response")
        
        # 设置视频保存目录
        video_dir = os.path.join(settings.DATA_DIR, "videos")
        os.makedirs(video_dir, exist_ok=True)
        
        # 下载所有视频
        for idx, video_info in enumerate(video_results):
            video_url = video_info.get("url", "")
            cover_image_url = video_info.get("cover_image_url", "")
            
            if not video_url:
                logger.warning(f"Empty video URL for video {idx}")
                continue
                
            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"zhipuai_{timestamp}_{idx}_{uuid.uuid4().hex[:8]}.mp4"
            local_path = os.path.join(video_dir, file_name)
            
            # 下载视频
            saved_path = await self.download_video(video_url, local_path)
            
            # 添加到响应中
            video_data = {
                "index": idx,
                "url": video_url,  # 保留原始URL
                "cover_image_url": cover_image_url,  # 封面图URL
                "local_path": saved_path  # 添加本地路径
            }
            
            # 添加可能的视频属性
            for attr in ["duration", "size", "fps"]:
                if attr in original_params:
                    video_data[attr] = original_params[attr]
            
            formatted_response["videos"].append(video_data)
        
        # 添加原始参数到响应中
        for key, value in original_params.items():
            if key not in formatted_response and key not in ["model"]:
                formatted_response[key] = value
        
        return formatted_response