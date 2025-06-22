import httpx
import json
import time
import os
import asyncio
from pathlib import Path
from datetime import datetime
import uuid
from typing import Dict, Any, List, Optional

from .base import ModelProvider
from ...core.logging import logger
from ...core.config import settings


class AliyunProvider(ModelProvider):
    """阿里云模型提供商"""
    
    @property
    def provider_name(self) -> str:
        """提供商名称"""
        return "aliyun"
    
    @property
    def supported_models(self) -> List[str]:
        """从配置文件中获取支持的模型列表"""
        return settings.PROVIDER_SUPPORTED_MODELS.get("aliyun", [
            "wanx2.1-t2i-turbo", "wanx2.1-t2i-plus", "wanx2.0-t2i-turbo"
        ])
    
    async def validate_parameters(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证模型参数
        
        Args:
            model: 模型名称
            parameters: 模型参数
            
        Returns:
            Dict[str, Any]: 验证后的参数
        """
        # 检查模型是否支持
        if model not in self.supported_models:
            supported = ", ".join(self.supported_models)
            raise ValueError(f"Model '{model}' not supported. Supported models: {supported}")
        
        # 验证必需参数
        if "prompt" not in parameters:
            raise ValueError("Parameter 'prompt' is required")
        
        # 首先复制所有原始参数，保留自定义参数
        validated = parameters.copy()
        
        # 添加模型信息
        validated["model"] = model
        
        # 处理并规范化一些核心参数，但不删除其他自定义参数
        
        # 处理尺寸参数
        if "size" in validated:
            # 确保尺寸格式正确，例如 "1024*1024"
            validated["size"] = validated["size"]
        else:
            validated["size"] = "1024*1024"
            
        # 处理生成数量参数
        if "n" in validated:
            validated["n"] = min(max(int(validated["n"]), 1), 4)
        else:
            validated["n"] = 1
            
        # 处理负面提示词
        if "negative_prompt" not in validated:
            validated["negative_prompt"] = ""
            
        # 处理风格参数
        if "style" not in validated:
            validated["style"] = "<auto>"
            
        # 处理参考图像相关参数
        if "ref_img" in validated:
            # 如果提供了参考图像，确保有相关参数
            if "ref_strength" not in validated:
                validated["ref_strength"] = 1.0
            if "ref_mode" not in validated:
                validated["ref_mode"] = "repaint"
                
        # 处理seed参数，确保是整数
        if "seed" in validated:
            validated["seed"] = int(validated["seed"])
            
        return validated
    
    async def download_image(self, url: str, save_path: str) -> str:
        """
        下载图像并保存到本地
        
        Args:
            url: 图像URL
            save_path: 保存路径
            
        Returns:
            str: 本地文件路径
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 下载图像
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # 保存图像
                with open(save_path, "wb") as f:
                    f.write(response.content)
                    
                logger.info(f"Image downloaded and saved to {save_path}")
                return save_path
        except Exception as e:
            logger.error(f"Error downloading image: {str(e)}")
            return ""
      
    async def call_model(self, model: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用阿里云图像模型
        
        Args:
            model: 模型名称
            parameters: 模型参数
            
        Returns:
            Dict[str, Any]: 模型调用结果
        """
        # 验证参数
        validated_params = await self.validate_parameters(model, parameters)
        
        # 获取API密钥和URL
        api_key = settings.ALIYUN_API_KEY
        api_url = settings.ALIYUN_API_URL
        
        if not api_key:
            raise ValueError("Aliyun API key not configured")
        
        if not api_url:
            # 使用默认API URL
            api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        
        logger.info(f"Calling Aliyun image model {model}")
        
        try:
            # 准备请求数据
            request_data = {
                "model": validated_params["model"],
                "input": {
                    "prompt": validated_params["prompt"]
                },
                "parameters": {}
            }
            
            # 添加负面提示词
            if validated_params.get("negative_prompt"):
                request_data["input"]["negative_prompt"] = validated_params["negative_prompt"]
                
            # 添加参考图像
            if validated_params.get("ref_img"):
                request_data["input"]["ref_image"] = validated_params["ref_img"]
            
            # 将所有除了特定排除参数之外的参数添加到请求的parameters中
            exclude_keys = ["model", "prompt", "negative_prompt", "ref_img"]  # 这些参数不属于parameters部分
            
            # 特别处理某些参数
            special_params = {
                "size": "size",
                "n": "n",
                "style": "style",
                "seed": "seed",
                "ref_strength": "ref_strength",
                "ref_mode": "ref_mode"
            }
            
            # 添加特殊参数到parameters中
            for param_name, api_param in special_params.items():
                if param_name in validated_params:
                    request_data["parameters"][api_param] = validated_params[param_name]
                    
            # 添加其他自定义参数
            for key, value in validated_params.items():
                if key not in exclude_keys and key not in special_params:
                    request_data["parameters"][key] = value
                    
            # 记录完整的请求参数
            logger.info(f"Request data for Aliyun API: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 准备请求头，添加异步调用标识
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-DashScope-Async": "enable",  # 启用异步调用
                "X-DashScope-DataInspection": "disable",  # 禁止数据检查
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
                
                # 获取任务ID - 从output字段中获取
                output = task_result.get("output", {})
                task_id = output.get("task_id")
                if not task_id:
                    # 记录完整的响应以便调试
                    logger.error(f"Failed to get task_id from response: {task_result}")
                    raise ValueError(f"Failed to get task_id from response: {task_result}")
                
                logger.info(f"Created Aliyun async task with ID: {task_id}")
                
                # 轮询任务结果 - 增加轮询次数和间隔时间
                max_retries = 120  # 最多等待120次 (增加到2分钟)
                retry_interval = 15  # 每次等待15秒 (增加间隔)
                
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
                    
                    # 记录完整的任务状态响应
                    logger.info(f"Task {task_id} status response: {json.dumps(task_status, ensure_ascii=False)}")
                    
                    # 检查任务状态 - 尝试从不同位置获取状态
                    task_status_value = task_status.get("task_status", "")
                    if not task_status_value and "output" in task_status:
                        task_status_value = task_status["output"].get("task_status", "")
                    
                    logger.info(f"Task {task_id} status: {task_status_value}")
                    
                    # 如果任务完成或失败，返回结果
                    if task_status_value in ["SUCCEEDED", "COMPLETE", "SUCCESS"]:
                        # 格式化响应结果并下载图片
                        result = await self._format_response_and_download_images(task_status, validated_params)
                        return result
                    elif task_status_value in ["FAILED", "CANCELLED", "ERROR"]:
                        error_msg = task_status.get("message", "Unknown error")
                        if "output" in task_status and "message" in task_status["output"]:
                            error_msg = task_status["output"]["message"]
                        raise ValueError(f"Task failed: {error_msg}")
                
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
    
    async def _format_response_and_download_images(self, api_response: Dict[str, Any], original_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化阿里云API响应并下载图片
        
        Args:
            api_response: API原始响应
            original_params: 原始参数
            
        Returns:
            Dict[str, Any]: 格式化的响应，包含本地图片路径
        """
        # 提取输出内容（异步任务结果的结构与同步不同）
        output = api_response.get("output", {})
        if not output and "result" in api_response:
            output = api_response.get("result", {})
        
        # 构建统一格式的响应
        formatted_response = {
            "id": api_response.get("request_id", api_response.get("task_id", str(uuid.uuid4()))),
            "model": original_params.get("model", ""),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "images": []
        }
        
        # 添加图像结果并下载图片
        results = []
        if "results" in output:
            results = output["results"]
        # 适配不同的响应格式
        elif "task_metrics" in output and "SUCCEEDED" in output.get("task_metrics", {}):
            # 可能结果在另一个位置
            if "result" in api_response:
                results = api_response["result"].get("results", [])
        
        # 设置图片保存目录
        images_dir = Path(settings.DATA_DIR) / "images" / "aliyun"
        os.makedirs(images_dir, exist_ok=True)
        
        # 下载并保存图片
        for i, result in enumerate(results):
            image_url = result.get("url", "")
            if not image_url:
                continue
                
            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}_{i}_{uuid.uuid4().hex[:8]}.png"
            local_path = os.path.join(images_dir, file_name)
            
            # 下载图片
            saved_path = await self.download_image(image_url, local_path)
            
            # 添加到响应中
            image_data = {
                "index": i,
                "url": image_url,  # 保留原始URL
                "local_path": saved_path,  # 添加本地路径
                "seed": result.get("seed", None)
            }
            formatted_response["images"].append(image_data)
        
        # 添加原始提示词
        formatted_response["prompt"] = original_params.get("prompt", "")
        if "negative_prompt" in original_params:
            formatted_response["negative_prompt"] = original_params["negative_prompt"]
            
        # 添加图像尺寸信息
        if "size" in original_params:
            size_parts = original_params["size"].split("*")
            if len(size_parts) == 2:
                try:
                    formatted_response["width"] = int(size_parts[0])
                    formatted_response["height"] = int(size_parts[1])
                except ValueError:
                    formatted_response["size"] = original_params["size"]
            else:
                formatted_response["size"] = original_params["size"]
        else:
            formatted_response["width"] = 1024
            formatted_response["height"] = 1024
            
        return formatted_response


# 导入asyncio
import asyncio

# 注册提供商
from . import register_provider
register_provider(AliyunProvider) 