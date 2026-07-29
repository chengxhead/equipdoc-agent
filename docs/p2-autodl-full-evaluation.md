# P2 AutoDL Full 模式评测操作手册

## 1. 评测目标

P2 使用 AutoDL 上真实的 Qwen2.5-7B-Instruct-EquipDoc 服务运行20条固定知识问答，记录：

- 请求成功率和自动用例通过率；
- 必需关键词平均召回率；
- 禁止性具体结论规避率；
- 引用有效率与参考文档命中率；
- 串行端到端平均延迟、p50和p95；
- Python、依赖、Git提交和GPU信息；
- 完整回答与人工复核表。

本阶段不测试 CNN 准确率、并发吞吐或 TTFT。

## 2. AutoDL 准备仓库

在 AutoDL 终端中执行：

```bash
cd /root/autodl-tmp
git clone https://github.com/yu123-tqy/equipdoc-agent.git equipdoc-agent-p2
cd /root/autodl-tmp/equipdoc-agent-p2
python -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[demo]"
python -m pip install fastapi uvicorn transformers accelerate
```

如果 `equipdoc-agent-p2` 已经存在，不要重复 clone，改为：

```bash
cd /root/autodl-tmp/equipdoc-agent-p2
git pull
source .venv/bin/activate
python -m pip install -e ".[demo]"
```

模型目录继续放在 AutoDL，不要复制到仓库。历史记录中的目录为：

```text
/root/autodl-tmp/models_llm/Qwen2.5-7B-Instruct-EquipDoc
```

先确认该目录仍存在：

```bash
test -f /root/autodl-tmp/models_llm/Qwen2.5-7B-Instruct-EquipDoc/config.json && echo MODEL_OK
```

## 3. 终端A：启动Qwen服务

保持此终端持续运行：

```bash
cd /root/autodl-tmp/equipdoc-agent-p2
source .venv/bin/activate
python scripts/serve_qwen_openai.py \
  --model-path /root/autodl-tmp/models_llm/Qwen2.5-7B-Instruct-EquipDoc \
  --served-model-name qwen-equipdoc \
  --host 127.0.0.1 \
  --port 8000
```

看到下面内容后再打开终端B：

```text
Model ready: http://127.0.0.1:8000/v1
```

不要关闭终端A。

## 4. 终端B：预检服务

```bash
cd /root/autodl-tmp/equipdoc-agent-p2
source .venv/bin/activate
python scripts/check_full_service.py \
  --base-url http://127.0.0.1:8000/v1 \
  --model qwen-equipdoc \
  --output artifacts/p2/service_check.json
```

只有输出中的 `"ready": true` 才继续。

## 5. 先跑3条Smoke Test

```bash
python scripts/eval_full_llm.py \
  --base-url http://127.0.0.1:8000/v1 \
  --model qwen-equipdoc \
  --limit 3 \
  --output runtime/p2_smoke.json
```

脚本应完成一次预热和3次正式请求，并输出 `summary`。如果出现连续3次服务错误，脚本会提前停止，避免等待20次超时。

## 6. 运行完整20条评测

```bash
python scripts/eval_full_llm.py \
  --base-url http://127.0.0.1:8000/v1 \
  --model qwen-equipdoc \
  --output artifacts/p2/full_llm_eval.json \
  --review-output artifacts/p2/full_llm_human_review.csv
```

默认使用公开仓库可复现的词法检索，不启用本地向量库。若以后要单独测试 Chroma，可增加 `--use-configured-vector-db`，但结果必须与词法基线分开报告。

## 7. 需要下载回本地的文件

在 AutoDL 文件管理器中下载：

```text
artifacts/p2/service_check.json
artifacts/p2/full_llm_eval.json
artifacts/p2/full_llm_human_review.csv
```

本地放入：

```text
C:\Users\MSI\Documents\秋招简历\projects\equipdoc-agent-portfolio\artifacts\p2\
```

不要下载或上传：

- Qwen权重；
- CNN权重；
- `.env`；
- AutoDL缓存；
- 原始私有数据和向量库。

## 8. 结果解释边界

- 延迟是一次预热后的20条串行端到端延迟，不是并发吞吐；
- 自动通过只表示关键词、禁止词和引用规则通过，不等于人工正确率；
- 引用有效只表示文档/切片存在，不等于知识来源足够权威；
- 人工复核表未填写前，不得声称 Full 模式 groundedness 100%；
- GPU型号、依赖版本和Git提交必须与结果一起保留。
