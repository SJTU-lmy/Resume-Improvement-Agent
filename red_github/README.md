# 求职信息筛选 + 简历定制优化 Agent

输入一批招聘帖和你的简历，输出与求职目标匹配岗位对应的定制化简历（docx）：从岗位帖中筛选出匹配岗位，提取岗位要求，把简历改写成对标JD的版本，并经过检查修复与分项打分的质量闭环。
**本仓库只包含核心代码与多智能体 Prompt，不含爬虫、不含任何真实数据与密钥。**

## 功能

- 多智能体流水线：岗位筛选（filter）→ 优秀简历 Vector RAG → 简历优化（optimizer）→ 规则校验 + 检查（checker）→ 错误修复 → 打分（scorer）→ 低分质量修复
- 优秀简历 RAG：基于阿里 text-embedding-v3 的向量检索，可限定岗位族范例池
- 防编造：邮箱、城市、post_type、实习/工作经历、岗位名、奖项名称均有硬约束与检测，岗位名只从笔记文字提取
- 关键词体系：岗位关键词只从「任职要求」段提取，按 硬技能/工具/软素质/领域 分类，内置词典 + 新词待确认回填
- 结构化输出：改写简历自动排版为 docx（姓名/求职意向/联系方式 → 教育 → 项目 → 个人优势 → 专业技能 → 荣誉奖项）

## 架构

```text
岗位笔记 + 求职目标 + 原简历
  → filter 智能体（相关度判断；无岗位文字则剔除）
  → Vector RAG（岗位族限定，取 top-3 优秀简历作范例）
  → optimizer 智能体（提取岗位信息 + 岗位化改写简历）
  → 规则校验 + checker 智能体（显式错误检测）
  → 有错则回传 optimizer 修复（≤1 轮）
  → scorer 打分（岗位匹配/关键词覆盖/事实保真/结构/量化）
  → 低分触发质量修复轮
  → 生成 docx
```

## 目录结构

```text
red_github/
├── config/                 # 配置模板（*.example.json 复制后填写）
├── prompts/                # executor_v0.txt + prompts/v1 四套智能体模板
├── src/                    # 核心代码（流水线、检索、关键词、简历落盘）
├── dataset/                # 示例数据 test_set.example.json
├── run_single.py           # 单条入口：一条岗位 → 一份 docx
├── batch_optimize.py       # 批量入口：全部岗位 → 多份 docx + jobs_info.json
├── convert_notes.py        # txt（===== 分隔）→ test_set.json
├── filter_notes.py         # 关键词预筛（可选）
└── requirements.txt
```

## 安装

建议 Python 3.10+：

## 安装所需要的库
pip install -r requirements.txt
```


## 快速开始（示例数据）

```bash
# 1) 生成配置并填入真实 API Key
在 config/llm_config.example.json config/llm_config.json
和 config/retrieval_config.example.json config/retrieval_config.json 填写你真实的API_Key

# 2) 准备测试集（示例自带简历文本，可直接运行）
cp dataset/test_set.example.json dataset/test_set.json

# 3) 单条 / 批量
python run_single.py --job "AI产品经理" --sample_id 001
python batch_optimize.py --job "AI产品经理" --sample-limit 3
```

> Windows 下把 `cp` 换成 `copy`。示例邮箱均为虚构；真实数据与简历请放本地，不要提交到仓库。

## 真实数据准备

1. 简历：放 `resume/`（自动探测 `resume.docx`→`简历.docx`→`resume.pdf`→`简历.pdf`），或在 test_set.json 每条内写 `user_resume` 文本。
2. 优秀简历库：精选简历放入 `resume_examples/`，按 `config/job_family.json` 分组（可选岗位族限定）。
3. 岗位笔记：`notes.txt`（笔记间用单独一行 `=====` 分隔）→ `python convert_notes.py`。

## 输出

- `new/001_optimized.docx`…：每个匹配岗位的定制简历（默认 docx；`--with-pdf` 同时出 pdf）
- `new/jobs_info.json`：逐条结果清单（sample_id / 状态 / job_name / base_city / contact_email / post_type / docx 路径）

`run_single.py` 参数：`--sample_id`、`--job`（求职目标）、`--resume`、`--with-pdf`、`--out`。
`batch_optimize.py` 参数：`--job`、`--resume`、`--out`、`--with-pdf`、`--sample-limit`、`--max-repair`、`--max-quality-repair`。

## 免责声明

- 本仓库不含爬虫；请自行遵守目标平台条款与法律法规，自行准备数据与 API Key。
- 简历与笔记可能含个人信息，请勿提交到公开仓库。
