import httpx
import json
import time
import os
import asyncio
import hmac
from hashlib import sha1
import base64
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from .base import ModelProvider
from ...core.logging import logger
from ...core.config import settings


class LiblibAIProvider(ModelProvider):
    """LiblibAI模型提供商"""
    
    @property
    def provider_name(self) -> str:
        """提供商名称"""
        return "liblibai"
    
    @property
    def supported_models(self) -> List[str]:
        """从配置文件中获取支持的模型列表"""
        return settings.PROVIDER_SUPPORTED_MODELS.get("liblibai", [
            "star-3-alpha-t2i", "star-3-alpha-i2i", "liblib-custom"
        ])
    
    def generate_signature(self, uri: str) -> Dict[str, str]:
        """
        生成LiblibAI API签名
        
        Args:
            uri: API URI地址
            
        Returns:
            Dict[str, str]: 签名参数
        """
        # 获取API密钥
        access_key = settings.LIBLIBAI_ACCESS_KEY
        secret_key = settings.LIBLIBAI_SECRET_KEY
        
        if not access_key or not secret_key:
            raise ValueError("LiblibAI API keys not configured")
        
        # 生成时间戳和随机字符串
        timestamp = str(int(time.time() * 1000))
        signature_nonce = str(uuid.uuid4())
        
        # 拼接请求数据
        content = '&'.join((uri, timestamp, signature_nonce))
        
        # 生成签名
        digest = hmac.new(secret_key.encode(), content.encode(), sha1).digest()
        # 移除为了补全base64位数而填充的尾部等号
        signature = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
        
        return {
            "AccessKey": access_key,
            "Signature": signature,
            "Timestamp": timestamp,
            "SignatureNonce": signature_nonce
        }
    
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
        
        # 首先复制所有原始参数，保留自定义参数
        validated = parameters.copy()
        
        # 添加模型信息
        validated["model"] = model
        
        # 根据不同模型类型验证和处理参数
        if model == "star-3-alpha-t2i":
            # 验证必需参数
            if "prompt" not in validated:
                raise ValueError("Parameter 'prompt' is required for Star-3 Alpha text-to-image")
                
            # 确保generateParams存在
            if "generateParams" not in validated:
                validated["generateParams"] = {}
                
            # 将prompt添加到generateParams
            if "prompt" not in validated["generateParams"]:
                validated["generateParams"]["prompt"] = validated["prompt"]
                
            # 设置默认参数
            if "aspectRatio" not in validated["generateParams"] and "imageSize" not in validated["generateParams"]:
                validated["generateParams"]["aspectRatio"] = "portrait"
                
            if "imgCount" not in validated["generateParams"]:
                validated["generateParams"]["imgCount"] = 1
                
            # 设置模板UUID
            if "templateUuid" not in validated:
                validated["templateUuid"] = "5d7e67009b344550bc1aa6ccbfa1d7f4"  # 星流Star-3 Alpha文生图固定模板
                
        elif model == "star-3-alpha-i2i":
            # 验证必需参数
            if "prompt" not in validated:
                raise ValueError("Parameter 'prompt' is required for Star-3 Alpha image-to-image")
                
            if "sourceImage" not in validated:
                raise ValueError("Parameter 'sourceImage' is required for Star-3 Alpha image-to-image")
                
            # 确保generateParams存在
            if "generateParams" not in validated:
                validated["generateParams"] = {}
                
            # 将参数添加到generateParams
            if "prompt" not in validated["generateParams"]:
                validated["generateParams"]["prompt"] = validated["prompt"]
                
            if "sourceImage" not in validated["generateParams"]:
                validated["generateParams"]["sourceImage"] = validated["sourceImage"]
                
            # 设置默认参数
            if "width" not in validated["generateParams"]:
                validated["generateParams"]["width"] = 768
                
            if "height" not in validated["generateParams"]:
                validated["generateParams"]["height"] = 1024
                
            if "imgCount" not in validated["generateParams"]:
                validated["generateParams"]["imgCount"] = 1
                
            # 设置模板UUID
            if "templateUuid" not in validated:
                validated["templateUuid"] = "07e00af4fc464c7ab55ff906f8acf1b7"  # 星流Star-3 Alpha图生图固定模板
        
        elif model == "liblib-custom":
            # 验证必需参数
            if "checkPointId" not in validated:
                raise ValueError("Parameter 'checkPointId' is required for LiblibAI custom model")
                
            if "prompt" not in validated:
                raise ValueError("Parameter 'prompt' is required for LiblibAI custom model")
                
            # 确保generateParams存在
            if "generateParams" not in validated:
                validated["generateParams"] = {}
                
            # 将参数添加到generateParams
            if "checkPointId" not in validated["generateParams"]:
                validated["generateParams"]["checkPointId"] = validated["checkPointId"]
                
            if "prompt" not in validated["generateParams"]:
                validated["generateParams"]["prompt"] = validated["prompt"]
                
            # 设置默认参数
            if "sampler" not in validated["generateParams"]:
                validated["generateParams"]["sampler"] = 15  # DPM++ 2M Karras
                
            if "steps" not in validated["generateParams"]:
                validated["generateParams"]["steps"] = 20
                
            if "cfgScale" not in validated["generateParams"]:
                validated["generateParams"]["cfgScale"] = 7
                
            if "width" not in validated["generateParams"]:
                validated["generateParams"]["width"] = 768
                
            if "height" not in validated["generateParams"]:
                validated["generateParams"]["height"] = 1024
                
            if "imgCount" not in validated["generateParams"]:
                validated["generateParams"]["imgCount"] = 1
                
            if "seed" not in validated["generateParams"]:
                validated["generateParams"]["seed"] = -1
                
            # 设置模板UUID (根据基础算法类型和是文生图还是图生图选择)
            if "templateUuid" not in validated:
                # 检查是否指定了基础算法类型
                base_model_type = validated.get("baseModelType", "").lower()
                is_f1 = base_model_type == "f.1" or base_model_type == "f1"
                
                if "sourceImage" in validated["generateParams"]:
                    if is_f1:
                        # F.1图生图模板
                        validated["templateUuid"] = "63b72710c9574457ba303d9d9b8df8bd"
                    else:
                        # 1.5和XL图生图模板
                        validated["templateUuid"] = "9c7d531dc75f476aa833b3d452b8f7ad"
                else:
                    if is_f1:
                        # F.1文生图模板
                        validated["templateUuid"] = "6f7c4652458d4802969f8d089cf5b91f"
                    else:
                        # 1.5和XL文生图模板
                        validated["templateUuid"] = "e10adc3949ba59abbe56e057f20f883e"
        
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
        调用LiblibAI图像模型
        
        Args:
            model: 模型名称
            parameters: 模型参数
            
        Returns:
            Dict[str, Any]: 模型调用结果
        """
        # 验证参数
        validated_params = await self.validate_parameters(model, parameters)
        
        # 获取API基础URL
        api_base_url = settings.LIBLIBAI_API_URL
        if not api_base_url:
            api_base_url = "https://openapi.liblibai.cloud"
        
        # 根据模型类型确定API端点
        if model == "star-3-alpha-t2i":
            api_endpoint = "/api/generate/webui/text2img/ultra"
        elif model == "star-3-alpha-i2i":
            api_endpoint = "/api/generate/webui/img2img/ultra"
        elif model == "liblib-custom":
            if "sourceImage" in validated_params.get("generateParams", {}):
                api_endpoint = "/api/generate/webui/img2img"
            else:
                api_endpoint = "/api/generate/webui/text2img"
        else:
            raise ValueError(f"Unsupported model: {model}")
        
        # 生成签名参数
        signature_params = self.generate_signature(api_endpoint)
        
        # 构建完整API URL
        api_url = f"{api_base_url}{api_endpoint}"
        
        logger.info(f"Calling LiblibAI image model {model}")
        
        try:
            # 准备请求数据
            request_data = {
                "templateUuid": validated_params["templateUuid"],
                "generateParams": validated_params["generateParams"]
            }
            
            # 记录完整的请求参数
            logger.info(f"Request data for LiblibAI API: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 准备请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            # 调用API创建任务
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 构建带签名的URL
                url_with_params = f"{api_url}?AccessKey={signature_params['AccessKey']}&Signature={signature_params['Signature']}&Timestamp={signature_params['Timestamp']}&SignatureNonce={signature_params['SignatureNonce']}"
                
                response = await client.post(
                    url_with_params,
                    json=request_data,
                    headers=headers
                )
                
                # 检查响应状态
                response.raise_for_status()
                task_result = response.json()
                
                # 记录完整的响应
                logger.info(f"Task creation response: {json.dumps(task_result, ensure_ascii=False)}")
                
                # 获取任务ID
                if task_result.get("code") != 0:
                    error_msg = task_result.get("msg", "Unknown error")
                    raise ValueError(f"LiblibAI API error: {error_msg}")
                
                generate_uuid = task_result.get("data", {}).get("generateUuid")
                if not generate_uuid:
                    logger.error(f"Failed to get generateUuid from response: {task_result}")
                    raise ValueError(f"Failed to get generateUuid from response: {task_result}")
                
                logger.info(f"Created LiblibAI task with ID: {generate_uuid}")
                
                # 轮询任务结果
                max_retries = 120  # 最多等待120次 (约12分钟)
                retry_interval = 15  # 每次等待15秒
                
                # 构建查询任务状态的URL
                status_endpoint = "/api/generate/webui/status"
                
                for i in range(max_retries):
                    # 等待一段时间
                    await asyncio.sleep(retry_interval)
                    
                    # 生成查询任务的签名
                    status_signature_params = self.generate_signature(status_endpoint)
                    status_url = f"{api_base_url}{status_endpoint}?AccessKey={status_signature_params['AccessKey']}&Signature={status_signature_params['Signature']}&Timestamp={status_signature_params['Timestamp']}&SignatureNonce={status_signature_params['SignatureNonce']}"
                    
                    # 查询任务状态
                    status_response = await client.post(
                        status_url,
                        json={"generateUuid": generate_uuid},
                        headers=headers
                    )
                    
                    status_response.raise_for_status()
                    task_status = status_response.json()
                    
                    # 记录完整的任务状态响应
                    logger.info(f"Task {generate_uuid} status response: {json.dumps(task_status, ensure_ascii=False)}")
                    
                    if task_status.get("code") != 0:
                        error_msg = task_status.get("msg", "Unknown error")
                        raise ValueError(f"LiblibAI API error: {error_msg}")
                    
                    # 获取任务状态
                    task_data = task_status.get("data", {})
                    generate_status = task_data.get("generateStatus", 0)
                    
                    logger.info(f"Task {generate_uuid} status: {generate_status}")
                    
                    # 如果任务完成或失败，返回结果
                    if generate_status == 5:  # 成功
                        # 格式化响应结果并下载图片
                        result = await self._format_response_and_download_images(task_data, validated_params)
                        return result
                    elif generate_status == 6 or generate_status == 7:  # 失败或超时
                        error_msg = task_data.get("generateMsg", "Task failed or timed out")
                        raise ValueError(f"Task failed: {error_msg}")
                
                # 超过最大重试次数
                raise ValueError(f"Task {generate_uuid} did not complete within expected time")
                
        except httpx.HTTPStatusError as e:
            error_detail = {}
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"message": e.response.text}
                
            error_msg = f"LiblibAI API HTTP error: {e.response.status_code}, {error_detail}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        except Exception as e:
            logger.error(f"Error calling LiblibAI model: {str(e)}")
            raise ValueError(f"LiblibAI API error: {str(e)}")
    
    async def _format_response_and_download_images(self, api_response: Dict[str, Any], original_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化LiblibAI API响应并下载图片
        
        Args:
            api_response: API原始响应
            original_params: 原始参数
            
        Returns:
            Dict[str, Any]: 格式化的响应，包含本地图片路径
        """
        # 构建统一格式的响应
        formatted_response = {
            "id": api_response.get("generateUuid", str(uuid.uuid4())),
            "model": original_params.get("model", ""),
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "images": [],
            "pointsCost": api_response.get("pointsCost", 0),
            "accountBalance": api_response.get("accountBalance", 0)
        }
        
        # 设置图片保存目录
        base_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
        images_dir = base_dir / "data" / "images" / "liblibai"
        os.makedirs(images_dir, exist_ok=True)
        
        # 下载并保存图片
        images = api_response.get("images", [])
        for i, image_data in enumerate(images):
            image_url = image_data.get("imageUrl", "")
            if not image_url:
                continue
                
            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"liblibai_{timestamp}_{i}_{uuid.uuid4().hex[:8]}.png"
            local_path = os.path.join(images_dir, file_name)
            
            # 下载图片
            saved_path = await self.download_image(image_url, local_path)
            
            # 添加到响应中
            image_info = {
                "index": i,
                "url": image_url,  # 保留原始URL
                "local_path": saved_path,  # 添加本地路径
                "seed": image_data.get("seed", None),
                "auditStatus": image_data.get("auditStatus", None)
            }
            formatted_response["images"].append(image_info)
        
        # 添加原始提示词
        generate_params = original_params.get("generateParams", {})
        formatted_response["prompt"] = generate_params.get("prompt", "")
        
        if "negativePrompt" in generate_params:
            formatted_response["negative_prompt"] = generate_params["negativePrompt"]
        
        # 添加图像尺寸信息
        if "width" in generate_params and "height" in generate_params:
            formatted_response["width"] = generate_params["width"]
            formatted_response["height"] = generate_params["height"]
        elif "imageSize" in generate_params:
            image_size = generate_params["imageSize"]
            formatted_response["width"] = image_size.get("width", 768)
            formatted_response["height"] = image_size.get("height", 1024)
        else:
            formatted_response["width"] = 768
            formatted_response["height"] = 1024
            
        return formatted_response


# 注册提供商
from . import register_provider
register_provider(LiblibAIProvider) 