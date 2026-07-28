# EquipDoc-Agent

面向机电设备运维场景的可审核、可降级 Agent 作品。项目将安全策略、LangGraph 人工审核、轴承信号诊断工具、可选 RAG 和证据化报告组织为一个可复现的公开仓库。

> P0 status: the repository can run in a clearly labelled model-free Demo mode. Full-model metrics and cross-condition evaluation are intentionally deferred to P1.

## 项目解决什么问题

传统大模型问答无法直接分析时序信号，也容易在设备信息不足时编造维修依据。本项目关注的是一个受控流程：

```text
安全上传振动信号
→ 确定性策略判断任务边界
→ 人工审核工具调用
→ 轴承诊断工具
→ 检索故障机理与维修依据
→ 生成带边界说明的诊断报告
```

项目不控制真实设备，不替代工程师作出高风险维修决策，也不根据单段信号预测精确剩余寿命。

## P0 已完成

- 标准 `src/` Python 包和 `pyproject.toml`；
- Git/环境变量/依赖/Docker 发布骨架；
- 去除 AutoDL 绝对路径；
- CNN、LLM 和向量库懒加载；
- 缺少7B模型时可运行的显式 Demo 模式；
- `.npy` 文件沙箱、大小、类型和数值检查；
- 启动前健康检查；
- Gradio 文件上传和 LangGraph Approve/Reject；
- 无向量库时的词法检索降级；
- 原始评测与部署 JSON 作为 `artifacts/legacy/` 历史证据保存；
- 对旧 CNN 数据切分局限的明确说明；
- 不依赖模型权重的基础单元测试。

## 当前项目结构

```text
equipdoc-agent-portfolio/
├─ app_gradio.py
├─ pyproject.toml
├─ .env.example
├─ Dockerfile
├─ docker-compose.yml
├─ src/equipdoc_agent/
│  ├─ config.py
│  ├─ health.py
│  ├─ agent/
│  ├─ tools/
│  ├─ models/
│  └─ rag/
├─ data/
│  ├─ samples/
│  ├─ knowledge/
│  └─ eval/
├─ scripts/
│  ├─ build_rag_index.py
│  ├─ demo_smoke.py
│  └─ legacy/
├─ tests/
├─ docs/
└─ artifacts/legacy/
```

详细架构见 [`docs/architecture.md`](docs/architecture.md)，从 AutoDL 快照迁移了什么见 [`docs/migration-notes.md`](docs/migration-notes.md)。

## 方式一：无模型 Demo 模式

这是第一次克隆仓库时的推荐路径。它不需要 Qwen、Torch、CNN 权重或 Chroma 向量库。

### 1. 准备 Python

推荐 Python 3.10 或3.11。

```bash
python -m venv .venv
```

Linux/AutoDL：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. 安装 Demo 依赖

```bash
python -m pip install --upgrade pip
pip install -e ".[demo]"
```

### 3. 创建配置

Linux/AutoDL：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

确认 `.env` 中为：

```text
EQUIPDOC_DEMO_MODE=true
```

### 4. 运行健康检查和 Smoke Test

```bash
equipdoc-health --strict
python scripts/demo_smoke.py
```

健康检查中的 `bearing_model` 和 `rag_vector_db` 可以显示为不存在，因为它们在 Demo 模式不是必需项。

### 5. 启动页面

```bash
python app_gradio.py
```

浏览器打开：

```text
http://127.0.0.1:7860
```

若 `7860` 已被其他程序占用，应用会自动依次尝试 `7861`、`7862` 等端口。请以终端中 `Running on local URL` 后显示的实际地址为准。也可以在 PowerShell 中手动指定端口：

```powershell
$env:EQUIPDOC_SERVER_PORT="7861"
.\.venv\Scripts\python.exe .\app_gradio.py
```

页面默认使用仓库内的 `data/samples/test_signal.npy`。提交后会出现工具审核，点击 Approve 才继续生成报告。

Demo 页面会明确显示：故障类型是固定案例回放，不是本机模型推理结果。

## 方式二：Docker Demo

```bash
docker compose up --build
```

打开：

```text
http://127.0.0.1:7860
```

Docker 镜像只包含 Demo 所需依赖，不包含7B模型和 Torch。

## 方式三：AutoDL Full 模式

Full 模式需要你在 AutoDL 上保留或重新生成模型文件。

### 1. 安装完整依赖

建议新建环境，避免破坏原实验环境：

```bash
conda create -n equipdoc-public python=3.11 -y
conda activate equipdoc-public
pip install -e ".[demo,ml,rag]"
```

如现有 CUDA/Torch 环境已经可用，可以先安装 `[demo,rag]`，不要无条件升级 Torch。

### 2. 准备轴承模型文件

Full 模式默认需要：

```text
models/bearing_cnn.pth
data/processed/norm.npy
```

可以从原 AutoDL 项目复制：

```bash
mkdir -p models data/processed
cp /root/autodl-tmp/equipdoc-agent/models/bearing_cnn.pth models/
cp /root/autodl-tmp/equipdoc-agent/data/processed/norm.npy data/processed/
```

旧模型仅用于复现原工具链。其100%测试准确率不代表跨工况泛化，详见 `scripts/legacy/README.md`。

### 3. 配置 Qwen 服务

不要把14GB合并模型上传 GitHub。让模型继续保留在 AutoDL，并启动一个 OpenAI-compatible 服务。

在 `.env` 中修改：

```text
EQUIPDOC_DEMO_MODE=false
EQUIPDOC_LLM_BASE_URL=http://127.0.0.1:8000/v1
EQUIPDOC_LLM_MODEL=qwen-equipdoc
EQUIPDOC_LLM_API_KEY=EMPTY
```

模型服务必须至少支持普通 `/v1/chat/completions`。诊断主路径有确定性安全路由；如果希望展示真正的 LLM 结构化工具选择，服务还必须支持 `tools/tool_calls`，并在 P1 中单独评测。

### 4. 构建可选向量库

```bash
python scripts/build_rag_index.py --reset
```

如果不构建向量库，系统仍会使用词法检索，并在健康信息中明确显示 Dense Retrieval 未启用。

### 5. 检查并启动

```bash
equipdoc-health --strict
python app_gradio.py
```

## 配置说明

所有配置都放在环境变量中，完整示例见 `.env.example`。

| 变量 | 用途 | 安全默认值 |
|---|---|---|
| `EQUIPDOC_DEMO_MODE` | 是否使用无模型固定案例 | `true` |
| `EQUIPDOC_LLM_BASE_URL` | OpenAI-compatible 服务地址 | 本机8000端口 |
| `EQUIPDOC_BEARING_MODEL_PATH` | CNN权重 | `models/bearing_cnn.pth` |
| `EQUIPDOC_UPLOAD_ROOT` | 上传沙箱 | `runtime/uploads` |
| `EQUIPDOC_MAX_UPLOAD_MB` | 文件大小限制 | `8` |
| `EQUIPDOC_RAG_DB_DIR` | Chroma目录 | `vector_db/chroma_equipdoc` |
| `EQUIPDOC_EMBEDDING_MODEL` | Embedding模型 | `bge-small-zh-v1.5` |

## 测试

基础测试不调用7B模型：

```bash
python -m unittest discover -s tests -v
```

如果安装了开发依赖，也可以：

```bash
pytest -q
ruff check .
```

## 安全与公开边界

- UI不接受服务器路径输入，只接受上传文件或内置样例；
- 上传文件被复制到 `runtime/uploads`，使用随机文件名；
- 工具只允许读取 `data/samples` 和 `runtime/uploads`；
- 仅接受受限大小的数值型 `.npy`；
- 禁止把真实单位代码、内部手册、设备参数和客户数据加入仓库；
- Demo 标签不能删除，否则固定案例结果可能被误解为真实推理；
- 当前知识库是自写笔记，P1需要补充权威来源和版本信息。

## 当前证据应如何解释

`artifacts/legacy/` 保存了原 AutoDL 结果，但不在首页宣传为最终性能：

- 30条 Agent 评测主要验证规则路由和审核分支；
- FP16结果只有9次串行请求，而且没有记录GPU型号；
- BNB 4-bit结果是单问题测试；
- 旧CNN随机窗口拆分存在同源数据泄漏风险；
- 100条 RAG 测试集存在，但当前仓库没有原实验的最终 RAG 输出。

P1完成前，简历不应写“CNN准确率100%”“Agent工具路由100%”或未经人工复核的“幻觉降低率”。

## GitHub 发布建议

首次检查后执行：

```bash
git add .
git status
git commit -m "feat: publish reproducible P0 demo"
```

再创建远程仓库并推送。推送前务必检查：

```bash
git status
git ls-files
```

确认没有 `.env`、模型权重、AutoDL日志、内部数据和个人密钥。

当前 `LICENSE` 为保留所有权、允许招聘与教育评审的展示许可。如果确认所有代码和数据均有权开放，再单独选择 MIT 或 Apache-2.0。

## 下一阶段

P1聚焦可信评测，而不是继续堆功能：

1. 按原始文件/工况进行 Group Split；
2. 分开统计规则路由和 LLM 路由；
3. 扩展安全、异常、多轮和多工具评测；
4. 为知识库补权威来源；
5. 完成人工 groundedness 审查；
6. 重新运行带GPU、版本、并发和 p95 的部署基准。
