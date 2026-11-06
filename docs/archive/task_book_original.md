# 实习任务书（PDF 转 Markdown，原版归档）

> 归档说明：本文件是原任务书副本，仅作参考。v2 实际执行口径见 [`../task.md`](../task.md)。

> 源文件：`D:\Desktop\实习任务：基于 pi agent 验证 CLI 工具做文档检索与研究总结的效率 (1).pdf`
> PDF sha256：`7b2c7897a262abcc79e0e6133e378596619b30a46da11eee9e281d77b02ceb2b`
> 页数：7
> 转换：pypdf 文本层逐页提取；仅修正康熙部首/兼容字，保留中文标点；表格/排版可能丢失。
> 用途：规范引用文件，不进入 corpus/S，不参与 G0/G1/G3。

<!-- page: 1 -->

实习任务：基于  pi agent 验证  CLI 工具做文档检
索与研究总结的效率
 Nov 2, 2026  ·  @Can Wang
背景与目标
本任务要验证：不建向量库，只给  Agent 原生的  grep / find / ls / read / bash 工具，在文档查
询检索和研究总结两类任务上，效果能不能达到向量  RAG 的水平，代价（ token 、耗时、调用
轮数）是多少。
Claude Code 、 pi 这类  coding agent 都不用向量索引，靠「 Agent 自己搜」（ agentic search ）
来找代码。代码里的标识符很精确，这样做效果好。但企业文档是中文自然语言，没有空格分
词，同义说法多，文件格式也杂。这套做法能不能迁移到企业文档上，需要用数据回答。
要回答的  5 个问题：
1. 准确性：分题型看，纯  CLI 检索的答对率和证据命中率跟向量  RAG 比各差多少。题型包括
精确事实查找、问法和原文用词不同、跨文档汇总、开放研究总结、资料里没有答案。
2. 成本：每道题的输入 / 输出  token 、工具调用次数、对话轮数、端到端耗时、费用。
3. 规模：语料从约  20 份涨到约  2000 份时，上面两组指标怎么变，在哪个规模开始明显变差。
4. 上下文行为：⻓研究任务里  Agent 怎么挑  grep 关键词、怎么换词、读整个文件还是分段
读；会不会触发上下文压缩（ compaction ），压缩以后质量掉多少。
5. 结论：哪类任务用  CLI 检索就够了，哪类必须上  RAG ，两者混合用怎么搭最划算。
独立完成与  AI 辅助
本任务由你一人独立负责，语料、题集、脚本到最后的结论都由你完成。
允许用  coding agent 辅助： WorkBuddy 、 CodeBuddy 等都可以，用来写运行脚本、
JSONL 解析、打分器、 search_docs  extension 和报告初稿。用它们的免费余额即可，推
荐选其中的  DeepSeek 模型。
代码要读懂： AI 生成的每个脚本都要能讲清逻辑，汇报时会抽查。
数据不能编：参考答案、证据位置、实验数字都必须来自原文和真实运行记录，不能让  AI 代
写或补⻬。
留痕：周记里写明哪些部分由  AI 生成、自己改了什么。
分清两件事： coding agent 是你写代码的工具， pi 是被测对象。 pi 调用的模型单独配置（⻅
下一节），两者互不影响。
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 1 of 7

<!-- page: 2 -->

pi agent 与实验用到的能力
pi 是一个极简的开源  coding agent （earendil-works/pi），系统提示词短、内置工具少，很适
合拿来做对照实验。运行需要  Node.js 22.19 及以上，安装命令： npm install -g --ignore-
scripts @earendil-works/pi-coding-agent 。
内置工具（cli.md）：默认只启用  read  / bash  / edit  / write ， grep  / find  / ls  是内置工
具但默认关闭，要用  --tools  显式打开。
接入公网模型（models.md）：在  models.json  里加一个  OpenAI 兼容的服务商，密钥用环境
变量引用，不写在明文里。下面  baseUrl 和模型  id 是占位符，实际值以服务商官方文档为准。
也可以接本机  Ollama 。
{
  "providers": {
    "public-llm": {
      "baseUrl": "https://< 服务商域名 >/v1",
      "api": "openai-completions",
      "apiKey": "$PUBLIC_LLM_API_KEY",
      "models": [{ "id": "< 模型  id>" }]
    }
  }
}
批量跑实验：用  JSON 模式跑单题，输出  JSONL 事件流（json.md），所有指标都从这个文件
里算。
工具 用途 默认是否启用 本实验用法
read 读文本文件和图片 是 所有组都开
grep 搜索文件内容 否 CLI 组的核心
find 按  glob 查找路径 否 CLI 组开
ls 列目录 否 CLI 组开
bash 执行  shell 命令 是 只在  G2 / G4 组开（可用  rg 、管道等）
edit  / write 改文件  / 写文件 是 一律关闭，防止改动语料
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 2 of 7

<!-- page: 3 -->

cd corpus/S
pi --mode json --no-session -nc \
   --model public-llm/< 模型  id> \
   --tools read,grep,find,ls \
   --append-system-prompt ../../prompts/researcher.md \
   " 问题文本 " > ../../runs/G1/S/q001_r1.jsonl
-nc ：不自动加载  AGENTS.md / CLAUDE.md 。想测「给语料配一份目录索引」的效果
时，再单独开一组把它打开。
--no-session ：每道题都从干净的上下文开始，避免题与题之间互相干扰。
需要解析的事件： tool_execution_start （工具名和参数）、 tool_execution_end （工
具结果和  durationMs ）、 message_update  里的  usage （ token 和  cost ）、
compaction_start  / compaction_end （ tokensBefore  / estimatedTokensAfter ）、
agent_end 。
上下文压缩（settings.md）：默认开启。剩余可用上下文低于
compaction.reserveTokens （默认  16384 ）时触发，最近
compaction.keepRecentTokens （默认  20000 ）个  token 保留原文。第  5 周要改这两个值
做对比。
向量检索工具用  pi 的  extension 机制注册（extensions.md），不改  pi 源码。
动手前先通读  how-pi-works.md。文中的参数是  2026-11 的文档写法，以实际安装版本的  pi -
-help  为准。
实验设计
同一个模型、同一套题、同一份语料，只改工具组合和语料规模，每道题每种配置跑  3 次，指标
取均值并报告波动。
语料
来源：只用公开中文资料，比如上市公司年报（巨潮资讯网等公开渠道）、国家法律法规数据
库里的法规、开源项目的中文技术文档。建议以一个领域为主（如金融年报），混入少量其他
领域做干扰。
三档规模： S 约  20 份文件  / 约  2 MB 文本； M 约  200 份  / 约  20 MB ； L 约  2000 份  / 100 MB
以上。 M 包含  S ， L 包含  M ，这样同一道题的答案在三档里都存在。
格式预处理： grep 搜不了  PDF / Word 二进制内容，先统一转成  Markdown 或纯文本
（ pymupdf 、 pdftotext 、 pandoc 等自选）。转换脚本要入库，并记录转换损失（表格、换
行断句）。可以加一组对照：只给原始  PDF ，允许  bash 调  pdftotext ，看  Agent 会不会自己
转。
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 3 of 7

<!-- page: 4 -->

题集（共  80 题）
每题标注参考答案和证据位置（文件名  + ⻚码或章节）。题目写完后隔一两天，自己抽  20 题对
照原文复核，也可以让另一个模型交叉检查参考答案。
对照组
各组用同一段追加提示词（ prompts/researcher.md ）：只写研究助手角色、要求标明出处、
查不到如实说，不写「先  grep 再  read 」这类检索技巧，否则测的是提示词而不是工具。
类别 题
数
例子 考察点
A 精确事实 20 某公司  2025 年研发投入是多少 关键词明确，预期  CLI 强项
B 语义改写 20 问「人力成本」，原文写的是「职工薪
酬」
问法和原文用词不同，预期  RAG
强项
C 跨文档汇
总
15 对比  5 家公司近三年毛利率 多次检索  + 信息拼接
D 开放研究 15 写一份  2000 字的行业⻛险研究综述 ⻓任务、上下文压缩、结构化输
出
E 无答案 10 问语料里根本没有的公司 应如实说查不到，不能编
组 工具 说明
G0 无工具 语料整个塞进上下文，只在  S 档放得下时跑，用作准
确率上限参考
G1 read,grep,find,ls 纯只读  CLI ，本任务的主角
G2 G1 + bash 允许  rg 、管道、 wc 、 awk 等组合，在隔离目录或容器
里跑
G3 read  + search_docs 向量  RAG 对照：用  extension 注册检索工具，本地
embedding （如  bge 系列） + 轻量向量库（ faiss /
LanceDB / Chroma 任选）
G4 G2 + search_docs 混合：观察  Agent 自己怎么分配两类工具
G1+ G1 + 目录索引 语料根目录放一份  INDEX.md （每个文件一行摘要）
并用  AGENTS.md 引用，测一份廉价的「地图」能提
升多少
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 4 of 7

<!-- page: 5 -->

指标
除了数字，还要做行为分析：每类题中挑  3 个典型轨迹，写清  Agent 搜了什么词、换了几次
词、读了哪些文件的哪些段、在哪一步走偏。还要重点看中文问题：没有分词、繁简写法、全角
半角、数字格式（「 1.2 亿」和「 120,000,000 」）对  grep 的影响。
分阶段计划
全程按  6 周安排，每周五交一篇周记：做了什么、数据、遇到的问题。前一阶段验收通过再进入
下一阶段。
指标 怎么算
答对率 LLM 对照参考答案打分（ 0 / 0.5 / 1 ），人工抽检  20%
校准打分器
证据命中率 回答里引用的文件和位置是否包含标注的证据
幻觉率 回答里语料中找不到来源的事实、数字占比
E 类拒答率 无答案题里如实说「查不到」的比例
输入  / 输出  token 、费用 汇总  usage
工具调用次数、轮数 按工具名统计  tool_execution_start
端到端耗时 脚本计时  + 工具  durationMs
压缩次数与压缩率 compaction_end  的  tokensBefore  /
estimatedTokensAfter
周 内容 验收标准
1 装  pi 、接通公网模型；通读  how-pi-works /
cli / json 文档；写好单题运行脚本和  JSONL
解析脚本
任意一题能一条命令跑完，并输出
token 、工具调用次数、耗时；能讲清  pi
一轮对话里发给模型的内容由哪几部分组
成
2 采集并转换  S / M / L 三档语料；写  80 题及参
考答案、证据位置；写  LLM 打分器
抽  20 题对照原文复核无误；打分器与人
工打分在  20 题上的一致率  ≥ 85%
3 在  S / M 上跑  G0 、 G1 、 G2 、 G1+ 出第一版对比表；每类题至少  3 个带解读
的典型轨迹
4 用  extension 实现  search_docs （切块  +
embedding + 混合检索），跑  G3 、 G4
search_docs  单独的  recall@5 有数据；
G1 到  G4 在同一张表里可比
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 5 of 7

<!-- page: 6 -->

最终交付物
交付一个独立  Git 仓库、一份评估报告和一次  30 分钟的汇报。
仓库结构（语料文件体积大，只提交下载和转换脚本，不提交语料本身）：
pi-cli-retrieval-bench/
  README.md            # 环境、 pi 版本、模型、一键复现命令
  corpus/scripts/      # 下载与格式转换脚本
  questions/           # questions.jsonl ：题目、类别、参考答案、证据位置
  prompts/             # researcher.md 、打分器提示词
  extensions/          # search_docs 的  pi extension 及建索引脚本
  config/              # models.json （不含密钥）、各组  settings
  runner/              # 批量运行、 JSONL 解析、打分、汇总
  runs/                # 原始  JSONL 轨迹（可选  git-lfs 或只保留样本）
  report/              # 评估报告与图表
  notes/               # 每周周记
评估报告大纲：
1. 结论（ 1 ⻚内）：哪类任务、多大规模用纯  CLI 就够，哪类必须上  RAG ，推荐的混合方案。
2. 实验设置：模型及版本、 pi 版本、语料概况、题集分布、各组配置。
3. 主结果：分题型  × 分组的答对率与成本对比。
4. 规模曲线： S / M / L 三档下的准确率和  token 成本变化。
5. 行为分析：典型轨迹、失败模式分类、中文对  grep 的影响。
6. 上下文压缩：触发频率、压缩率、压缩前后的质量变化。
7. 局限性：只测了哪些模型和领域、打分器偏差，以及哪些结论不能外推。
约束与注意事项
数据安全：只用公开资料。任何公司内部文档、代码、会话都不进语料，也不发给公网模
型。
周 内容 验收标准
5 扩到  L 档； D 类⻓任务下调
compaction.reserveTokens  /
keepRecentTokens ，对比压缩前后质量；可
选：换一个模型复跑  G1 看结论是否稳定
出「规模 — 准确率  / 成本」曲线；至少  3
个压缩前后质量变化的对照案例
6 写评估报告，整理仓库保证可一键复现，准备
汇报
报告给出明确的选型建议；在全新目录里
按  README 能在半天内复跑  S 档  G1
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 6 of 7

<!-- page: 7 -->

API 额度： pi 跑实验用的模型  API 自己准备（如  DeepSeek 开放平台），并在服务商后台设
好消费上限。 coding agent 的免费余额用于写代码，一般不能拿来给  pi 调用。每批实验前先
用  5 题估算费用。 L 档和  D 类⻓任务最费钱，开跑前先报预算。
可复现：锁定  pi 版本（ pi -v ）和模型  id ，写进  README ；温度等采样参数固定；每次运
行的完整命令记入  runs/  下的元数据。
不改  pi 源码：新增能力一律用  extension 、 settings 、 --append-system-prompt  实现。这
样结论对应的是原生  pi 的行为。
安全隔离：只读组关闭  bash  / edit  / write ；带  bash 的组在容器或专用目录里跑，语料
目录挂成只读。无人值守运行前先读  security.md。
公平对比：各组提示词、模型、超时时间一致；不针对某一组调题或调提示词；失败的实验
如实写进报告。
每周汇报：每周五交周记时附  2 条  JSONL 轨迹的解读，讲清楚  Agent 每一步为什么这么
做。
参考：pi 仓库 · cli.md · json.md · models.md · settings.md · how-pi-works.md · 上下文工程实
战指南
实习任务：基于  pi agent 验证  CLI 工具做文档检索与研究总结的效率
Page 7 of 7
