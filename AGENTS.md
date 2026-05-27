# AGENTS.md

你正在开发一个“电商短视频编导 Agent”。

## 项目目标

根据产品信息生成电商短视频脚本，支持真人实拍和 AI 视频生成两种模式。

## 核心原则

1. 所有输出必须服务于电商短视频转化。
2. 先识别产品类目，再选择脚本策略。
3. 不同类目不能套用同一种剧情。
4. 真人实拍脚本要给摄影师、演员、主播、剪辑师看。
5. AI 视频脚本要给 Seedance、即梦、可灵、Runway、海螺、Sora 等视频工具使用。
6. AI 视频脚本必须包含画面提示词、镜头运动、人物动作、产品露出方式、字幕文案、口播文案、负面提示词。
7. 必须进行电商合规检查。
8. 输出必须是 Markdown，方便复制和归档。

## 重点类目

1. 母婴纸品类
2. 洗护个护类
3. 食品零食类
4. 冻品餐饮类
5. 家清日用品类
6. 美妆护肤类
7. 1688工厂定制类
8. 宠物用品类
9. 厨房用品类

## 开发要求

1. Python 代码要模块化。
2. 模板、规则、示例分离。
3. 新增类目时优先修改 `rules/category_rules.json`。
4. 新增脚本类型时优先添加 `templates` 文件。
5. 所有核心函数要有基础测试。

## 当前实现约定

- CLI 入口是 `main.py`。
- 核心 Python 包是 `director_agent/`。
- 类目识别与策略规则读取自 `rules/category_rules.json`。
- 合规风险词读取自 `rules/compliance.yaml`。
- 示例输入读取自 `examples/examples.yaml`。
- 默认输出到 `outputs/`，生成文件不纳入版本管理。
- 默认 provider 是 `local`；配置 OpenAI 或国内大模型失败时必须回退到本地模板。

## 测试命令

从项目目录运行：

```bash
.venv/bin/python -m pytest -q
```

示例生成：

```bash
.venv/bin/python main.py --example 乳霜纸
.venv/bin/python main.py --example 生姜洗发水
```

