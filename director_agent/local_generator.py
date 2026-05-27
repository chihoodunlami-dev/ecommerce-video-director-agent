"""Local template fallback generator."""

from __future__ import annotations

from typing import Any, Dict, List

from .category import split_selling_points
from .config import load_hook_rules, load_persona_rules
from .models import ProductInfo


def build_local_script_payload(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
) -> Dict[str, Any]:
    selling_points = split_selling_points(product.selling_points)
    if not selling_points:
        selling_points = ["场景适配", "使用方便", "细节扎实"]

    if product.script_mode == "ai_video":
        if product.script_subtype == "AI剧情短剧广告":
            return _build_ai_drama_ad_payload(product, category, strategy, selling_points)
        return _build_ai_video_payload(product, category, strategy, selling_points)
    if product.script_subtype == "真人口播":
        return _build_live_action_talking_head_payload(product, category, strategy, selling_points)
    return _build_live_action_payload(product, category, strategy, selling_points)


def _build_live_action_payload(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
    selling_points: List[str],
) -> Dict[str, Any]:
    per_scene = max(4, int(product.duration / 5))
    scenes = [
        {
            "order": 1,
            "title": "痛点开场",
            "visual": f"在{strategy['scenes'][0]}展示目标人群的真实使用困扰，快速带出{product.product_name}。",
            "voiceover": f"如果你也在找一款适合{product.audience}的{product.product_name}，先看这个细节。",
            "subtitle": f"{product.product_name}，解决日常使用小麻烦",
            "shot": "中近景 + 手部特写",
            "duration_seconds": per_scene,
            "character_action": "演员拿起产品，对镜头展示使用前的真实困扰。",
        },
        {
            "order": 2,
            "title": "卖点展示",
            "visual": f"用近景展示产品细节，依次呈现：{'、'.join(selling_points[:3])}。",
            "voiceover": f"它的重点不是夸张承诺，而是把{'、'.join(selling_points[:2])}这些体验做扎实。",
            "subtitle": "细节看得见，使用更安心",
            "shot": "俯拍 + 微距特写",
            "duration_seconds": per_scene,
            "character_action": "主播用手展示产品质地、包装和关键细节。",
        },
        {
            "order": 3,
            "title": "场景验证",
            "visual": f"切换到{strategy['scenes'][1]}，用{strategy['proof_points'][0]}和{strategy['proof_points'][1]}验证卖点。",
            "voiceover": f"放到真实场景里，才知道它是不是适合日常高频使用。",
            "subtitle": f"{strategy['core_angle']}",
            "shot": "连续动作镜头",
            "duration_seconds": per_scene,
            "character_action": "演员按真实使用步骤完成一次演示，动作放慢方便摄影师捕捉。",
        },
        {
            "order": 4,
            "title": "人群转化",
            "visual": f"真人拿起产品面对镜头，给{product.audience}一个明确购买理由。",
            "voiceover": f"想要一款{category}好上手的选择，可以把{product.product_name}加入你的日常清单。",
            "subtitle": f"适合：{product.audience}",
            "shot": "正面口播 + 产品定格",
            "duration_seconds": per_scene,
            "character_action": "主播面对镜头总结适用人群，并把产品放在画面中心。",
        },
    ]
    return {
        "product_summary": f"{product.product_name}面向{product.audience}，核心卖点是{product.selling_points}。",
        "hook": f"{product.product_name}到底适不适合日常用？看这几个真实场景。",
        "scenes": scenes,
        "selling_points": selling_points,
        "ai_video_prompt": None,
        "compliance_notes": ["本地模板已避免极限承诺与医疗化承诺，最终以风险词扫描为准。"],
        "metadata": {
            "script_subtype": product.script_subtype or "真人实拍",
            "live_action_format": "storyboard",
            "live_action_details": _live_action_details(product, strategy),
        },
    }


def _build_live_action_talking_head_payload(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
    selling_points: List[str],
) -> Dict[str, Any]:
    durations = _split_duration(product.duration, 7)
    first_point = selling_points[0] if selling_points else "日常体验"
    second_point = selling_points[1] if len(selling_points) > 1 else first_point
    scene_context = product.scene_setting or strategy["scenes"][0]
    price_line = product.price_mechanism or "按页面当前机制选择适合自己的规格"
    scenes = [
        {
            "order": 1,
            "title": "开头3秒钩子",
            "visual": f"主播站在{scene_context}，手持{product.product_name}，开场直接展示产品和使用痛点。",
            "voiceover": f"先别急着买{product.product_name}，你真正要看的其实是这几个使用细节。",
            "subtitle": "先看细节，再决定要不要入手",
            "shot": "正面近景，开头快速推近产品",
            "duration_seconds": durations[0],
            "character_action": "主播看向镜头，抬手把产品放到胸前或桌面中心。",
        },
        {
            "order": 2,
            "title": "痛点引入",
            "visual": f"切到{product.audience}常见的使用场景，展示选择产品时的犹豫点。",
            "voiceover": f"很多{product.audience}选这类产品，最怕的是说得好听，真正用起来不顺手。",
            "subtitle": "日常高频使用，更要看真实体验",
            "shot": "中景口播 + 场景补拍",
            "duration_seconds": durations[1],
            "character_action": "主播一边讲痛点，一边指向产品关键位置。",
        },
        {
            "order": 3,
            "title": "产品介绍",
            "visual": f"产品正面、侧面和细节依次入镜，说明它属于{category}，适合{product.audience}。",
            "voiceover": f"这款{product.product_name}，重点不是夸张承诺，而是围绕{first_point}做日常使用体验。",
            "subtitle": f"{product.product_name}｜{category}",
            "shot": "产品特写 + 主播半身口播",
            "duration_seconds": durations[2],
            "character_action": "主播把产品转向镜头，保持包装和核心信息清晰。",
        },
        {
            "order": 4,
            "title": "卖点展开",
            "visual": f"逐条展示卖点：{'、'.join(selling_points[:3])}，用手部动作或实物细节辅助说明。",
            "voiceover": f"第一个看{first_point}，第二个看{second_point}，这些都更接近日常真实使用感。",
            "subtitle": "卖点拆开看，细节更清楚",
            "shot": "微距特写 + 手部演示",
            "duration_seconds": durations[3],
            "character_action": "主播配合手势做分点讲解，不做夸张表情。",
        },
        {
            "order": 5,
            "title": "使用场景",
            "visual": f"切换到{strategy['scenes'][0]}和{strategy['scenes'][1]}，展示产品被自然使用或摆放。",
            "voiceover": f"放到真实场景里看，它更适合那些想要{strategy['core_angle']}的人。",
            "subtitle": f"适合场景：{strategy['core_angle']}",
            "shot": "生活化跟拍 + 定点补光",
            "duration_seconds": durations[4],
            "character_action": "演员完成一次自然使用动作，主播补一句场景说明。",
        },
        {
            "order": 6,
            "title": "价格/机制",
            "visual": "主播指向屏幕侧边或桌面价格牌，用字幕呈现机制，不制造虚假紧迫感。",
            "voiceover": f"价格和规格重点看清楚：{price_line}，按自己的使用频率选就行。",
            "subtitle": price_line,
            "shot": "正面口播 + 字幕强调",
            "duration_seconds": durations[5],
            "character_action": "主播指向价格/规格信息区域，动作简洁。",
        },
        {
            "order": 7,
            "title": "结尾引导",
            "visual": f"{product.product_name}放在画面中心，主播给出理性下单引导。",
            "voiceover": f"如果你正好需要一款适合{product.audience}的选择，可以先收藏，对照自己的需求再决定。",
            "subtitle": "先收藏，对照需求理性选择",
            "shot": "产品定格 + 主播正面收尾",
            "duration_seconds": durations[6],
            "character_action": "主播把产品轻放到镜头前，最后看向镜头收尾。",
        },
    ]
    return {
        "product_summary": f"{product.product_name}面向{product.audience}，适合真人口播讲清楚{product.selling_points}。",
        "hook": f"{product.product_name}值不值得入手，先用真人口播把关键细节讲清楚。",
        "scenes": scenes,
        "selling_points": selling_points,
        "ai_video_prompt": None,
        "compliance_notes": ["真人口播脚本采用体验化表达，避免绝对化和医疗化承诺。"],
        "metadata": {
            "script_subtype": "真人口播",
            "live_action_format": "talking_head",
            "live_action_details": _live_action_details(product, strategy),
        },
    }


def _build_ai_video_payload(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
    selling_points: List[str],
) -> Dict[str, Any]:
    per_scene = max(4, int(product.duration / 5))
    scenes = [
        {
            "order": 1,
            "title": "视觉钩子",
            "visual": f"干净明亮的{strategy['scenes'][0]}，镜头推近{product.product_name}，突出质感和使用场景。",
            "voiceover": f"给{product.audience}的日常选择，可以从这个{product.product_name}开始。",
            "subtitle": f"{product.product_name} 场景化展示",
            "shot": "slow push-in, product close-up",
            "duration_seconds": per_scene,
            "character_action": "人物从画面侧边伸手拿起产品，自然看向产品包装。",
            "product_exposure": "产品正面包装占画面中心，品牌和核心规格保持清晰可见。",
            "negative_prompt": "blurry, distorted package, unreadable text, exaggerated claim",
        },
        {
            "order": 2,
            "title": "卖点可视化",
            "visual": f"用动态图形和实物动作表现{'、'.join(selling_points[:3])}，画面保持真实电商质感。",
            "voiceover": f"把核心体验拆开看，重点是{'、'.join(selling_points[:2])}。",
            "subtitle": "核心卖点清晰呈现",
            "shot": "macro detail, smooth transition",
            "duration_seconds": per_scene,
            "character_action": "人物用手演示产品核心使用动作，动作慢且清楚。",
            "product_exposure": "产品在动作开始和结束时各露出一次，细节特写不少于 2 秒。",
            "negative_prompt": "fake comparison, overpromising, messy background, low quality",
        },
        {
            "order": 3,
            "title": "使用场景",
            "visual": f"切到{strategy['scenes'][1]}和{strategy['scenes'][2]}，展示产品被自然使用的过程。",
            "voiceover": f"不靠夸张表达，用真实场景说明它为什么值得被看见。",
            "subtitle": strategy["core_angle"],
            "shot": "lifestyle scene, handheld realism",
            "duration_seconds": per_scene,
            "character_action": "人物完成一次完整使用流程，表情自然，不做夸张反应。",
            "product_exposure": "产品与使用场景同框，避免只拍人物不露产品。",
            "negative_prompt": "medical effect, unrealistic transformation, exaggerated facial expression",
        },
        {
            "order": 4,
            "title": "转化收束",
            "visual": f"产品整齐摆放，出现平台风格的购买提示，但不使用夸大促销话术。",
            "voiceover": f"在{product.platform}看到它时，记得重点看规格、场景和自己的使用需求。",
            "subtitle": "按需求选择，理性下单",
            "shot": "hero product shot, clean background",
            "duration_seconds": per_scene,
            "character_action": "人物把产品放回画面中心，手指轻点包装或规格区域。",
            "product_exposure": "结尾定格产品完整包装和关键卖点字幕。",
            "negative_prompt": "hard sell, fake discount, distorted hands, unreadable subtitle",
        },
    ]
    prompt = (
        f"生成一支{product.duration}秒中文电商短视频，产品是{product.product_name}，"
        f"类目为{category}，目标人群是{product.audience}。画面风格真实、干净、适合{product.platform}，"
        f"突出{'、'.join(selling_points[:3])}。镜头包含产品特写、真实使用场景、人物自然动作、产品露出、细节展示和结尾定格。"
        "避免夸张疗效、过度承诺和虚假对比。negative prompt: blurry, distorted text, exaggerated medical claim, low quality."
    )
    return {
        "product_summary": f"{product.product_name}面向{product.audience}，适合用 AI 视频做场景化种草。",
        "hook": f"用一支真实质感 AI 短片，看懂{product.product_name}的使用场景。",
        "scenes": scenes,
        "selling_points": selling_points,
        "ai_video_prompt": prompt,
        "compliance_notes": ["AI 视频提示词已加入避免夸大和不当承诺的负面约束。"],
    }


def _build_ai_drama_ad_payload(
    product: ProductInfo,
    category: str,
    strategy: Dict[str, Any],
    selling_points: List[str],
) -> Dict[str, Any]:
    video_style, style_note = _choose_drama_style(product, strategy)
    aspect_ratio = product.aspect_ratio or "9:16"
    ai_tool = product.ai_tool or "Seedance"
    opening_hook = _select_opening_hook(category, product)
    persona_relation = _select_persona_relation(category, product, strategy)
    character_setting = product.character_setting or persona_relation or _default_character_setting(strategy)
    scene_setting = product.scene_setting or _default_scene_setting(strategy)
    core_pain_point = _core_pain_point(category, product)
    product_placement = _product_placement(category, product)
    compliance_suggestion = _compliance_suggestion(strategy)
    unified_negative_prompt = (
        "blurry, low quality, distorted hands, unreadable package, wrong product, "
        "exaggerated claim, medical claim, fake discount, messy subtitles"
    )
    continuity_requirements = (
        f"保持同一{character_setting}、同一{product.product_name}包装、同一{scene_setting}光线风格；"
        "产品外观、服装、空间方向和字幕风格在四段中保持连续。"
    )
    time_segments = _drama_time_segments(product.duration)
    scene_specs = _drama_scene_specs(
        category,
        product,
        strategy,
        selling_points,
        video_style,
        opening_hook,
        persona_relation,
    )

    scenes = []
    prompt_parts = [
        f"生成一支{product.duration}秒{aspect_ratio}中文电商AI剧情短剧广告。",
        f"产品：{product.product_name}。",
        f"视频风格：{video_style}。",
        f"人物设定：{character_setting}。",
        f"场景设定：{scene_setting}。",
    ]
    for index, ((label, duration), spec) in enumerate(zip(time_segments, scene_specs), start=1):
        scenes.append(
            {
                "order": index,
                "title": label,
                "plot": spec["plot"],
                "visual": spec["visual"],
                "voiceover": spec["voiceover"],
                "subtitle": spec["subtitle"],
                "shot": spec["shot"],
                "duration_seconds": duration,
                "character_action": spec["character_action"],
                "product_exposure": spec["product_exposure"],
                "negative_prompt": spec["negative_prompt"],
            }
        )
        prompt_parts.append(
            f"{label}：{_clean_sentence(spec['visual'])} 镜头运动：{_clean_sentence(spec['shot'])} "
            f"人物动作：{_clean_sentence(spec['character_action'])} 产品露出：{_clean_sentence(spec['product_exposure'])} "
            f"字幕：{_clean_sentence(spec['subtitle'])} 对白/口播：{_clean_sentence(spec['voiceover'])}。"
        )

    prompt_parts.extend(
        [
            f"统一负面提示词：{unified_negative_prompt}。",
            f"连续性要求：{continuity_requirements}",
            f"适合AI工具：{ai_tool}。",
        ]
    )

    return {
        "product_summary": f"{product.product_name}面向{product.audience}，适合生成类目化AI剧情短剧广告。",
        "hook": opening_hook or scene_specs[0]["subtitle"],
        "scenes": scenes,
        "selling_points": selling_points,
        "ai_video_prompt": "\n".join(prompt_parts),
        "compliance_notes": ["短剧脚本已按类目规避不合适剧情风格，并采用体验化表达。"],
        "metadata": {
            "video_type": "AI剧情短剧广告",
            "script_subtype": "AI剧情短剧广告",
            "aspect_ratio": aspect_ratio,
            "video_style": video_style,
            "requested_video_style": product.video_style or product.script_style,
            "style_adjustment": style_note,
            "ai_tool": ai_tool,
            "character_setting": character_setting,
            "persona_relation": persona_relation,
            "scene_setting": scene_setting,
            "core_pain_point": core_pain_point,
            "opening_hook": opening_hook,
            "product_placement": product_placement,
            "compliance_suggestion": compliance_suggestion,
            "unified_negative_prompt": unified_negative_prompt,
            "continuity_requirements": continuity_requirements,
        },
    }


def _split_duration(duration: int, count: int) -> List[int]:
    base = max(1, int(duration / count))
    parts = [base for _ in range(count)]
    while sum(parts) > duration:
        index = max(range(count), key=lambda idx: parts[idx])
        parts[index] -= 1
    while sum(parts) < duration:
        parts[sum(parts) % count] += 1
    return parts


def _live_action_details(product: ProductInfo, strategy: Dict[str, Any]) -> List[Dict[str, str]]:
    scenes = strategy.get("scenes") or ["真实使用场景"]
    props = f"{product.product_name}、辅助道具、桌面或手持展示物"
    return [
        {
            "props": props,
            "scene": scenes[min(index, len(scenes) - 1)],
            "editing_rhythm": "开头快切抓注意，中段用特写承接，结尾放慢给产品定格。",
            "closing_guidance": "引导收藏、对照需求查看规格，避免夸大承诺。",
        }
        for index in range(7)
    ]


def _choose_drama_style(product: ProductInfo, strategy: Dict[str, Any]) -> tuple:
    requested = product.video_style or product.script_style
    allowed = list(dict.fromkeys((strategy.get("recommended_plot_styles") or []) + (strategy.get("recommended_ai_styles") or [])))
    unsuitable = set(strategy.get("unsuitable_plot_styles") or [])
    if requested and requested not in unsuitable and (not allowed or requested in allowed):
        return requested, ""
    fallback = allowed[0] if allowed else "真实电商风"
    if requested and requested != fallback:
        return fallback, f"已避开不适合该类目的剧情风格，改用：{fallback}"
    return fallback, ""


def _default_character_setting(strategy: Dict[str, Any]) -> str:
    personas = strategy.get("recommended_personas") or []
    return personas[0] if personas else "目标用户"


def _default_scene_setting(strategy: Dict[str, Any]) -> str:
    scenes = strategy.get("scenes") or []
    return scenes[0] if scenes else "真实使用场景"


def _select_opening_hook(category: str, product: ProductInfo) -> str:
    hooks = (load_hook_rules().get("categories") or {}).get(category) or []
    if not hooks:
        return f"{product.product_name}的真实使用痛点，前三秒先讲清楚。"
    index = sum(ord(char) for char in product.product_name) % len(hooks)
    return str(hooks[index])


def _select_persona_relation(category: str, product: ProductInfo, strategy: Dict[str, Any]) -> str:
    personas = (load_persona_rules().get("categories") or {}).get(category) or []
    if personas:
        requested_style = product.video_style or product.script_style
        style_keywords = {
            "职场": "职场",
            "霸总": "霸总",
            "闺蜜": "闺蜜",
            "宝妈": "宝妈",
            "家庭": "家庭",
            "餐饮": "餐饮",
            "后厨": "厨师",
            "厨师": "厨师",
            "工厂": "工厂",
            "探厂": "工厂",
            "客户定制": "客户",
        }
        for style_token, persona_token in style_keywords.items():
            if requested_style and style_token in requested_style:
                for persona in personas:
                    if persona_token in persona:
                        return str(persona)
        index = sum(ord(char) for char in product.product_name + product.audience) % len(personas)
        return str(personas[index])
    fallback = strategy.get("recommended_personas") or []
    return str(fallback[0]) if fallback else "目标用户"


def _core_pain_point(category: str, product: ProductInfo) -> str:
    mapping = {
        "洗护个护类": "洗前状态不理想，用户希望日常护理后看起来更清爽蓬松。",
        "母婴纸品类": "家庭高频擦拭既要柔软，也要经得住真实使用。",
        "冻品餐饮类": "备菜慢、出餐压力大，需要更省时稳定的食材选择。",
        "1688工厂定制类": "商家打包效率低、规格不匹配，影响发货节奏。",
        "食品零食类": "休闲场景需要开袋即食、有分享感、能快速带来食欲记忆点。",
        "家清日用品类": "家务高频又琐碎，用户需要更顺手、省心的清洁或收纳选择。",
    }
    return mapping.get(category, f"{product.audience}在真实场景中需要更顺手的产品选择。")


def _product_placement(category: str, product: ProductInfo) -> str:
    mapping = {
        "洗护个护类": "产品以浴室台面、按压起泡、洗后定格三次自然露出。",
        "母婴纸品类": "产品在亲子擦拭、湿水按压、家庭多点摆放中露出。",
        "冻品餐饮类": "产品在开袋、下锅、成品夹起、后厨备货中露出。",
        "1688工厂定制类": "产品在工厂产线、规格对比、装袋封口、批量发货中露出。",
        "食品零食类": "产品在开袋声、近景质地、多人分享和囤货定格中露出。",
        "家清日用品类": "产品在脏乱痛点、使用动作、清爽收纳和结尾定格中露出。",
    }
    return mapping.get(category, f"{product.product_name}在痛点、使用、转化镜头中自然露出。")


def _compliance_suggestion(strategy: Dict[str, Any]) -> str:
    safe = "、".join(strategy.get("safe_claims") or ["体验化表达", "真实场景展示"])
    return f"建议使用：{safe}；避免诊疗功效、过强数字承诺、排名背书、长期效果承诺、虚假价格和过度承诺。"


def _clean_sentence(value: str) -> str:
    return value.rstrip("。.!！ ")


def _drama_time_segments(duration: int) -> List[tuple]:
    if duration == 48:
        return [
            ("【0-3秒 冲击力开篇】", 3),
            ("【4-20秒 冲突铺垫】", 17),
            ("【21-35秒 产品植入】", 15),
            ("【36-48秒 情绪反转 / 成交引导】", 13),
        ]

    base = [3, 17, 15, 13]
    total = sum(base)
    raw = [duration * value / total for value in base]
    parts = [max(1, int(value)) for value in raw]
    while sum(parts) > duration:
        index = max(range(len(parts)), key=lambda idx: parts[idx])
        parts[index] -= 1
    while sum(parts) < duration:
        fractions = [raw[idx] - int(raw[idx]) for idx in range(len(raw))]
        index = max(range(len(parts)), key=lambda idx: fractions[idx])
        parts[index] += 1

    names = ["冲击力开篇", "冲突铺垫", "产品植入", "情绪反转 / 成交引导"]
    labels = []
    start = 0
    for name, part in zip(names, parts):
        end = start + part
        labels.append((f"【{start}-{end}秒 {name}】", part))
        start = end
    return labels


def _drama_scene_specs(
    category: str,
    product: ProductInfo,
    strategy: Dict[str, Any],
    selling_points: List[str],
    video_style: str,
    opening_hook: str,
    persona_relation: str,
) -> List[Dict[str, str]]:
    product_points = "、".join(selling_points[:3])
    scene_a = strategy.get("scenes", ["真实场景"])[0]
    scene_b = strategy.get("scenes", [scene_a, scene_a])[1]
    proof_a = strategy.get("proof_points", ["细节展示"])[0]
    proof_b = strategy.get("proof_points", [proof_a, proof_a])[1]

    if category == "冻品餐饮类":
        return [
            {
                "plot": f"{persona_relation}在饭点前遇到订单突然增多，后厨备菜来不及，老板看着排单开始焦虑。",
                "visual": f"{scene_a}里订单小票连续弹出，厨师快速翻找食材，画面紧张但真实。",
                "shot": "handheld fast push-in, kitchen documentary style",
                "character_action": "餐饮老板皱眉看排单，厨师加快备菜动作。",
                "product_exposure": f"{product.product_name}包装在备菜台边缘首次露出。",
                "subtitle": opening_hook,
                "voiceover": "订单一多，备菜慢半拍，出餐节奏就容易乱。",
                "negative_prompt": "romantic CEO plot, luxury office, exaggerated love scene, low quality",
            },
            {
                "plot": "厨师对比传统处理流程和免浆处理流程，冲突点落在省时与出品稳定。",
                "visual": f"{scene_a}切到{scene_b}，一边是繁琐处理，一边是开袋即用的流程对比。",
                "shot": "split-screen comparison, top-down kitchen shot",
                "character_action": "厨师一边看时间一边快速开袋、分装、下锅。",
                "product_exposure": f"{product.product_name}完整包装正面朝向镜头，随后开袋展示。",
                "subtitle": "省掉繁琐备菜，后厨节奏更顺",
                "voiceover": f"重点是{product_points}，适合爆炒、火锅这些高频出餐场景。",
                "negative_prompt": "medical claim, dieting claim, overpromising, dirty kitchen",
            },
            {
                "plot": "产品正式进入烹饪镜头，食材下锅后快速形成食欲感。",
                "visual": "热锅、油光、食材翻炒，蒸汽和酱汁包裹食材，成品色泽饱满。",
                "shot": "macro food close-up, slow motion stir-fry, steam highlight",
                "character_action": "厨师翻锅、夹起成品，老板在旁确认出餐速度。",
                "product_exposure": f"{proof_a}和{proof_b}时让包装与成品同框出现。",
                "subtitle": "出餐快一点，翻台就从容一点",
                "voiceover": "好用的半成品食材，不是替你做菜，是帮后厨把节奏稳住。",
                "negative_prompt": "raw unsafe food, false health benefit, blurry steam, unrealistic texture",
            },
            {
                "plot": "老板看到出餐顺了，镜头切到顾客上桌和后厨备货，完成成交引导。",
                "visual": "成品端上桌，顾客夹起尝试，后厨整齐备货，老板轻松点头。",
                "shot": "smooth pull-back, hero food shot, warm restaurant light",
                "character_action": "老板把产品放进冷柜备货区，厨师继续稳定出餐。",
                "product_exposure": f"结尾定格{product.product_name}包装、成品菜和备货场景三者同框。",
                "subtitle": "适合餐饮后厨和家庭快手菜场景",
                "voiceover": f"想让备菜更省心，可以重点看看这款{product.product_name}。",
                "negative_prompt": "romantic plot, fake discount, health cure, distorted package",
            },
        ]

    if category == "洗护个护类":
        return [
            {
                "plot": f"{persona_relation}关系里，主角准备出门却发现头发贴头皮，重要场合前状态不够清爽。",
                "visual": f"{video_style}画面中，主角站在镜前整理发型，发根扁塌，浴室光线高级干净。",
                "shot": "medium mirror shot, slow push-in",
                "character_action": "人物用手拨开发根，表情从犹豫转为想改变状态。",
                "product_exposure": f"{product.product_name}在镜台边缘虚化露出，包装保持可辨。",
                "subtitle": opening_hook,
                "voiceover": "状态差一点，整个人的精致感就少一截。",
                "negative_prompt": "hair growth claim, hair loss cure, medical scalp treatment, low quality",
            },
            {
                "plot": "闺蜜或同事提醒主角，问题不在造型，而在日常清洁护理的体验。",
                "visual": f"镜头切到{scene_a}，两人自然对话，画面保持真实生活广告质感。",
                "shot": "over-shoulder dialogue shot, soft bathroom light",
                "character_action": "配角拿起产品递给主角，主角低头看瓶身卖点。",
                "product_exposure": f"产品正面包装占画面三分之一，卖点通过字幕表达：{product_points}。",
                "subtitle": "先把日常清洁护理做顺",
                "voiceover": f"这支{product.product_name}主打{product_points}，更适合日常护理场景。",
                "negative_prompt": "anti-hair-loss promise, permanent repair, medical repair, exaggerated effect",
            },
            {
                "plot": "产品进入使用镜头，泡沫、冲洗、香氛和洗后质感被可视化。",
                "visual": f"{proof_a}、{proof_b}、发丝水光和瓶身细节交替出现，节奏精致克制。",
                "shot": "macro close-up, slow motion water flow, smooth transition",
                "character_action": "人物按压泵头、揉出泡沫、轻柔按摩发根并冲洗。",
                "product_exposure": "按压泵头、瓶身特写、浴室台面定格三次自然露出。",
                "subtitle": "清爽、蓬松、香氛感，日常护理刚刚好",
                "voiceover": "不用夸张承诺，把清爽和蓬松感做进日常体验里就够了。",
                "negative_prompt": "before-after fake transformation, scalp disease cure, distorted text",
            },
            {
                "plot": "主角整理发型后自信出门，情绪从焦虑变轻松，落到理性种草。",
                "visual": "自然窗光下主角轻梳发根，发丝自然蓬起，产品在梳妆台与镜面同框。",
                "shot": "hero vanity shot, gentle pull-back, cinematic natural light",
                "character_action": "人物拿起包出门前回头看镜子，微笑点头。",
                "product_exposure": f"结尾产品完整包装与人物状态同框，字幕提示适合{product.audience}。",
                "subtitle": "发根更显蓬松，出门状态更在线",
                "voiceover": f"如果你也想要清爽一点的日常护理，可以试试{product.product_name}。",
                "negative_prompt": "guaranteed growth, medical endorsement, fake ranking, overexposure",
            },
        ]

    if category == "母婴纸品类":
        return [
            {
                "plot": f"{persona_relation}在家庭早晨场景里，宝宝打喷嚏、宝妈急着找纸，冲突落在擦拭是否够柔和、够顺手。",
                "visual": f"{scene_a}里宝妈抱着宝宝，桌面抽纸、奶瓶和玩具同框，画面温柔明亮。",
                "shot": "warm handheld close-up, quick emotional push-in",
                "character_action": "宝妈一手抱宝宝，一手抽纸轻轻擦拭鼻尖和小手。",
                "product_exposure": f"{product.product_name}放在亲子桌面中心，抽取动作让包装正面自然露出。",
                "subtitle": opening_hook,
                "voiceover": "家里有宝宝，纸巾看的不是一句口号，是每一次擦拭的手感。",
                "negative_prompt": "medical baby claim, 100 percent sterilization, unsafe baby handling, low quality",
            },
            {
                "plot": "闺蜜来家里做客，看到宝妈频繁抽纸，提出湿水、擦脸、擦小手这些真实高频场景。",
                "visual": f"镜头从{scene_a}切到{scene_b}，纸巾湿水按压、擦拭宝宝用品、擦鼻子动作连续出现。",
                "shot": "top-down test shot, soft home light, gentle cut",
                "character_action": "宝妈把纸巾沾水后按压，再轻轻擦过手背和宝宝用品边缘。",
                "product_exposure": f"包装与湿水按压动作同框，字幕呈现卖点：{product_points}。",
                "subtitle": "擦脸、擦鼻子、擦小手，都要更顺手",
                "voiceover": f"这款{product.product_name}主打{product_points}，适合家庭日常高频擦拭。",
                "negative_prompt": "absolute safety claim, baby disease treatment, exaggerated proof, messy room",
            },
            {
                "plot": "产品正式进入亲子使用场景，纸张触感、湿水韧性和家庭多点摆放被具体展示。",
                "visual": f"{proof_a}、{proof_b}、护理台抽取、餐桌擦拭四个细节快速串联，色调干净柔和。",
                "shot": "macro tissue texture, slow pan, gentle family montage",
                "character_action": "宝妈把纸巾放到护理台、餐桌和客厅，家人顺手抽取使用。",
                "product_exposure": "护理台、餐桌、客厅三处都让产品包装完整出现一次。",
                "subtitle": "柔软触感和湿水表现，放进真实家庭场景看",
                "voiceover": "不做夸张承诺，用触感、湿水和高频场景说明它为什么适合放在家里。",
                "negative_prompt": "medical endorsement, treatment claim, 100 percent claim, distorted baby",
            },
            {
                "plot": "宝宝状态安稳，宝妈把产品加入家庭囤货区，情绪从慌乱变成从容。",
                "visual": "亲子区恢复整洁，纸巾和宝宝用品整齐摆放，宝妈轻松把一提纸放入收纳柜。",
                "shot": "warm pull-back, product hero shot, clean home composition",
                "character_action": "宝妈对宝宝微笑，随后整理家庭囤货区。",
                "product_exposure": f"结尾定格{product.product_name}、宝宝用品和家庭收纳场景同框。",
                "subtitle": "家里高频用纸，选柔软也选顺手",
                "voiceover": f"给有宝宝的家庭和敏感擦拭场景，可以重点看看{product.product_name}。",
                "negative_prompt": "guaranteed baby safety, fake ranking, hard sell, unreadable package",
            },
        ]

    if category == "1688工厂定制类":
        return [
            {
                "plot": f"{persona_relation}在打包高峰前对接需求，客户催发货但包装袋规格不匹配，工厂老板直接带客户看产线。",
                "visual": f"{scene_a}里产线运转，客户拿着样品袋和订单单据，镜头扫过仓库货架和打包台。",
                "shot": "factory walk-through, fast dolly-in, documentary commercial style",
                "character_action": "工厂老板指向产线，客户拿样品袋比对尺寸。",
                "product_exposure": f"{product.product_name}样品袋在客户手里首次露出，规格标签清晰可见。",
                "subtitle": opening_hook,
                "voiceover": "商家做发货，包装袋不是好看就够，关键是规格对、封口顺、能跟上节奏。",
                "negative_prompt": "luxury romance plot, fake lowest price, official exclusive claim, low quality",
            },
            {
                "plot": "采购提出多规格、封口、承重和批量交付的担心，工厂用样品和打包流程逐一回应。",
                "visual": f"镜头切到{scene_b}，不同规格包装袋铺开，商品放入、撕膜封口、贴单动作连续展示。",
                "shot": "top-down specification comparison, close-up sealing motion",
                "character_action": "业务员拿出三种规格，打包员演示装袋封口并放上传送台。",
                "product_exposure": f"产品正面、侧面厚度和封口区域分别特写，字幕呈现：{product_points}。",
                "subtitle": "规格合适，打包台才不会卡住",
                "voiceover": f"{product.product_name}重点看{product_points}，更适合电商发货和批量采购沟通。",
                "negative_prompt": "absolute lowest price, national factory claim, fake certification, distorted text",
            },
            {
                "plot": "产品进入真实打包镜头，客户看到从装入商品到快递揽收的完整效率链路。",
                "visual": f"{proof_a}、{proof_b}、批量打包、快递揽收四个镜头衔接，画面利落有工厂实感。",
                "shot": "macro packaging close-up, conveyor tracking shot, quick rhythmic cuts",
                "character_action": "打包员连续装袋、封口、贴单，客户在旁边点头记录。",
                "product_exposure": "每次装袋封口时保留包装袋完整轮廓，最后与批量成品同框。",
                "subtitle": "从样品到批量发货，流程要看得见",
                "voiceover": "探厂不是只拍机器，要把商家真正关心的规格、打包和交付拍清楚。",
                "negative_prompt": "fake factory scale, unreadable logo, unrealistic production speed",
            },
            {
                "plot": "客户确认样品，工厂老板给出按需求沟通的转化引导，镜头落到仓库备货和打包台。",
                "visual": "客户拿着样品袋和订单确认单，背景是整齐仓库和正在打包的工位。",
                "shot": "smooth pull-back, warehouse hero shot, clean industrial light",
                "character_action": "工厂老板把样品袋递给客户，业务员在旁记录规格需求。",
                "product_exposure": f"结尾定格{product.product_name}多规格样品、打包台和仓库货架。",
                "subtitle": "商家打包耗材，先按规格和用量来选",
                "voiceover": f"如果你是电商商家，可以把{product.product_name}按规格、数量和定制需求聊清楚。",
                "negative_prompt": "fake discount, guaranteed lowest price, exaggerated delivery promise",
            },
        ]

    if category == "食品零食类":
        return [
            {
                "plot": f"{persona_relation}在办公室下午犯困，抽屉里翻不到合适零食，同事被开袋声吸引。",
                "visual": f"{scene_a}上电脑、咖啡和零食袋同框，人物停下工作看向抽屉。",
                "shot": "quick desk push-in, snack close-up, light office comedy rhythm",
                "character_action": "人物打开抽屉拿出零食，旁边同事探头看过来。",
                "product_exposure": f"{product.product_name}包装从抽屉里被拿出，正面朝向镜头。",
                "subtitle": opening_hook,
                "voiceover": "下午三点想提提精神，手边有一口顺手的小零食就很关键。",
                "negative_prompt": "dieting claim, medical benefit, cure claim, messy eating",
            },
            {
                "plot": "同事想尝，主角先从开袋声、近景质地和分享场景证明不是一个人吃完就算。",
                "visual": f"切到{scene_b}，开袋、倒出、近景质地、多人伸手分享连续出现。",
                "shot": "macro texture shot, crisp sound emphasis, overhead sharing shot",
                "character_action": "人物撕开包装，倒在小碟里递给同事。",
                "product_exposure": f"包装和零食实物同框，字幕呈现卖点：{product_points}。",
                "subtitle": "开袋即食，办公室分享更有氛围",
                "voiceover": f"重点是{product_points}，适合下午茶、追剧和朋友分享。",
                "negative_prompt": "weight-loss promise, health cure, exaggerated appetite effect",
            },
            {
                "plot": "产品进入口感和场景镜头，办公室、追剧和囤货理由被拆成三个短动作。",
                "visual": f"{proof_a}、{proof_b}、多人分享和桌面囤货快速切换，画面干净有食欲。",
                "shot": "macro bite close-up, smooth tabletop pan, warm snack lighting",
                "character_action": "人物轻拿零食、分享给同事、把剩余包装放回抽屉。",
                "product_exposure": "开袋、入口前、桌面分享和囤货定格都让包装自然出现。",
                "subtitle": "小包装放身边，休闲场景随手拿",
                "voiceover": "好吃不好吃要靠真实口感镜头和分享反应，不用夸张功效。",
                "negative_prompt": "medical claim, fake nutrition claim, dirty desk, distorted food",
            },
            {
                "plot": "同事一起下单或加入办公室零食角，结尾落到理性囤货。",
                "visual": "办公室零食角整齐摆放，几个人自然拿取，包装和桌面场景形成定格。",
                "shot": "friendly group pull-back, product hero shot, bright office light",
                "character_action": "主角把零食放入共享零食篮，同事点头拿起一包。",
                "product_exposure": f"结尾定格{product.product_name}包装、零食篮和分享场景。",
                "subtitle": "适合办公室、追剧和朋友分享",
                "voiceover": f"如果你也想囤点休闲小零食，可以看看{product.product_name}。",
                "negative_prompt": "fake discount, diet effect, health treatment, unreadable package",
            },
        ]

    if category == "家清日用品类":
        return [
            {
                "plot": f"{persona_relation}做完饭后看到厨房台面、水槽和地面同时变乱，家务压力一下被放大。",
                "visual": f"{scene_a}里水槽、台面和清洁工具同框，人物停在门口叹气但画面真实克制。",
                "shot": "wide messy kitchen reveal, fast push-in",
                "character_action": "人物卷起袖子，看向水槽和台面，准备开始清洁。",
                "product_exposure": f"{product.product_name}放在水槽边，作为即将使用的解决工具首次露出。",
                "subtitle": opening_hook,
                "voiceover": "家务烦的不是做一次，是每次都要从乱糟糟开始。",
                "negative_prompt": "100 percent sterilization, permanent odor removal, medical cleaning claim",
            },
            {
                "plot": "家人催着出门，主角必须在有限时间内把厨房恢复清爽，冲突落在工具是否顺手。",
                "visual": f"切到{scene_b}，台面污渍、收纳凌乱和使用动作形成前后节奏。",
                "shot": "before-after practical comparison, handheld home realism",
                "character_action": "人物拿起产品快速处理台面、水槽边和角落收纳。",
                "product_exposure": f"产品包装正面与清洁动作同框，字幕呈现：{product_points}。",
                "subtitle": "工具顺手，家务节奏才不拖",
                "voiceover": f"核心看{product_points}，适合家庭高频清洁和收纳场景。",
                "negative_prompt": "absolute residue-free claim, fake comparison, unrealistic sparkle",
            },
            {
                "plot": "产品进入完整使用流程，污渍处理、收纳和清爽台面被分步骤呈现。",
                "visual": f"{proof_a}、{proof_b}、收纳效果和家庭高频场景串联，色调清爽明亮。",
                "shot": "macro cleaning detail, smooth side pan, satisfying reset montage",
                "character_action": "人物完成一次清洁或收纳动作，然后把产品放回固定位置。",
                "product_exposure": "使用前、动作中、收纳后都让产品与场景同框。",
                "subtitle": "把高频家务拆小，日常就更省心",
                "voiceover": "不用夸大效果，把每一步顺不顺手拍清楚就够有说服力。",
                "negative_prompt": "fake proof, medical grade claim, overexposed white kitchen",
            },
            {
                "plot": "厨房恢复清爽，家人进来看到变化，结尾引导按使用场景理性选择。",
                "visual": "干净台面、整齐水槽和收纳区同框，人物把产品放在顺手位置。",
                "shot": "clean home hero shot, gentle pull-back",
                "character_action": "人物擦干手，回头看整洁空间，轻松点头。",
                "product_exposure": f"结尾定格{product.product_name}和清爽家庭场景。",
                "subtitle": "高频家务，选一个更顺手的帮手",
                "voiceover": f"如果你也想让家务流程轻一点，可以重点看看{product.product_name}。",
                "negative_prompt": "hard sell, fake discount, absolute promise, unreadable label",
            },
        ]

    return [
        {
            "plot": f"{persona_relation}遇到真实使用痛点，第一秒建立共鸣。",
            "visual": f"{scene_a}中人物面对产品相关痛点，情绪真实，画面快速进入主题。",
            "shot": "fast push-in, realistic commercial style",
            "character_action": "人物停下手中动作，看向问题场景。",
            "product_exposure": f"{product.product_name}在画面边缘首次露出。",
            "subtitle": opening_hook,
            "voiceover": f"{product.product_name}适合解决这种高频使用场景。",
            "negative_prompt": "exaggerated claim, fake comparison, low quality, unreadable text",
        },
        {
            "plot": "痛点被放大，人物开始寻找更顺手的解决方案。",
            "visual": f"切到{scene_b}，用真实动作展示使用前的不便。",
            "shot": "handheld realism, medium close-up",
            "character_action": "人物尝试旧方法，随后注意到产品。",
            "product_exposure": f"产品正面包装清晰露出，卖点字幕出现：{product_points}。",
            "subtitle": "换个顺手的选择，体验会不一样",
            "voiceover": f"核心看这几点：{product_points}。",
            "negative_prompt": "hard sell, unrealistic transformation, medical claim",
        },
        {
            "plot": "产品进入场景，卖点通过动作和细节自然展示。",
            "visual": f"用{proof_a}和{proof_b}展示产品细节，动作慢且清楚。",
            "shot": "macro product detail, smooth pan",
            "character_action": "人物完成一次完整使用动作。",
            "product_exposure": "使用前、使用中、使用后都让产品自然同框。",
            "subtitle": "细节看得见，日常更好上手",
            "voiceover": "不靠夸张表达，用真实细节说明为什么值得看。",
            "negative_prompt": "absolute promise, fake proof, distorted package",
        },
        {
            "plot": "人物情绪转为轻松，结尾给出理性成交引导。",
            "visual": "产品定格在干净背景中，人物完成使用后自然点头。",
            "shot": "clean hero shot, slow pull-back",
            "character_action": "人物把产品放回画面中心。",
            "product_exposure": "结尾定格产品完整包装和关键字幕。",
            "subtitle": "按需求选择，理性下单",
            "voiceover": f"在{product.platform}看到它时，记得结合自己的使用场景来选。",
            "negative_prompt": "fake discount, exaggerated claim, low quality",
        },
    ]
