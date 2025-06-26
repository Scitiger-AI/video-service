import asyncio
import time
import uuid
import httpx
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ...core.config import settings
from ...core.logging import logger
from .base import ModelProvider
from . import register_provider
from pathlib import Path


@register_provider
class AliyunProvider(ModelProvider):
    """阿里云视频模型提供商"""
    
    @property
    def provider_name(self) -> str:
        return "aliyun"
    
    @property
    def supported_models(self) -> List[str]:
        """从配置文件中获取支持的模型列表"""
        return settings.PROVIDER_SUPPORTED_MODELS.get("aliyun", [
            "wanx2.1-t2v-turbo",  # 通义万相文本生成视频-快速版
            "wanx2.1-t2v-plus",   # 通义万相文本生成视频-高质量版
            "wanx2.1-i2v-turbo",  # 通义万相图生视频-快速版
            "wanx2.1-i2v-plus",   # 通义万相图生视频-高质量版
            "wanx2.1-kf2v-plus",  # 通义万相首尾帧生成视频
        ])
    
    async def validate_parameters(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证模型参数"""
        # 复制参数，避免修改原始参数
        validated = parameters.copy()
        
        # 检查模型是否支持
        if model not in self.supported_models:
            supported = ", ".join(self.supported_models)
            raise ValueError(f"Model '{model}' not supported. Supported models: {supported}")
        
        # 确定模型类型并添加到validated字典中
        validated["model_type"] = self._determine_model_type(model)
        
        # 检查必要参数
        if "prompt" not in validated:
            # 首尾帧生成视频可以不需要提示词
            if validated["model_type"] != "keyframe_to_video":
                raise ValueError("Missing required parameter: prompt")
        
        # 图生视频需要图像
        if validated["model_type"] == "image_to_video":
            if "img_url" not in validated and "source_image" not in validated:
                raise ValueError("Image-to-video model requires img_url parameter")
            # 兼容处理，如果使用的是source_image参数，统一转换为img_url
            if "source_image" in validated and "img_url" not in validated:
                validated["img_url"] = validated["source_image"]
                del validated["source_image"]
        
        # 首尾帧生成视频需要首尾帧图像
        if validated["model_type"] == "keyframe_to_video":
            if "first_frame_url" not in validated:
                raise ValueError("Keyframe-to-video model requires first_frame_url parameter")
            if "last_frame_url" not in validated:
                raise ValueError("Keyframe-to-video model requires last_frame_url parameter")
        
        # 设置默认参数
        if "duration" not in validated:
            validated["duration"] = 5  # 默认5秒视频
        else:
            # 确保持续时间在合理范围内
            if validated["model_type"] in ["text_to_video", "image_to_video"]:
                # T2V和I2V模型支持3-5秒
                validated["duration"] = min(max(int(validated["duration"]), 3), 5)
            else:
                # KF2V模型固定为5秒
                validated["duration"] = 5
        
        # 设置分辨率
        if "resolution" not in validated:
            if "size" in validated:
                # 兼容处理，如果使用了size参数
                size = validated["size"]
                if size == "1280*720":
                    validated["resolution"] = "720P"
                elif size == "720*1280":
                    validated["resolution"] = "720P"  # 但实际是9:16比例
                elif size == "960*960":
                    validated["resolution"] = "720P"  # 但实际是1:1比例
                elif size == "832*1088":
                    validated["resolution"] = "720P"  # 但实际是3:4比例
                elif size == "1088*832":
                    validated["resolution"] = "720P"  # 但实际是4:3比例
                elif size == "832*480":
                    validated["resolution"] = "480P"  # 16:9比例
                elif size == "480*832":
                    validated["resolution"] = "480P"  # 9:16比例
                elif size == "624*624":
                    validated["resolution"] = "480P"  # 1:1比例
                else:
                    validated["resolution"] = "720P"  # 默认720P
                
                # 删除不标准的参数
                del validated["size"]
            else:
                # 根据模型类型设置默认分辨率
                if validated["model_type"] == "text_to_video":
                    # T2V模型 turbo支持480P和720P，plus只支持720P
                    if model.endswith("turbo"):
                        validated["resolution"] = "720P"
                    else:
                        validated["resolution"] = "720P"
                elif validated["model_type"] == "image_to_video":
                    # I2V模型 turbo支持480P和720P，plus只支持720P
                    if model.endswith("turbo"):
                        validated["resolution"] = "720P"
                    else:
                        validated["resolution"] = "720P"
                else:
                    # KF2V模型只支持720P
                    validated["resolution"] = "720P"
        
        # 添加提示词智能改写参数
        if "prompt_extend" not in validated:
            validated["prompt_extend"] = True
        
        # 设置随机种子
        if "seed" not in validated:
            validated["seed"] = -1  # 使用随机种子
        
        return validated
    
    def _determine_model_type(self, model: str) -> str:
        """
        根据模型名称确定模型类型
        
        Args:
            model: 模型名称
            
        Returns:
            str: 模型类型 (text_to_video, image_to_video, keyframe_to_video)
        """
        # 这里使用更通用的判断方式，不仅限于特定版本号
        if "t2v" in model.lower():
            return "text_to_video"
        elif "i2v" in model.lower():
            return "image_to_video"
        elif "kf2v" in model.lower() or "keyframe" in model.lower():
            return "keyframe_to_video"
        else:
            # 默认返回文本生成视频类型
            logger.warning(f"无法确定模型 {model} 的类型，默认使用 text_to_video 类型")
            return "text_to_video"
    
    async def ensure_file_in_temporary_storage(self, file_url: str, model: str) -> str:
        """
        确保文件已上传到阿里云临时存储空间
        
        Args:
            file_url: 原始文件URL
            model: 模型名称
            
        Returns:
            str: 阿里云临时存储空间的URL
        """
        # 如果已经是OSS URL，直接返回
        if file_url.startswith("oss://"):
            return file_url
        
        # 否则上传到临时存储空间
        return await self.upload_file_to_temporary_storage(file_url, model)
    
    async def upload_file_to_temporary_storage(self, file_url: str, model: str) -> str:
        """
        将文件上传到阿里云临时存储空间
        
        Args:
            file_url: 文件URL
            model: 模型名称
            
        Returns:
            str: 阿里云临时存储空间的URL
        """
        logger.info(f"上传文件到阿里云临时存储空间: {file_url}")
        
        # 获取API密钥
        api_key = settings.ALIYUN_API_KEY
        
        if not api_key:
            raise ValueError("Aliyun API key not configured")
        
        try:
            # 步骤1: 获取上传凭证
            upload_policy_url = "https://dashscope.aliyuncs.com/api/v1/uploads"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            params = {
                "action": "getPolicy",
                "model": model
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    upload_policy_url,
                    headers=headers,
                    params=params
                )
                
                response.raise_for_status()
                policy_data = response.json().get('data', {})
                
                logger.info(f"获取上传凭证成功: {json.dumps(policy_data, ensure_ascii=False)}")
                
                # 步骤2: 下载原始文件
                # 创建临时目录
                temp_dir = Path(settings.DATA_DIR) / "temp"
                os.makedirs(temp_dir, exist_ok=True)
                
                # 生成临时文件名
                file_ext = self._get_file_extension_from_url(file_url)
                temp_filename = f"temp_{uuid.uuid4().hex}{file_ext}"
                temp_file_path = str(temp_dir / temp_filename)
                
                # 下载文件
                file_response = await client.get(file_url)
                file_response.raise_for_status()
                
                # 保存文件到临时文件
                with open(temp_file_path, "wb") as f:
                    f.write(file_response.content)
                
                logger.info(f"文件已下载到临时文件: {temp_file_path}")
                
                # 步骤3: 上传文件到阿里云OSS
                file_name = Path(temp_file_path).name
                key = f"{policy_data['upload_dir']}/{file_name}"
                
                with open(temp_file_path, 'rb') as file:
                    files = {
                        'OSSAccessKeyId': (None, policy_data['oss_access_key_id']),
                        'Signature': (None, policy_data['signature']),
                        'policy': (None, policy_data['policy']),
                        'x-oss-object-acl': (None, policy_data['x_oss_object_acl']),
                        'x-oss-forbid-overwrite': (None, policy_data['x_oss_forbid_overwrite']),
                        'key': (None, key),
                        'success_action_status': (None, '200'),
                        'file': (file_name, file)
                    }
                    
                    upload_response = await client.post(
                        policy_data['upload_host'],
                        files=files
                    )
                    
                    upload_response.raise_for_status()
                    
                    # 删除临时文件
                    os.remove(temp_file_path)
                    
                    # 构造阿里云OSS URL
                    oss_url = f"oss://{key}"
                    
                    # 计算过期时间
                    expire_time = datetime.now() + timedelta(hours=48)
                    logger.info(f"文件已上传到阿里云临时存储空间: {oss_url}，有效期48小时，过期时间: {expire_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    return oss_url
                    
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"message": e.response.text}
                
            error_msg = f"Aliyun 上传文件API错误: {e.response.status_code}, {error_detail}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        except Exception as e:
            logger.error(f"上传文件到阿里云临时存储空间出错: {str(e)}")
            raise ValueError(f"上传文件到阿里云临时存储空间出错: {str(e)}")
    
    def _get_file_extension_from_url(self, url: str) -> str:
        """
        从URL中获取文件扩展名
        
        Args:
            url: 文件URL
            
        Returns:
            str: 文件扩展名，如 .jpg, .png 等
        """
        # 从URL中提取文件名
        path = url.split('?')[0]  # 移除查询参数
        filename = path.split('/')[-1]
        
        # 获取扩展名
        _, ext = os.path.splitext(filename)
        
        # 如果没有扩展名，默认为.jpg
        if not ext:
            ext = '.jpg'
        
        return ext
    
    async def call_model(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用阿里云视频生成模型
        
        Args:
            model: 模型名称
            parameters: 模型参数
            
        Returns:
            Dict[str, Any]: 模型调用结果
        """
        # 验证参数
        validated_params = await self.validate_parameters(model, parameters)
        
        # 获取API密钥
        api_key = settings.ALIYUN_API_KEY
        
        if not api_key:
            raise ValueError("Aliyun API key not configured")
        
        # 确定API URL
        api_url = settings.ALIYUN_API_URL
        
        if not api_url:
            # 根据模型类型设置不同的API URL
            if validated_params["model_type"] == "text_to_video" or validated_params["model_type"] == "image_to_video":
                api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
            elif validated_params["model_type"] == "keyframe_to_video":
                api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"
        
        logger.info(f"调用阿里云视频模型: {model}, 类型: {validated_params['model_type']}")
        logger.info(f"API URL: {api_url}")
        logger.info(f"参数: {json.dumps(validated_params, ensure_ascii=False)}")
        
        try:
            # 准备请求数据
            request_data = {
                "model": model,
                "input": {},
                "parameters": {}
            }
            
            # 处理所有可能的URL参数，确保它们都已上传到临时存储空间
            url_params_mapping = {
                "image_to_video": ["img_url", "source_image"],
                "keyframe_to_video": ["first_frame_url", "last_frame_url"]
            }
            
            # 根据模型类型获取需要处理的URL参数
            url_params = url_params_mapping.get(validated_params["model_type"], [])
            
            # 上传所有需要的文件到临时存储空间
            for param in url_params:
                if param in validated_params and validated_params[param]:
                    original_url = validated_params[param]
                    validated_params[param] = await self.ensure_file_in_temporary_storage(original_url, model)
                    logger.info(f"参数 {param} 的URL已更新: {original_url} -> {validated_params[param]}")
            
            # 添加输入参数
            if validated_params["model_type"] == "text_to_video":
                # 文本生成视频
                request_data["input"]["prompt"] = validated_params["prompt"]
                if "negative_prompt" in validated_params:
                    request_data["input"]["negative_prompt"] = validated_params["negative_prompt"]
            
            elif validated_params["model_type"] == "image_to_video":
                # 图像生成视频(基于首帧)
                request_data["input"]["prompt"] = validated_params.get("prompt", "")
                request_data["input"]["img_url"] = validated_params["img_url"]
            
            elif validated_params["model_type"] == "keyframe_to_video":
                # 首尾帧生成视频
                if "prompt" in validated_params:
                    request_data["input"]["prompt"] = validated_params["prompt"]
                request_data["input"]["first_frame_url"] = validated_params["first_frame_url"]
                request_data["input"]["last_frame_url"] = validated_params["last_frame_url"]
                
                # 首尾帧API还需要设置功能名称
                request_data["input"]["function"] = "image_reference"
            
            # 添加参数
            # 添加分辨率
            if "resolution" in validated_params:
                request_data["parameters"]["resolution"] = validated_params["resolution"]
            
            # 添加持续时间
            if "duration" in validated_params:
                request_data["parameters"]["duration"] = validated_params["duration"]
            
            # 添加提示词智能改写参数
            if "prompt_extend" in validated_params:
                request_data["parameters"]["prompt_extend"] = validated_params["prompt_extend"]
            
            # 添加种子
            if "seed" in validated_params and validated_params["seed"] > 0:
                request_data["parameters"]["seed"] = validated_params["seed"]
            
            # 添加首尾帧模型特殊参数
            if validated_params["model_type"] == "keyframe_to_video" and "obj_or_bg" in validated_params:
                request_data["parameters"]["obj_or_bg"] = validated_params["obj_or_bg"]
            
            # 记录完整的请求参数
            logger.info(f"Request data for Aliyun API: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 准备请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-DashScope-Async": "enable",  # 启用异步调用
                "X-DashScope-OssResourceResolve": "enable",  # 启用OSS资源解析，必须添加此参数以使用临时存储空间中的文件
            }
            
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
                output = task_result.get("output", {})
                task_id = output.get("task_id")
                if not task_id:
                    # 记录完整的响应以便调试
                    logger.error(f"Failed to get task_id from response: {task_result}")
                    raise ValueError(f"Failed to get task_id from response: {task_result}")
                
                logger.info(f"Created Aliyun async task with ID: {task_id}")
                
                # 轮询任务结果
                max_retries = 180  # 最多等待30分钟 (180次*10秒)
                retry_interval = 15  # 每次等待15秒
                
                for i in range(max_retries):
                    # 等待一段时间
                    await asyncio.sleep(retry_interval)
                    
                    # 查询任务状态
                    task_status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
                    status_response = await client.get(
                        task_status_url,
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                    
                    status_response.raise_for_status()
                    task_status = status_response.json()
                    
                    # 记录任务状态响应
                    logger.info(f"Task {task_id} status response: {json.dumps(task_status, ensure_ascii=False)}")
                    
                    # 检查任务状态
                    output = task_status.get("output", {})
                    task_status_value = output.get("task_status", "")
                    
                    logger.info(f"Task {task_id} status: {task_status_value}")
                    
                    # 如果任务完成或失败，返回结果
                    if task_status_value in ["SUCCEEDED", "COMPLETE", "SUCCESS"]:
                        # 格式化响应结果并下载视频
                        result = await self._format_response_and_download_video(task_status, validated_params)
                        return result
                    elif task_status_value in ["FAILED", "CANCELLED", "ERROR"]:
                        error_msg = output.get("message", "Unknown error")
                        error_code = output.get("code", "Unknown error code")
                        raise ValueError(f"Task failed: {error_code} - {error_msg}")
                
                # 超过最大重试次数
                raise ValueError(f"Task {task_id} did not complete within expected time")
                
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"message": e.response.text}
                
            error_msg = f"Aliyun API HTTP error: {e.response.status_code}, {error_detail}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        except Exception as e:
            logger.error(f"Error calling Aliyun model: {str(e)}")
            raise ValueError(f"Aliyun API error: {str(e)}")
    
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
        格式化阿里云API响应并下载视频
        
        Args:
            api_response: API原始响应
            original_params: 原始参数
            
        Returns:
            Dict[str, Any]: 格式化的响应，包含本地视频路径
        """
        # 提取输出内容
        output = api_response.get("output", {})
        
        # 构建统一格式的响应
        formatted_response = {
            "id": api_response.get("request_id", str(uuid.uuid4())),
            "model": original_params.get("model", ""),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "videos": []
        }
        
        # 获取视频结果
        video_url = output.get("video_url", "")
        
        if not video_url:
            logger.error(f"Failed to find video URL in response: {json.dumps(api_response, ensure_ascii=False)}")
            raise ValueError("Failed to find video URL in response")
            
        # 设置视频保存目录
        videos_dir = Path(settings.DATA_DIR) / "videos" / "aliyun"
        os.makedirs(videos_dir, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"aliyun_{timestamp}_0_{uuid.uuid4().hex[:8]}.mp4"
        local_path = str(videos_dir / file_name)
        
        # 下载视频
        saved_path = await self.download_video(video_url, local_path)
        
        # 添加到响应中
        video_data = {
            "index": 0,
            "url": video_url,  # 保留原始URL
            "local_path": saved_path,  # 添加本地路径
            "duration": original_params.get("duration", 5),
        }
        formatted_response["videos"].append(video_data)
        
        # 添加原始提示词
        if "prompt" in original_params:
            formatted_response["prompt"] = original_params["prompt"]
        
        # 添加实际使用的提示词（如果有）
        if "actual_prompt" in output:
            formatted_response["actual_prompt"] = output["actual_prompt"]
        elif "orig_prompt" in output and "actual_prompt" in output:
            formatted_response["prompt"] = output["orig_prompt"]
            formatted_response["actual_prompt"] = output["actual_prompt"]
        
        # 添加模型信息
        formatted_response["model"] = original_params.get("model", "")
        formatted_response["model_type"] = original_params.get("model_type", "")
        
        # 添加分辨率信息
        if "resolution" in original_params:
            formatted_response["resolution"] = original_params["resolution"]
        
        # 添加额外信息
        if "usage" in api_response:
            formatted_response["usage"] = api_response["usage"]
        
        return formatted_response 