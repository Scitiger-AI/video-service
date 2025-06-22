from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse
from typing import Optional
import os
from pathlib import Path
from ..core.logging import logger
from ..core.config import settings

router = APIRouter()

@router.get("/{file_name}")
async def download_file(
    file_name: str,
    request: Request
):
    """
    下载文件
    
    Args:
        file_name: 文件名
        request: 请求对象
    
    Returns:
        FileResponse: 文件响应
    """
    try:
        # 在数据目录中查找文件
        data_dir = Path(settings.DATA_DIR)
        
        # 首先检查是否直接存在于videos目录下
        videos_dir = data_dir / "videos"
        file_path = videos_dir / file_name
        
        if not file_path.exists():
            # 如果不存在，检查子目录
            for provider_dir in ["aliyun", "zhipuai"]:
                provider_path = videos_dir / provider_dir / file_name
                if provider_path.exists():
                    file_path = provider_path
                    break
            
            # 如果仍然找不到，在整个数据目录中递归查找
            if not file_path.exists():
                matching_files = list(data_dir.glob(f"**/{file_name}"))
                
                if not matching_files:
                    logger.error(f"文件未找到: {file_name}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"File not found: {file_name}"
                    )
                
                file_path = matching_files[0]
            
        logger.info(f"提供文件下载: {file_path}")
        
        # 根据文件类型设置适当的媒体类型
        media_type = "video/mp4"  # 默认类型
        file_extension = file_path.suffix.lower()
        
        if file_extension == ".mp4":
            media_type = "video/mp4"
        elif file_extension == ".webm":
            media_type = "video/webm"
        elif file_extension == ".mov":
            media_type = "video/quicktime"
        elif file_extension == ".avi":
            media_type = "video/x-msvideo"
        elif file_extension == ".mkv":
            media_type = "video/x-matroska"
        elif file_extension == ".flv":
            media_type = "video/x-flv"
        elif file_extension in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_extension == ".png":
            media_type = "image/png"
        elif file_extension == ".gif":
            media_type = "image/gif"
        else:
            media_type = "application/octet-stream"
        
        # 返回文件
        return FileResponse(
            path=str(file_path),
            filename=file_name,
            media_type=media_type
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理文件下载请求时出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process download request: {str(e)}"
        ) 