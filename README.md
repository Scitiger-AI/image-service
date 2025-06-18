# Image Service

图像模型调用服务，支持通过API调用各种图像生成模型。

## 功能特性

- 支持多种图像生成模型
- 异步任务处理
- 任务状态跟踪和结果获取
- 统一的API接口
- 集成认证系统
- 自动下载和保存生成的图像

## 支持的模型

### 阿里云通义万相模型

- wanx2.1-t2i-turbo：通义万相2.1 Turbo版本，快速生成图像
- wanx2.1-t2i-plus：通义万相2.1 Plus版本，高质量图像生成
- wanx2.0-t2i-turbo：通义万相2.0 Turbo版本

### LiblibAI模型

- star-3-alpha-t2i：星流Star-3 Alpha文生图，适合对AI生图参数不太了解或不想复杂控制的用户
- star-3-alpha-i2i：星流Star-3 Alpha图生图，适合基于参考图像生成新图像
- liblib-custom：LiblibAI自定义模型，可调用LiblibAI网站内全量模型，适合高度自由和精准控制的场景

## 实现说明

本服务使用异步方式调用各种图像生成API。流程如下：

1. 服务接收用户请求并创建任务记录
2. 使用异步方式调用相应提供商的API
3. 获取API返回的任务ID
4. 轮询任务状态直到完成或失败
5. 下载生成的图像并保存到本地 `data/images` 目录
6. 返回处理结果给用户，包括原始图像URL和本地保存路径

### 图像保存

- 生成的图像会自动下载并保存到 `data/images` 目录
- 文件名格式：`{提供商}_{时间戳}_{索引}_{随机ID}.png`
- 任务结果中会包含图像的原始URL和本地保存路径
- 提供商返回的图像URL有效期有限，但本地保存的图像永久有效

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
- `LIBLIBAI_ACCESS_KEY`：LiblibAI访问密钥
- `LIBLIBAI_SECRET_KEY`：LiblibAI访问密钥密文

### 启动服务

1. 启动API服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001  --reload
```

2. 启动Celery Worker

```bash
celery -A app.core.celery_app worker --loglevel=info
```

## API使用

### 创建图像生成任务 - 阿里云通义万相

```bash
curl -X POST "http://localhost:8001/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx2.1-t2i-turbo",
    "provider": "aliyun",
    "parameters": {
      "prompt": "一只可爱的小猫咪在草地上玩耍",
      "negative_prompt": "模糊, 扭曲, 低质量",
      "size": "1024*1024",
      "n": 1
    },
    "is_async": true
  }'
```

### 创建图像生成任务 - LiblibAI星流Star-3 Alpha文生图

```bash
curl -X POST "http://localhost:8001/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "star-3-alpha-t2i",
    "provider": "liblibai",
    "parameters": {
      "prompt": "1 girl,lotus leaf,masterpiece,best quality,finely detail,highres,8k,beautiful and aesthetic,no watermark",
      "aspectRatio": "portrait",
      "imgCount": 1,
      "steps": 30
    },
    "is_async": true
  }'
```

### 创建图像生成任务 - LiblibAI星流Star-3 Alpha图生图

```bash
curl -X POST "http://localhost:8001/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "star-3-alpha-i2i",
    "provider": "liblibai",
    "parameters": {
      "prompt": "focus on the cat,there is a cat holding a bag of mcdonald, product advertisement",
      "sourceImage": "https://example.com/source-image.jpg",
      "width": 768,
      "height": 1024,
      "imgCount": 1
    },
    "is_async": true
  }'
```

### 创建图像生成任务 - LiblibAI自定义模型文生图

```bash
curl -X POST "http://localhost:8001/api/v1/tasks/" \
  -H "Content-Type: application/json" \
  -d '{
  "model": "liblib-custom",
  "provider": "liblibai",
  "parameters": {
    "baseModelType": "f1",
    "checkPointId": "412b427ddb674b4dbab9e5abd5ae6057",
    "prompt": "短发女孩",
    "generateParams": {
      "negativePrompt": "低质量，模糊",
      "sampler": 1,
      "steps": 30,
      "cfgScale": 3.5,
      "width": 720,
      "height": 1440,
      "imgCount": 1,
      "additionalNetwork": [{
                 "modelId": "d250a31f321e4cee84fe4115cabb8bc4",
                 "weight": 0.8
                }]
    }
  },
  "is_async": true
}'
```

### 查询任务状态

```bash
curl "http://localhost:8001/api/v1/tasks/{task_id}/status"
```

### 获取任务结果

```bash
curl "http://localhost:8001/api/v1/tasks/{task_id}/result"
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
      "model": "star-3-alpha-t2i",
      "created": "2025-06-16 20:08:58",
      "images": [
        {
          "index": 0,
          "url": "https://liblibai-online.liblib.cloud/sd-images/08efe30c1cacc4bb08df8585368db1f9c082b6904dd8150e6e0de5bc526419ee.png",
          "local_path": "/Users/alanfu/Documents/projects/sciTigerService/image-service/data/images/liblibai_20250616_200858_0_a1b2c3d4.png",
          "seed": 12345,
          "auditStatus": 3
        }
      ],
      "prompt": "1 girl,lotus leaf,masterpiece,best quality",
      "width": 768,
      "height": 1024,
      "pointsCost": 10,
      "accountBalance": 1356402
    },
    "error": null
  }
}
```

## 开发指南

### 项目结构

```
text-service/
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
│   │   └── response.py             # 统一响应格式
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

1. 在`app/services/model_providers`目录下创建新的提供商文件
2. 实现`ModelProvider`接口
3. 在`__init__.py`中注册提供商

