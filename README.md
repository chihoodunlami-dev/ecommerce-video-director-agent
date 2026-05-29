# 电商短视频编导 Agent

当前版本：`v1.0 简洁版脚本生成工作台`

一个面向电商产品的短视频脚本生成 CLI + Streamlit 内部工具。项目采用“大模型优先 + 本地规则兜底”的混合架构：

- 本地规则负责产品类目识别、类目策略匹配、合规风险词检查和 Markdown 渲染。
- 大模型负责在明确 brief 和 JSON Schema 约束下生成脚本内容。
- 没有配置 API Key、模型超时或返回非法 JSON 时，会自动回退到本地模板生成。

## v1.0 大模型优先智能编导版说明

v1.0 将普通用户侧生成策略调整为“大模型优先”：前台页面不再展示“本地稳定生成”选项，`local_only` 仅保留为后台 fallback、测试和调试用途。

v1.0 已支持：

- 页面默认生成模式改为“大模型多版本生成”，并保留“本地生成 + 大模型润色”。
- 脚本生成优先调用 Qwen / OpenAI 等 LLM provider，失败时自动回退 `local_only`。
- 本地规则继续负责类目识别、真人实拍 / AI视频模式隔离、合规检查、输出结构校验、相似度规避和评分。
- metadata 持续记录 `requested_generation_mode`、`generation_mode`、`analysis_source`、`generation_source`、`provider`、`model`、`fallback_reason`。

### 简洁版前台说明

当前前台页面已回归为“简洁版脚本生成工作台”。用户打开网页后只看到产品信息输入、脚本模式、脚本子类型、生成模式、输出结果、一键复制、Markdown / JSON 导出、历史记录和 metadata。

“爆款素材学习 / 视频素材解析 / 参考视频仿写”功能已从前台隐藏，相关代码和测试暂时保留，后续如有需要可独立为单独工具。

v1.0 测试结果：

```bash
.venv/bin/python -m pytest -q
# 51 passed
```

## 功能

- 交互式输入产品名称、类目、人群、卖点、平台、视频时长、脚本模式。
- `script_mode` 支持 `live_action` 和 `ai_video`。
- 用户填写类目时优先使用用户类目；未填写时自动识别。
- 根据类目匹配脚本策略和场景。
- 输出真人实拍分镜脚本，或 AI 视频剧情脚本和可复制提示词。
- AI 视频脚本包含画面提示词、镜头运动、人物动作、产品露出方式、字幕文案、口播文案、负面提示词。
- 内置合规检查，标记高风险词并给出替代表达。
- 生成 Markdown 文件到 `outputs/`，同时可保存结构化 JSON 中间结果。

## v0.9 视频爆款解析版说明

v0.9 在 v0.8 稳定版基础上新增“视频素材解析 + 原创仿写生成”能力，不破坏脚本生成工作台、爆款素材学习库、真人实拍 / AI 视频模式隔离、`local_only`、`local_plus_llm_polish` 和 Qwen 调用链路。

v0.9 已支持：

- 在“爆款素材学习库”中切换素材类型：`文案 / 笔记素材`、`视频素材`。
- 手动上传视频文件并在页面预览。
- 按时间间隔抽取关键帧，默认每 3 秒抽一帧，最多 12 帧。
- 第一版优先使用用户手动补充的口播/字幕文案；没有转写服务时流程不中断。
- 生成视频爆款解析报告：基础信息、口播/字幕、前三秒钩子、节奏拆解、场景、人物关系、痛点、冲突、产品出现时机、卖点植入、镜头特点、字幕风格、情绪触发和转化引导。
- 提取可模仿结构，并结合脚本生成工作台中的当前产品信息生成 3 / 5 / 8 个原创脚本方案。
- 原创仿写只学习结构、节奏、钩子、场景逻辑和转化方式，不照抄原视频文案。
- 真人实拍模式不输出 AI 专用字段；AI 视频模式输出 AI画面提示词、镜头运动、负面提示词、连续性要求和可直接复制版提示词。
- 输出合规检查和相似度规避说明。

v0.9 新增文件：

- `director_agent/video_frame_extractor.py`
- `director_agent/video_transcriber.py`
- `director_agent/video_material_analyzer.py`
- `director_agent/video_imitation_writer.py`
- `rules/video_analysis_rules.json`
- `rules/video_imitation_rules.json`
- `references/video_library/index.json`

v0.9 存储与限制：

- 上传视频只做临时处理，不默认长期保存原视频。
- 默认保存视频标题、来源链接、口播/字幕转写、关键帧路径或摘要、视频分析报告和原创生成结果。
- 不做抖音、小红书等平台自动抓取。
- 没有可用自动转写服务时，需要用户手动粘贴口播或字幕文案。
- 大视频文件、原始视频目录、关键帧图片目录和临时目录已加入 `.gitignore`。

v0.9 测试结果：

```bash
.venv/bin/python -m pytest -q
# 45 passed
```

## v0.8 爆款素材学习版说明

v0.8 在 v0.7 稳定版基础上做增量升级，不破坏当前网页、真人实拍 / AI 视频模式隔离、`local_only`、`local_plus_llm_polish` 和 Qwen 调用链路。

v0.8 已支持：

- 爆款素材库：用户可手动添加同类优秀产品的视频文案、小红书笔记、网页链接和同行案例。
- 素材分析：提取开头钩子、用户痛点、目标人群、场景设计、人物关系、内容结构、卖点植入方式、情绪触发点、转化引导方式、可复用思路、不能照搬的表达和适合迁移的产品类型。
- 素材保存：分析结果可保存到 `references/copy_library/`，并记录索引 `references/copy_library/index.json`。
- 参考素材检索：可从素材库中选择 1-5 条参考素材。
- 原创迁移生成：基于参考素材的结构和思路，为当前产品生成 3-5 个原创脚本方案。
- 相似度规避：不照抄参考原文，不连续复用参考文案完整句子，并在输出中给出相似度规避说明。
- 模式隔离延续：真人实拍原创迁移不输出 AI画面提示词；AI视频原创迁移保留 AI画面提示词和负面提示词。
- 输出记录：原创迁移结果可导出 Markdown / JSON，metadata 记录参考素材 id 和链接，不复制参考文案全文。

v0.8 新增文件：

- `director_agent/copy_analyzer.py`
- `director_agent/reference_retriever.py`
- `director_agent/creative_rewriter.py`
- `rules/copy_analysis_rules.json`
- `rules/rewrite_rules.json`
- `rules/similarity_avoidance_rules.json`
- `references/copy_library/index.json`

v0.8 测试结果：

```bash
.venv/bin/python -m pytest -q
# 39 passed
```

## v0.7 稳定版说明

v0.7 已固化为稳定版。本版本不新增大功能，重点修复真人实拍模式和 AI 视频模式混用的问题；未改动 `llm.py`、Qwen 调用链路和大模型润色逻辑。

v0.7 已完成：

- 真人实拍 / AI视频模式隔离：`live_action` 和 `ai_video` 使用不同的子类型、风格选项和输出结构。
- 脚本子类型按模式动态切换：真人实拍只显示真人口播、真人剧情短剧、测评对比、直播切片、老板口播、探厂脚本、产品使用教程；AI 视频只显示 AI剧情短剧广告、AI产品广告片、AI生活方式种草、AI虚拟人口播、AI产品使用教程、AI分镜提示词。
- 真人实拍输出不再包含 AI 专用字段：不会输出 `AI画面提示词`、`负面提示词`、`连续性要求` 和可直接复制到 AI 视频工具的提示词。
- AI 视频输出保留 AI 专用字段：继续输出 `AI画面提示词`、`负面提示词`、`连续性要求` 和可直接复制版提示词。
- 非法组合自动纠正并写入 metadata：例如 `live_action + AI剧情短剧广告` 会自动纠正为真人实拍可用子类型，并记录 `normalized_script_subtype` 和 `normalization_reason`。

v0.7 测试结果：

```bash
.venv/bin/python -m pytest -q
# 34 passed
```

## v0.6 UI 稳定版说明

v0.6 已固化为 UI 稳定版。本版本不新增生成能力，不改动核心生成逻辑，重点优化 Streamlit 内部工具页面的使用体验和信息层级。

v0.6 已完成：

- 深色高级风格页面：整体采用深色背景、深灰表单卡片、高对比字段标签和金色强调按钮。
- 左中右三栏布局：左侧输入区，中间脚本输出区，右侧当前结果操作区。
- 输入区折叠分组：按基础信息、投放信息、脚本设定、生成配置组织表单字段。
- 输出区 Tab 展示：基础信息、剧情分镜、AI提示词、字幕/口播、合规检查、质量评分和 metadata 分区查看。
- 当前结果操作区：集中展示当前脚本的评分、复制、导出和历史记录。
- 脚本质量评分卡：大号展示分数，显示优秀/良好/可用/待优化等级和简短建议。
- 一键复制卡：支持复制完整提示词、字幕文案、对白/口播和 AI画面提示词。
- 导出文件卡：支持下载 Markdown、下载 JSON 和复制完整路径；默认只显示文件名与 `outputs/` 保存目录，不暴露完整绝对路径。
- 历史生成记录卡：本次会话内保留历史生成记录，展示产品名、类目、评分、时间、脚本模式、生成模式和文件名。

当前状态：

- 页面功能可用。
- 导出文件模块已优化。
- 生成逻辑、评分逻辑、文件输出逻辑保持 v0.5 稳定版能力。

## v0.4 页面体验说明

v0.4 不改动核心生成逻辑，重点把 v0.3 的能力变成更顺手的内部工具页面：

- 一键复制可直接复制版提示词。
- 一键复制字幕文案。
- 一键复制对白/口播。
- 一键复制 AI画面提示词。
- 支持示例产品快速载入。
- 输出区采用脚本预览和操作区分栏显示。
- 支持本次会话历史生成记录。
- 支持下载 Markdown 文件。

## v0.5 稳定版说明

v0.5 已固化为稳定版。本版本不替换现有本地生成逻辑，默认仍使用 `local_only` 的本地稳定生成。

v0.5 已支持：

- 本地稳定生成 `local_only`：规则系统稳定生成类目化 AI剧情短剧广告。
- 本地生成 + 大模型润色 `local_plus_llm_polish`：先本地生成完整脚本，再交给 Qwen/OpenAI 等 provider 在固定结构内润色。
- 大模型失败自动回退 `local_only`：没有 API Key、provider 不可用、返回非法 JSON、违反结构约束或合规扫描失败时，保留本地稳定结果。
- metadata 显示关键生成状态：`generation_source`、`provider`、`generation_mode`、`requested_generation_mode`、`fallback_reason`。
- 优化后的脚本质量评分：评分维度更关注画面提示词具体程度、台词自然度、镜头语言细节、产品植入自然度和 AI 视频可生成性。

`local_plus_llm_polish` 的约束：

- 大模型只能优化语言、画面感和剧情张力。
- 不允许改变产品类目、分镜结构、分镜时长、合规规则、产品卖点和输出字段。
- 润色结果会再次执行本地合规扫描。
- 没有 API Key、provider 不可用、返回非法 JSON 或违反结构约束时，自动回退到 `local_only`。
- Markdown 会展示 `generation_source`、`provider` 和 `generation_mode`。

v0.5 验证结果：

- Qwen 润色链路已跑通，`generation_mode=local_plus_llm_polish` 可成功输出。
- 同一产品“生姜洗发水”对比测试：
  - `local_only` 得分：95
  - `local_plus_llm_polish` 得分：98
- 测试结果：

```bash
.venv/bin/python -m pytest -q
# 28 passed
```

## v0.3 稳定版说明

v0.3 已固化为稳定版。本版本不再新增功能，后续优先做规则维护、内容质量评估和使用体验优化。

v0.3 在 v0.2 稳定版基础上增强“专业电商编导感”的类目化短剧能力：

- 新增 `rules/hook_rules.json`，按类目管理前三秒开头钩子。
- 新增 `rules/persona_rules.json`，按类目管理推荐人物关系。
- AI剧情短剧广告按类目区分剧情冲突、人物关系和产品植入方式，避免只替换产品名。
- 新增脚本质量评分模块，输出 0-100 分、优点和优化建议。
- Markdown 末尾展示脚本质量评分。
- Streamlit 页面展示评分，并支持分别复制可直接复制版提示词、字幕文案、对白/口播和 AI画面提示词。

v0.3 已支持能力：

- 类目钩子规则：通过 `rules/hook_rules.json` 为不同类目配置开头 3 秒钩子。
- 人物关系规则：通过 `rules/persona_rules.json` 为不同类目配置推荐人物关系。
- AI剧情短剧生成：支持按类目生成四段式 AI剧情短剧广告。
- 脚本质量评分：输出总分、分项评分、优点和需要优化的地方。
- 类目错配规避：例如冻品餐饮类会避开霸总甜宠，改用餐饮老板/后厨效率类逻辑。
- 合规扫描：生成后使用本地规则二次扫描风险词和夸大表达。
- Streamlit 页面展示：页面展示脚本结果、质量评分、合规检查、分项复制和 Markdown 下载。

v0.3 验收示例：

- 生姜洗发水：洗护个护类，生成职场逆袭/高级浴室场景的 AI剧情短剧广告。
- 乳霜纸：母婴纸品类，生成宝妈、宝宝、家庭擦拭场景的 AI剧情短剧广告。
- 免浆牛蛙块：冻品餐饮类，自动避开霸总甜宠，生成餐饮老板、后厨效率、出餐节奏逻辑。
- 1688包装袋：1688工厂定制类，生成工厂、探厂、客户定制和打包发货逻辑。

v0.3 测试结果：

```bash
.venv/bin/python -m pytest -q
# 24 passed
```

## v0.2 更新说明

v0.2 已标记为稳定版，当前阶段不再新增功能，后续优先做质量评估、规则维护和体验优化。

已支持能力：

- 类目识别：根据产品名称和卖点自动识别类目，用户填写类目时优先使用用户输入。
- 类目策略适配：从 `rules/category_rules.json` 读取类目策略、推荐人设、剧情风格、安全表达和规避表达。
- AI剧情短剧广告：支持 `ai_video + AI剧情短剧广告`，按类目生成四段式剧情短剧广告。
- 真人实拍脚本：支持输出真人实拍分镜、画面、口播、字幕和镜头建议。
- 合规检查：内置通用风险词，并补充洗护、母婴、食品等类目风险词。
- Markdown 输出：生成可归档、可复制的 Markdown，同时可保存结构化 JSON。
- Streamlit 页面：提供左右分栏内部工具页面，支持输入、生成、合规查看、复制和下载 Markdown。

v0.2 的 AI 剧情短剧广告固定包含：

- 人物设定
- 场景设定
- 分段剧情
- AI画面提示词
- 镜头运动
- 人物动作
- 产品露出方式
- 字幕文案
- 对白/口播
- 负面提示词
- 统一负面提示词
- 连续性要求
- 可直接复制版提示词

## 规则文件

- 类目识别和脚本策略：`rules/category_rules.json`
- 开头钩子：`rules/hook_rules.json`
- 人物关系：`rules/persona_rules.json`
- 合规风险词：`rules/compliance.yaml`

新增类目时，优先修改 `rules/category_rules.json`，不要先改 Python 代码。

## 安装

```bash
cd ecommerce-video-director-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

基础本地模式只依赖 Python 标准库即可运行；安装依赖后可使用 PyYAML、Pydantic 和 pytest。

## 运行

```bash
python3 main.py
```

按提示输入信息即可。`script_mode` 输入：

- `live_action`：真人实拍分镜脚本
- `ai_video`：AI 视频剧情脚本 + 视频提示词
- `ai_video + AI剧情短剧广告`：按类目生成四段式剧情短剧广告，包含统一负面提示词、连续性要求和可复制 AI 工具提示词。

## Web 页面

内部工具版使用 Streamlit：

```bash
streamlit run streamlit_app.py
```

如果使用项目虚拟环境：

```bash
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

页面结构：

- 左侧输入区：通过折叠分组填写基础信息、投放信息、脚本设定和生成配置。
- 中间输出区：通过 Tab 查看基础信息、剧情分镜、AI提示词、字幕/口播、合规检查、质量评分和 metadata。
- 右侧操作区：展示脚本质量评分卡、一键复制卡、导出文件卡和历史生成记录卡。

## Streamlit Community Cloud 部署

部署入口文件：

```text
streamlit_app.py
```

部署步骤：

1. 将当前项目上传到 GitHub 仓库。
2. 打开 Streamlit Community Cloud，新建 app。
3. Repository 选择当前项目仓库。
4. Branch 选择 `main`。
5. Main file path 填写：

```text
streamlit_app.py
```

6. 如需启用 Qwen/DashScope 大模型润色，在 Streamlit Cloud 的 Secrets 中配置：

```toml
DASHSCOPE_API_KEY = "你的真实 Key"
```

7. 如需限制为公司内部少数人使用，可在 Secrets 中增加访问密码：

```toml
APP_PASSWORD = "你的公司内部访问密码"
```

也可以配置多个访问密码：

```toml
APP_PASSWORDS = ["成员A的密码", "成员B的密码"]
```

8. 点击 Deploy，等待依赖安装完成后打开页面。

部署前检查：

- `requirements.txt` 已包含 Streamlit 页面和 LLM HTTP 调用需要的依赖：`streamlit`、`PyYAML`、`pydantic`、`requests`、`pytest`。
- `streamlit_app.py` 可作为 Streamlit Community Cloud 的主入口。
- 不要提交 `.env`、`.streamlit/secrets.toml`、`.venv/`、`outputs/` 等本地文件；这些已写入 `.gitignore`。
- `config/settings.yaml` 只保存 provider、endpoint、model 和环境变量名，不保存真实 API Key。
- `DASHSCOPE_API_KEY` 会优先从环境变量读取；没有环境变量时，会尝试读取 Streamlit Cloud Secrets。
- `APP_PASSWORD` / `APP_PASSWORDS` 只从环境变量或 Streamlit Cloud Secrets 读取，不写入代码仓库；未配置时页面保持公开访问，配置后会先显示访问密码页。

Streamlit Cloud Secrets 中如需启用 Qwen/DashScope 润色链路，配置：

```toml
DASHSCOPE_API_KEY = "你的key"
```

如需公司内部访问门禁，继续增加：

```toml
APP_PASSWORD = "你的公司内部访问密码"
```

当前配置使用 `llm.provider=domestic`、`api_key_env=DASHSCOPE_API_KEY`、`model=qwen-plus`。页面默认使用“大模型多版本生成”，也可选择“本地生成 + 大模型润色”；如果没有配置 `DASHSCOPE_API_KEY`，会自动回退到本地稳定生成 `local_only`。`local_only` 不再作为普通用户页面选项展示。

注意事项：

- 不要把 `.env` 或 `.streamlit/secrets.toml` 提交到 GitHub。
- 不配置 `DASHSCOPE_API_KEY` 时，系统会自动 fallback 到 `local_only`，不调用大模型。
- 使用“大模型多版本生成”或 `local_plus_llm_polish` 会调用 Qwen/DashScope，并消耗你的 API 额度。

## 大模型配置

配置文件在 `config/settings.yaml`。API Key 只通过环境变量或 Streamlit Cloud Secrets 提供，不写入配置文件。

### OpenAI

```bash
export OPENAI_API_KEY="your_api_key"
```

然后在 `config/settings.yaml` 中设置：

```yaml
llm:
  provider: openai
```

### 国内大模型兼容接口

设置 API Key，并在配置中填写兼容 OpenAI Chat Completions 风格的 endpoint：

```bash
export DASHSCOPE_API_KEY="your_api_key"
```

```yaml
llm:
  provider: domestic
  domestic:
    api_key_env: "DASHSCOPE_API_KEY"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    model: "qwen-plus"
```

国内 provider 会要求模型输出 JSON，并使用本地校验与最多 2 次修复重试。

## 示例产品

`examples/examples.yaml` 内置 5 个示例：

- 乳霜纸
- 生姜洗发水
- 洗护三件套
- 免浆牛蛙块
- 1688包装袋

## 测试

```bash
.venv/bin/python -m pytest -q
```

测试覆盖类目识别、合规检查、输出文件、Mock LLM 成功、非法 JSON fallback、超时 fallback、AI剧情短剧广告结构、类目风格规避、分镜总时长校验、类目化剧情逻辑和脚本质量评分。
