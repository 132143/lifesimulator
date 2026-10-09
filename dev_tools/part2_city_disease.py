

# ==============================================================================
# 5. 效果字典：统一的属性变更描述与应用
# ==============================================================================
# 效果字典键名约定：
#   health / happy / money / temp / temp_now / temp_drift : 立即数值变更
#   disease  : 施加疾病，值为 (疾病id, 持续天数修正)
#   cure     : 立即治愈疾病，值为疾病id或 True
#   health_boost / happy_boost : 有上限的回复（不会超过 100）
#   func     : 特殊回调，签名 func(player) -> 追加描述(list[str])
#   title    : 变更条目的显示名（覆盖默认的提示文字）
# ==============================================================================


def merge_effect(target, extra):
    """把 extra 合并进 target 效果字典（数值累加，其余覆盖）。"""
    if not extra:
        return target
    for key, value in extra.items():
        if key == "func":
            target[key] = value
        elif isinstance(value, (int, float)) and isinstance(target.get(key), (int, float)):
            target[key] = target[key] + value
        else:
            target[key] = value
    return target


def describe_effects(effects, player=None):
    """
    把效果字典翻译成中文描述列表（用于选择弹窗的提示文字）。
    """
    if not effects:
        return []
    parts = []
    names = {
        "health": "健康", "happy": "幸福", "money": "金钱", "temp": "体温",
        "temp_now": "体温", "temp_drift": "体温趋势", "health_boost": "健康",
        "happy_boost": "幸福",
    }
    order = ["health", "happy", "money", "temp", "temp_now", "temp_drift",
             "health_boost", "happy_boost"]
    for key in order:
        if key not in effects:
            continue
        value = effects[key]
        if key in ("health", "happy", "money"):
            parts.append("%s %s" % (names[key], fmt_signed(value, 0 if key != "money" else 0)))
        elif key in ("temp", "temp_now"):
            parts.append("%s %s" % (names[key], fmt_signed(value, 1)))
        elif key == "health_boost":
            parts.append("健康 回复最多 %+d" % value)
        elif key == "happy_boost":
            parts.append("幸福 回复最多 %+d" % value)
        elif key == "temp_drift":
            parts.append("体温趋势 %s" % fmt_signed(value, 1))
    if "disease" in effects:
        did = effects["disease"]
        if isinstance(did, (tuple, list)):
            did = did[0]
        dis = DISEASES.get(did)
        parts.append("可能患病：%s" % (dis["name"] if dis else did))
    if effects.get("cure"):
        parts.append("立刻治愈当前疾病")
    return parts


# ==============================================================================
# 6. 城市气候系统
# ==============================================================================
# 每个城市包含：
#   tag            : 气候类型
#   desc           : 简介
#   seasons        : 四季基准气温（℃）
#   variance       : 每日气温波动幅度
#   temp_swing     : 环境事件造成的体温波动倍率（越高越"极端"）
#   cost_factor    : 消费水平系数（影响每月固定支出）
#   env_weights    : 四季环境气候事件权重表
#   disease_weights: 疾病易感权重（按季节合并计算的额外倾向）
# ==============================================================================

SEASON_NAMES = {1: "春季", 2: "夏季", 3: "秋季", 4: "冬季"}

CITIES = {
    "harbin": {
        "name": "哈尔滨",
        "tag": "寒冷",
        "desc": "北国冰城：冬季漫长严寒，寒潮与冻伤高发；室内供暖好，夏季凉爽宜人。",
        "seasons": {1: 4.0, 2: 22.0, 3: 5.0, 4: -18.0},
        "variance": 6.0,
        "temp_swing": 1.6,
        "cost_factor": 0.86,
        "env_weights": {
            1: {"cold_wave": 16, "blizzard": 12, "rain": 8, "haze": 5, "heat_wave": 0, "heatstroke": 0},
            2: {"heat_wave": 5, "heatstroke": 3, "rain": 12, "haze": 4, "cold_wave": 0, "blizzard": 0},
            3: {"cold_wave": 10, "rain": 10, "haze": 10, "blizzard": 2, "heat_wave": 0, "heatstroke": 0},
            4: {"cold_wave": 26, "blizzard": 18, "haze": 12, "rain": 2, "heat_wave": 0, "heatstroke": 0},
        },
        "disease_weights": {"cold": 20, "flu": 16, "tonsillitis": 12, "bronchitis": 10, "pneumonia": 10, "asthma": 6, "rhinitis": 4, "gastro": 8, "food_poisoning": 6, "gastritis": 6, "hypertension": 8, "heart_disease": 6, "diabetes": 6, "gout": 5, "migraine": 6, "insomnia": 5, "frostbite": 12, "burns": 4, "fracture": 5, "sprain": 6, "dental": 5, "dermatitis": 4, "depression": 4, "anxiety": 4, "heatstroke": 1},
    },
    "beijing": {
        "name": "北京",
        "tag": "温带",
        "desc": "温带季风：四季分明，春季沙尘、夏季闷热、冬季干冷，气候事件较为均衡。",
        "seasons": {1: 12.0, 2: 27.0, 3: 13.0, 4: -3.0},
        "variance": 5.0,
        "temp_swing": 1.15,
        "cost_factor": 1.10,
        "env_weights": {
            1: {"sandstorm": 14, "haze": 12, "rain": 8, "cold_wave": 5, "heat_wave": 0, "heatstroke": 0},
            2: {"heat_wave": 14, "heatstroke": 8, "rain": 14, "haze": 6, "cold_wave": 0, "blizzard": 0},
            3: {"haze": 14, "rain": 10, "cold_wave": 6, "sandstorm": 4, "heat_wave": 0, "heatstroke": 0},
            4: {"cold_wave": 16, "haze": 16, "blizzard": 8, "sandstorm": 4, "rain": 2, "heat_wave": 0},
        },
        "disease_weights": {"cold": 18, "flu": 16, "tonsillitis": 10, "bronchitis": 12, "pneumonia": 10, "asthma": 8, "rhinitis": 8, "gastro": 12, "food_poisoning": 8, "gastritis": 8, "hypertension": 10, "heart_disease": 8, "diabetes": 8, "gout": 6, "migraine": 8, "insomnia": 7, "frostbite": 6, "burns": 4, "fracture": 5, "sprain": 6, "dental": 6, "dermatitis": 5, "depression": 5, "anxiety": 5, "heatstroke": 3},
    },
    "shanghai": {
        "name": "上海",
        "tag": "亚热带",
        "desc": "亚热带季风：梅雨连绵、夏季湿热难耐，体质偏弱者易患肠胃疾病。",
        "seasons": {1: 15.0, 2: 30.0, 3: 20.0, 4: 6.0},
        "variance": 4.0,
        "temp_swing": 1.0,
        "cost_factor": 1.22,
        "env_weights": {
            1: {"rain": 16, "cold_wave": 4, "haze": 8, "heat_wave": 0, "heatstroke": 0},
            2: {"rain": 18, "heat_wave": 12, "heatstroke": 6, "haze": 4, "cold_wave": 0},
            3: {"rain": 10, "haze": 8, "cold_wave": 4, "heat_wave": 0, "heatstroke": 0},
            4: {"cold_wave": 10, "rain": 12, "haze": 10, "heat_wave": 0, "heatstroke": 0},
        },
        "disease_weights": {"cold": 16, "flu": 14, "tonsillitis": 10, "bronchitis": 10, "pneumonia": 8, "asthma": 8, "rhinitis": 10, "gastro": 18, "food_poisoning": 12, "gastritis": 10, "hypertension": 9, "heart_disease": 6, "diabetes": 7, "gout": 6, "migraine": 8, "insomnia": 8, "frostbite": 2, "burns": 4, "fracture": 5, "sprain": 7, "dental": 6, "dermatitis": 7, "depression": 5, "anxiety": 5, "heatstroke": 8},
    },
    "guangzhou": {
        "name": "广州",
        "tag": "炎热",
        "desc": "南国花城：长夏无冬，高温高湿，中暑与湿热型肠胃病高发。",
        "seasons": {1: 22.0, 2: 33.0, 3: 27.0, 4: 16.0},
        "variance": 3.0,
        "temp_swing": 1.25,
        "cost_factor": 1.05,
        "env_weights": {
            1: {"rain": 14, "heat_wave": 6, "heatstroke": 6, "haze": 4},
            2: {"heat_wave": 20, "heatstroke": 16, "rain": 16, "haze": 4},
            3: {"heat_wave": 8, "heatstroke": 8, "rain": 10, "haze": 8},
            4: {"heat_wave": 6, "heatstroke": 6, "cold_wave": 3, "rain": 6, "haze": 6},
        },
        "disease_weights": {"cold": 12, "flu": 12, "tonsillitis": 10, "bronchitis": 8, "pneumonia": 6, "asthma": 7, "rhinitis": 10, "gastro": 16, "food_poisoning": 12, "gastritis": 9, "hypertension": 8, "heart_disease": 5, "diabetes": 7, "gout": 7, "migraine": 7, "insomnia": 7, "frostbite": 1, "burns": 5, "fracture": 4, "sprain": 7, "dental": 6, "dermatitis": 8, "depression": 4, "anxiety": 4, "heatstroke": 16},
    },
}

CITY_ORDER = ["harbin", "beijing", "shanghai", "guangzhou"]

#: 春秋季环境事件的补充权重（让季节间差异更自然）
ENV_BASE_WEIGHTS = {
    1: {"rain": 6, "haze": 4, "cold_wave": 2, "sandstorm": 4},
    2: {"heat_wave": 4, "rain": 6, "heatstroke": 2},
    3: {"rain": 5, "haze": 5, "cold_wave": 4},
    4: {"cold_wave": 8, "blizzard": 4, "haze": 4},
}


def get_city(city_id):
    """取城市数据，未知城市退回北京（保证不崩溃）。"""
    return CITIES.get(city_id) or CITIES["beijing"]


def season_of_month(month):
    """月份 -> 季节编号（1春 2夏 3秋 4冬）。"""
    if month in (3, 4, 5):
        return 1
    if month in (6, 7, 8):
        return 2
    if month in (9, 10, 11):
        return 3
    return 4


def season_name(month):
    return SEASON_NAMES[season_of_month(month)]


def seasonal_avg_temp(city_id, month):
    """该城市该月的基准气温。"""
    city = get_city(city_id)
    season = season_of_month(month)
    base = city["seasons"].get(season, 20.0)
    # 同一季节内做小幅偏移，让同季不同月也有区别
    offset_map = {
        1: {3: -2.0, 4: 0.0, 5: 2.0},
        2: {6: -1.0, 7: 1.5, 8: 0.5},
        3: {9: 2.0, 10: 0.0, 11: -2.0},
        4: {12: -2.0, 1: 0.0, 2: 1.5},
    }
    return base + offset_map.get(season, {}).get(month, 0.0)


def roll_ambient_temp(dice, city_id, month):
    """
    投掷当日气温：基准气温 ± d6 波动（寒冷城市波动更大）。
    返回 (气温, DiceResult)
    """
    city = get_city(city_id)
    base = seasonal_avg_temp(city_id, month)
    res = dice.roll(6, 2, 0, "气温波动")
    swing = (res.value - 7) / 1.0            # 2d6 期望 7，范围 -5 ~ +5
    swing *= (city["variance"] / 5.0)
    return round(base + swing, 1), res


def env_weights_for(city_id, month):
    """合并城市权重与季节基础权重，返回 (事件id -> 权重) 字典。"""
    city = get_city(city_id)
    season = season_of_month(month)
    weights = {}
    for key, value in (city["env_weights"].get(season) or {}).items():
        if value > 0:
            weights[key] = weights.get(key, 0) + value
    for key, value in ENV_BASE_WEIGHTS.get(season, {}).items():
        weights[key] = weights.get(key, 0) + value
    return weights


def temperature_adjust(dice, player):
    """
    每日环境对体温的自发影响：
      * 气温过高/过低会把体温推离正常区间（有上限，不会一天之内暴走）
      * 同时身体会向 36.5℃ 回归，越偏离回归越强
      * 因此体温异常是"缓慢恶化 + 可自救"的过程，而不是必死陷阱
    返回 (体温变化量, 描述文本, DiceResult)
    """
    city = get_city(player.city)
    ambient = player.ambient_temp
    swing_factor = min(1.5, float(city["temp_swing"]))
    desc = []
    push = 0.0
    neutral = 36.5

    if ambient <= 0:
        push -= min(0.30, (0 - ambient) * 0.012) * swing_factor
        desc.append("严寒环境推低体温")
    elif ambient >= 33:
        push += min(0.30, (ambient - 33) * 0.012) * swing_factor
        desc.append("酷热环境推高体温")

    res = dice.d10("环境体温影响")
    push += (res.value - 5.5) / 10.0 * 0.25        # 轻微随机波动

    # 身体恒温调节：越偏离正常值，回归力越强（最低 0.12，避免"越冻越冷"）
    deviation = neutral - player.temp
    regulate = max(-0.30, min(0.30, deviation * 0.22))
    if abs(deviation) > 0.6:
        regulate += 0.12 if deviation > 0 else -0.12

    delta = push + regulate
    if regulate > 0 and player.temp < 36.2:
        desc.append("身体努力回暖")
    elif regulate < 0 and player.temp > 36.8:
        desc.append("身体努力降温")

    return round(delta, 2), "，".join(desc), res


# ==============================================================================
# 7. 疾病系统
# ==============================================================================
# 字段说明：
#   name / kind / desc : 名称、类型、描述
#   days               : (最短, 最长) 严重程度（1~5，用于判定"是否更严重"）
#   hp_per_day         : 每日健康扣除（已按"现实病程 + 游戏可玩性"标定）
#   happy_per_day      : 每日幸福扣除
#   cure_cost          : 彻底治愈费用
#   self_heal          : 每日自愈概率（0 表示不会自愈，只能花钱）
#   temp_mod           : 每日体温累积影响（发烧为正、冻伤为负）
#   needs_cure         : True 表示必须花钱治疗，否则一直持续（慢性病）
#   fatal              : True 表示危重疾病，健康过低时可能直接致死
#   severity           : 1~5 严重度（替代旧的 DISEASE_SEVERITY 表）
#   scope              : 适用人群（all/child/adult/elder）——影响抽病权重
#   contagion          : 传染性（1~3），影响季节/人群聚集时的权重
#   tags               : 附加标签（fever 发热 / chill 失温 / chronic 慢性 / injury 外伤）
# ==============================================================================

DISEASES = {
    # ---------------- 呼吸道 ----------------
    "cold": {
        "id": "cold", "name": "普通感冒", "kind": "轻症",
        "desc": "鼻塞、流涕、打喷嚏，通常一周左右自愈。",
        "days": (2, 6), "hp_per_day": 1.6, "happy_per_day": 2,
        "cure_cost": 80.0, "self_heal": 0.55, "temp_mod": 0.10,
        "severity": 1, "scope": "all", "contagion": 2, "tags": ["fever"],
    },
    "flu": {
        "id": "flu", "name": "流行性感冒", "kind": "中症",
        "desc": "高热、全身酸痛，比普通感冒重得多，容易并发肺炎。",
        "days": (4, 10), "hp_per_day": 2.6, "happy_per_day": 3,
        "cure_cost": 260.0, "self_heal": 0.35, "temp_mod": 0.22,
        "severity": 2, "scope": "all", "contagion": 3, "tags": ["fever"],
    },
    "tonsillitis": {
        "id": "tonsillitis", "name": "扁桃体炎", "kind": "中症",
        "desc": "咽喉肿痛、吞咽困难，儿童和青少年尤其常见。",
        "days": (3, 8), "hp_per_day": 2.2, "happy_per_day": 2,
        "cure_cost": 220.0, "self_heal": 0.35, "temp_mod": 0.18,
        "severity": 2, "scope": "child", "contagion": 1, "tags": ["fever"],
    },
    "bronchitis": {
        "id": "bronchitis", "name": "支气管炎", "kind": "中症",
        "desc": "咳嗽不止、痰多胸闷，抽烟或空气差的人更容易得。",
        "days": (5, 12), "hp_per_day": 2.8, "happy_per_day": 3,
        "cure_cost": 420.0, "self_heal": 0.25, "temp_mod": 0.15,
        "severity": 3, "scope": "all", "contagion": 1, "tags": ["fever"],
    },
    "pneumonia": {
        "id": "pneumonia", "name": "肺炎", "kind": "重症",
        "desc": "高烧不退、呼吸带杂音，必须住院治疗，否则非常危险。",
        "days": (7, 18), "hp_per_day": 4.2, "happy_per_day": 5,
        "cure_cost": 2600.0, "self_heal": 0.05, "temp_mod": 0.30,
        "severity": 5, "scope": "all", "contagion": 1, "tags": ["fever"], "fatal": True,
    },
    "asthma": {
        "id": "asthma", "name": "哮喘发作", "kind": "顽疾",
        "desc": "气道痉挛、喘不上气，换季或雾霾天特别容易发作。",
        "days": (2, 6), "hp_per_day": 3.0, "happy_per_day": 4,
        "cure_cost": 480.0, "self_heal": 0.45, "temp_mod": 0.05,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    "rhinitis": {
        "id": "rhinitis", "name": "过敏性鼻炎", "kind": "轻症",
        "desc": "喷嚏不断、鼻子发痒，春天和雾霾天最难受。",
        "days": (4, 12), "hp_per_day": 0.8, "happy_per_day": 2,
        "cure_cost": 180.0, "self_heal": 0.45, "temp_mod": 0.0,
        "severity": 1, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    # ---------------- 消化道 ----------------
    "gastro": {
        "id": "gastro", "name": "急性肠胃炎", "kind": "中症",
        "desc": "上吐下泻、浑身发软，多因吃坏东西引起。",
        "days": (3, 8), "hp_per_day": 2.4, "happy_per_day": 3,
        "cure_cost": 320.0, "self_heal": 0.30, "temp_mod": 0.08,
        "severity": 2, "scope": "all", "contagion": 2, "tags": [],
    },
    "food_poisoning": {
        "id": "food_poisoning", "name": "食物中毒", "kind": "中症",
        "desc": "剧烈腹痛、反复呕吐，需要尽快补液。",
        "days": (2, 5), "hp_per_day": 3.2, "happy_per_day": 4,
        "cure_cost": 400.0, "self_heal": 0.35, "temp_mod": 0.12,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["fever"],
    },
    "gastritis": {
        "id": "gastritis", "name": "慢性胃炎", "kind": "顽疾",
        "desc": "胃部隐痛、反酸胀气，饮食不规律的人容易拖成老毛病。",
        "days": (15, 40), "hp_per_day": 0.9, "happy_per_day": 2,
        "cure_cost": 900.0, "self_heal": 0.10, "temp_mod": 0.0,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "appendicitis": {
        "id": "appendicitis", "name": "阑尾炎", "kind": "急症",
        "desc": "右下腹剧痛、按下去更疼，必须马上手术。",
        "days": (5, 12), "hp_per_day": 4.5, "happy_per_day": 5,
        "cure_cost": 3800.0, "self_heal": 0.02, "temp_mod": 0.25,
        "severity": 5, "scope": "all", "contagion": 0, "tags": ["fever"], "fatal": True,
    },
    "hemorrhoids": {
        "id": "hemorrhoids", "name": "痔疮", "kind": "轻症",
        "desc": "久坐、便秘之后的老毛病，坐立不安。",
        "days": (5, 15), "hp_per_day": 0.7, "happy_per_day": 2,
        "cure_cost": 600.0, "self_heal": 0.35, "temp_mod": 0.0,
        "severity": 2, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    # ---------------- 心血管 / 代谢 ----------------
    "hypertension": {
        "id": "hypertension", "name": "高血压", "kind": "慢性病",
        "desc": "头晕、后颈发紧，需要长期吃药控制，否则伤及心脑。",
        "days": (25, 60), "hp_per_day": 1.1, "happy_per_day": 2,
        "cure_cost": 1600.0, "self_heal": 0.0, "temp_mod": 0.02,
        "severity": 4, "scope": "elder", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True,
    },
    "heart_disease": {
        "id": "heart_disease", "name": "冠心病", "kind": "重症",
        "desc": "胸闷、心悸，情绪激动或劳累时可能急性发作。",
        "days": (20, 50), "hp_per_day": 1.8, "happy_per_day": 3,
        "cure_cost": 12000.0, "self_heal": 0.0, "temp_mod": 0.0,
        "severity": 5, "scope": "elder", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True, "fatal": True,
    },
    "diabetes": {
        "id": "diabetes", "name": "糖尿病", "kind": "慢性病",
        "desc": "口渴、多尿、体重下降，需要长期控糖与忌口。",
        "days": (30, 70), "hp_per_day": 1.0, "happy_per_day": 3,
        "cure_cost": 2400.0, "self_heal": 0.0, "temp_mod": 0.0,
        "severity": 4, "scope": "adult", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True,
    },
    "hyperlipidemia": {
        "id": "hyperlipidemia", "name": "高血脂", "kind": "慢性病",
        "desc": "体检报告上的常客，控制饮食就能缓解。",
        "days": (20, 50), "hp_per_day": 0.6, "happy_per_day": 1,
        "cure_cost": 1200.0, "self_heal": 0.05, "temp_mod": 0.0,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "gout": {
        "id": "gout", "name": "痛风", "kind": "顽疾",
        "desc": "关节红肿剧痛，半夜能把人疼醒，海鲜啤酒是元凶。",
        "days": (4, 14), "hp_per_day": 2.4, "happy_per_day": 4,
        "cure_cost": 800.0, "self_heal": 0.20, "temp_mod": 0.05,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "anemia": {
        "id": "anemia", "name": "贫血", "kind": "慢性病",
        "desc": "脸色苍白、容易头晕乏力，女性与偏食者更常见。",
        "days": (10, 30), "hp_per_day": 0.9, "happy_per_day": 2,
        "cure_cost": 700.0, "self_heal": 0.25, "temp_mod": 0.0,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    # ---------------- 感染 / 其他内科 ----------------
    "urinary_infection": {
        "id": "urinary_infection", "name": "尿路感染", "kind": "中症",
        "desc": "尿急尿痛、小腹坠胀，需要多喝水并尽快用药。",
        "days": (3, 9), "hp_per_day": 2.0, "happy_per_day": 4,
        "cure_cost": 300.0, "self_heal": 0.25, "temp_mod": 0.15,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["fever"],
    },
    "kidney_stone": {
        "id": "kidney_stone", "name": "肾结石", "kind": "急症",
        "desc": "腰部绞痛，疼起来直不起身，严重时需要碎石。",
        "days": (5, 15), "hp_per_day": 3.6, "happy_per_day": 5,
        "cure_cost": 4200.0, "self_heal": 0.10, "temp_mod": 0.05,
        "severity": 4, "scope": "adult", "contagion": 0, "tags": [],
    },
    "thyroid": {
        "id": "thyroid", "name": "甲状腺疾病", "kind": "慢性病",
        "desc": "心慌、怕冷或怕热、体重异常，需要长期服药。",
        "days": (25, 60), "hp_per_day": 0.8, "happy_per_day": 2,
        "cure_cost": 1800.0, "self_heal": 0.0, "temp_mod": 0.03,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True,
    },
    "liver_disease": {
        "id": "liver_disease", "name": "脂肪肝 / 肝功能异常", "kind": "慢性病",
        "desc": "体检提示肝酶升高，多半是熬夜和饮食造成的。",
        "days": (20, 50), "hp_per_day": 0.9, "happy_per_day": 2,
        "cure_cost": 2000.0, "self_heal": 0.10, "temp_mod": 0.0,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "migraine": {
        "id": "migraine", "name": "偏头痛", "kind": "顽疾",
        "desc": "一侧头痛、怕光怕吵，压力大时发作频繁。",
        "days": (2, 7), "hp_per_day": 1.4, "happy_per_day": 4,
        "cure_cost": 260.0, "self_heal": 0.45, "temp_mod": 0.0,
        "severity": 2, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "insomnia": {
        "id": "insomnia", "name": "失眠症", "kind": "轻症",
        "desc": "躺下两小时还睡不着，白天精神恍惚。",
        "days": (5, 20), "hp_per_day": 0.8, "happy_per_day": 3,
        "cure_cost": 400.0, "self_heal": 0.40, "temp_mod": 0.0,
        "severity": 2, "scope": "adult", "contagion": 0, "tags": [],
    },
    # ---------------- 外科 / 外伤 ----------------
    "fracture": {
        "id": "fracture", "name": "骨折", "kind": "外伤",
        "desc": "骨头断了，需要打石膏静养很长一段时间。",
        "days": (20, 45), "hp_per_day": 2.0, "happy_per_day": 3,
        "cure_cost": 3000.0, "self_heal": 0.05, "temp_mod": 0.05,
        "severity": 4, "scope": "all", "contagion": 0, "tags": ["injury"],
    },
    "sprain": {
        "id": "sprain", "name": "扭伤", "kind": "外伤",
        "desc": "脚踝或手腕扭伤，肿得像个馒头。",
        "days": (5, 14), "hp_per_day": 1.2, "happy_per_day": 2,
        "cure_cost": 300.0, "self_heal": 0.40, "temp_mod": 0.0,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["injury"],
    },
    "burns": {
        "id": "burns", "name": "烫伤 / 烧伤", "kind": "外伤",
        "desc": "皮肤红肿起泡，处理不当会留疤甚至感染。",
        "days": (4, 12), "hp_per_day": 2.6, "happy_per_day": 3,
        "cure_cost": 1200.0, "self_heal": 0.20, "temp_mod": 0.10,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["injury"],
    },
    "frostbite": {
        "id": "frostbite", "name": "冻伤", "kind": "外伤",
        "desc": "手脚冻得失去知觉，严重时皮肤发黑，必须尽快处理。",
        "days": (3, 9), "hp_per_day": 2.2, "happy_per_day": 3,
        "cure_cost": 260.0, "self_heal": 0.25, "temp_mod": -0.30,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["chill", "injury"],
    },
    "heatstroke": {
        "id": "heatstroke", "name": "中暑", "kind": "急症",
        "desc": "头晕恶心、体温飙升，需要马上降温补水。",
        "days": (2, 6), "hp_per_day": 3.0, "happy_per_day": 4,
        "cure_cost": 300.0, "self_heal": 0.35, "temp_mod": 0.35,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["fever"],
    },
    # ---------------- 皮肤 / 口腔 / 眼耳 ----------------
    "dermatitis": {
        "id": "dermatitis", "name": "皮炎 / 湿疹", "kind": "轻症",
        "desc": "皮肤发红发痒，越挠越难受。",
        "days": (5, 20), "hp_per_day": 0.6, "happy_per_day": 3,
        "cure_cost": 350.0, "self_heal": 0.30, "temp_mod": 0.0,
        "severity": 1, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    "dental": {
        "id": "dental", "name": "牙痛 / 龋齿", "kind": "轻症",
        "desc": "牙疼不是病，疼起来真要命，补牙还要花不少钱。",
        "days": (3, 10), "hp_per_day": 1.2, "happy_per_day": 4,
        "cure_cost": 900.0, "self_heal": 0.25, "temp_mod": 0.0,
        "severity": 2, "scope": "all", "contagion": 0, "tags": [],
    },
    "conjunctivitis": {
        "id": "conjunctivitis", "name": "结膜炎", "kind": "轻症",
        "desc": "眼睛红痒、分泌物增多，传染性很强。",
        "days": (3, 8), "hp_per_day": 0.9, "happy_per_day": 3,
        "cure_cost": 200.0, "self_heal": 0.45, "temp_mod": 0.05,
        "severity": 1, "scope": "all", "contagion": 2, "tags": [],
    },
    "otitis": {
        "id": "otitis", "name": "中耳炎", "kind": "中症",
        "desc": "耳朵闷痛、听力下降，小孩子尤其容易得。",
        "days": (4, 10), "hp_per_day": 1.8, "happy_per_day": 3,
        "cure_cost": 400.0, "self_heal": 0.35, "temp_mod": 0.15,
        "severity": 2, "scope": "child", "contagion": 1, "tags": ["fever"],
    },
    "hemorrhagic_fever": {
        "id": "hemorrhagic_fever", "name": "重症感染", "kind": "危重症",
        "desc": "高热、寒战、意识模糊，必须立刻住院抢救。",
        "days": (8, 20), "hp_per_day": 5.0, "happy_per_day": 6,
        "cure_cost": 20000.0, "self_heal": 0.02, "temp_mod": 0.45,
        "severity": 5, "scope": "all", "contagion": 2, "tags": ["fever"],
        "fatal": True,
    },
    # ---------------- 心理健康（现实中最常见的"病"之一）----------------
    "depression": {
        "id": "depression", "name": "抑郁症", "kind": "心理疾病",
        "desc": "提不起劲、对什么都失去兴趣，需要长期疏导与治疗。",
        "days": (30, 90), "hp_per_day": 1.0, "happy_per_day": 5,
        "cure_cost": 3000.0, "self_heal": 0.02, "temp_mod": 0.0,
        "severity": 4, "scope": "all", "contagion": 0, "tags": ["mental"],
        "needs_cure": True,
    },
    "anxiety": {
        "id": "anxiety", "name": "焦虑症", "kind": "心理疾病",
        "desc": "心慌、手抖、总是担心最坏的结果。",
        "days": (15, 45), "hp_per_day": 0.8, "happy_per_day": 4,
        "cure_cost": 1500.0, "self_heal": 0.10, "temp_mod": 0.0,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["mental"],
    },
}

#: 疾病严重度（由 severity 字段生成，保留旧接口名）
DISEASE_SEVERITY = {k: v.get("severity", 2) for k, v in DISEASES.items()}

#: 常见疾病总览（供帮助面板展示）
COMMON_DISEASE_KEYS = [
    "cold", "flu", "tonsillitis", "bronchitis", "pneumonia", "asthma", "rhinitis",
    "gastro", "food_poisoning", "gastritis", "appendicitis", "hemorrhoids",
    "hypertension", "heart_disease", "diabetes", "hyperlipidemia", "gout", "anemia",
    "urinary_infection", "kidney_stone", "thyroid", "liver_disease",
    "migraine", "insomnia", "fracture", "sprain", "burns", "frostbite", "heatstroke",
    "dermatitis", "dental", "conjunctivitis", "otitis", "hemorrhagic_fever",
    "depression", "anxiety",
]

#: 疾病分类（用于界面分组展示）
DISEASE_GROUPS = [
    ("呼吸道", ["cold", "flu", "tonsillitis", "bronchitis", "pneumonia", "asthma", "rhinitis"]),
    ("消化道", ["gastro", "food_poisoning", "gastritis", "appendicitis", "hemorrhoids"]),
    ("心血管/代谢", ["hypertension", "heart_disease", "diabetes", "hyperlipidemia",
                     "gout", "anemia", "thyroid", "liver_disease"]),
    ("感染与其他内科", ["urinary_infection", "kidney_stone", "migraine", "insomnia",
                        "hemorrhagic_fever"]),
    ("外伤/环境", ["fracture", "sprain", "burns", "frostbite", "heatstroke"]),
    ("皮肤/口腔/眼耳", ["dermatitis", "dental", "conjunctivitis", "otitis"]),
    ("心理", ["depression", "anxiety"]),
]

#: 患病概率的年龄系数（U 型曲线：婴幼儿偏高 -> 青少年最低 -> 老年快速升高）
#: 已按"各年龄段事件暴露量不同"做过实验修正，使实际患病频率呈标准 U 型
SICKNESS_AGE_POINTS = [
    (0, 1.20), (1, 1.15), (2, 1.05), (4, 0.95), (6, 0.88),
    (10, 0.80), (14, 0.72), (18, 0.62), (25, 0.66), (35, 0.85),
    (45, 1.15), (55, 1.70), (65, 2.45), (75, 3.40), (85, 4.60), (100, 5.80),
]

#: 患病基础概率（"患病机会"出现后真正病倒的概率）
SICKNESS_BASE_RATE = 0.055

#: 目标"每年生病次数"曲线（普通人、体质 50 分）：用于反推每日患病概率
#: 与真实人生接近：婴幼儿 3~4 次/年，青少年 1 次/年，老年人 4~6 次/年
ILLNESS_PER_YEAR_POINTS = [
    (0, 3.40), (1, 3.60), (2, 3.20), (4, 2.80), (6, 2.50),
    (10, 1.80), (14, 1.20), (18, 1.00), (25, 0.90), (35, 1.00),
    (45, 1.40), (55, 2.00), (65, 2.80), (75, 4.00), (85, 5.40), (100, 6.50),
]

#: 单次"患病机会"对应的掷骰精度（万分之一），使间隔分布更细腻
ILLNESS_ROLL_D10000 = 10000


def _interp(points, value):
    """在 (x, y) 点列上做线性插值。"""
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= value <= x1:
            ratio = (value - x0) / float(x1 - x0) if x1 != x0 else 0.0
            return y0 + (y1 - y0) * ratio
    return points[-1][1]


def illness_per_year(age, constitution=CONSTITUTION_MEAN):
    """
    该年龄 + 该体质下，平均每年生病次数（真实感的核心参数）。
    体质通过易感倍率调节：体质 80 分约 0.45 倍，体质 20 分约 1.8 倍。
    """
    base = _interp(ILLNESS_PER_YEAR_POINTS, age)
    return base * constitution_susceptibility(constitution)


def sickness_age_factor(age):
    """按年龄对患病概率做插值，形成 U 型曲线（保留给旧接口使用）。"""
    return _interp(SICKNESS_AGE_POINTS, age)


def sickness_probability(player):
    """
    计算"今天是否会生病"的**每日概率**（0~0.05），综合：
        * 基础发病率（随年龄呈 U 型：幼年高 -> 青少年低 -> 老年高）
        * 体质（开局固定参数，正态分布；越弱越容易病）
        * 当前健康 / 幸福 / 体温状态
        * 城市易感倾向（不同城市疾病权重均值不同）
    例：3 岁幼儿、体质 50 -> 约 3.2 次/年 -> 每日约 0.88%
        25 岁成人、体质 50 -> 约 0.90 次/年 -> 每日约 0.25%
        75 岁老人、体质 50 -> 约 4.0 次/年 -> 每日约 1.10%
    """
    age = getattr(player, "age", 0)
    constitution = getattr(player, "constitution", CONSTITUTION_MEAN)
    per_year = illness_per_year(age, constitution)
    daily = per_year / float(DAYS_PER_YEAR)

    # 状态修正
    kind = player_status_factor(player)
    daily *= kind
    # 城市整体易感倾向
    city = get_city(getattr(player, "city", "beijing"))
    weights = [w for w in city["disease_weights"].values()]
    avg = (sum(weights) / float(len(weights))) if weights else 10.0
    daily *= max(0.7, min(1.35, avg / 10.0))
    return max(0.0, min(0.05, daily))


def player_status_factor(player):
    """健康 / 幸福 / 体温对患病概率的修正系数。"""
    factor = 1.0
    try:
        health = float(player.health)
        happy = float(player.happy)
        temp = float(player.temp)
    except Exception:
        return 1.0
    if health < 35:
        factor *= 1.45
    elif health < 60:
        factor *= 1.18
    if happy < LOW_HAPPY_THRESHOLD:
        factor *= 1.22
    if temp >= 38.0 or temp <= 35.2:
        factor *= 1.35
    elif temp > TEMP_NORMAL_HIGH or temp < TEMP_NORMAL_LOW:
        factor *= 1.12
    sick = len(getattr(player, "diseases", []) or [])
    if sick >= 2:
        factor *= 1.25
    return factor


def illness_gap_ok(player, min_gap=None):
    """
    生病间隔检查：距上次生病至少 MIN_ILLNESS_GAP_DAYS 天，
    避免出现"一个月生好几次病"这种不现实的情况。
    """
    min_gap = MIN_ILLNESS_GAP_DAYS if min_gap is None else min_gap
    last = getattr(player, "last_illness_day", None)
    if last is None:
        return True
    return (getattr(player, "total_days", 0) - last) >= min_gap


def disease_table_text(full=False):
    """
    疾病速查表文本（用于帮助面板）。
    full=False 时只列出常见病摘要；full=True 时按分类列出全部疾病。
    """
    if not full:
        lines = ["  共收录 %d 种常见疾病，按分类如下：" % len(COMMON_DISEASE_KEYS)]
        for group_name, keys in DISEASE_GROUPS:
            names = "、".join(DISEASES[k]["name"] for k in keys if k in DISEASES)
            lines.append("  · %s（%d 种）：%s" % (group_name, len(keys), names))
        lines.append("")
        lines.append("  示例（每日健康/幸福扣除、治愈费、自愈率）：")
        for key in ("cold", "flu", "gastro", "pneumonia", "appendicitis",
                    "hypertension", "depression", "fracture"):
            d = DISEASES[key]
            lines.append("    - %s（%s）：健康 -%.1f / 幸福 -%d，治愈 %.0f，自愈 %s%s" % (
                d["name"], d["kind"], d["hp_per_day"], d["happy_per_day"], d["cure_cost"],
                pct_text(d["self_heal"]) if d["self_heal"] > 0 else "无（需治疗）",
                "，危重" if d.get("fatal") else ""))
        return "\n".join(lines)
    lines = []
    for group_name, keys in DISEASE_GROUPS:
        lines.append("【%s】" % group_name)
        for key in keys:
            d = DISEASES.get(key)
            if not d:
                continue
            days_txt = "%d~%d 天" % d["days"]
            lines.append("  · %-14s %-6s 病程 %-10s 健康 -%.1f/天  幸福 -%d/天  治愈 %-8.0f 自愈 %-6s%s" % (
                d["name"], d["kind"], days_txt, d["hp_per_day"], d["happy_per_day"],
                d["cure_cost"],
                pct_text(d["self_heal"]) if d["self_heal"] > 0 else "无",
                "  危重" if d.get("fatal") else ("  需长期治疗" if d.get("needs_cure") else "")))
        lines.append("")
    return "\n".join(lines)


def make_disease(dice, disease_id, hp_scale=1.0, days_bonus=0, temp_scale=1.0):
    """
    生成一个活动疾病实例（字典）。
    hp_scale  : 每日掉血倍率（受年龄、体质影响）
    days_bonus: 持续天数修正（负值表示恢复更快）
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]
    lo, hi = base["days"]
    # 用骰子决定持续天数，兼顾随机与均衡
    span = max(1, hi - lo + 1)
    res = dice.roll(span if span in DICE_FACES else 6, 1, 0, "病程天数")
    days = lo + (res.value - 1) % span + days_bonus
    days = max(1, int(days))
    return {
        "id": base["id"],
        "name": base["name"],
        "kind": base["kind"],
        "days": days,                                   # 剩余持续天数
        "total_days": days,
        "hp_per_day": round(base["hp_per_day"] * hp_scale, 2),
        "happy_per_day": base["happy_per_day"],
        "cure_cost": float(base["cure_cost"]),
        "self_heal": base["self_heal"],
        "temp_mod": round(base["temp_mod"] * temp_scale, 3),
        "needs_cure": base.get("needs_cure", False),
        "fatal": base.get("fatal", False),
        "severity": base.get("severity", 2),
        "desc": base.get("desc", ""),
        "tags": list(base.get("tags", [])),
        "days_roll": res.to_dict(),
    }


#: 疾病抽签的"人群适用性"倍率（scope 字段 + 年龄）
def _scope_modifier(player, disease):
    """
    某些病只在特定人群高发（例如幼儿中耳炎、老人冠心病），
    用倍率模拟真实人群分布；不适用时给一个很低但非零的权重。
    """
    scope = disease.get("scope", "all")
    age = getattr(player, "age", 30)
    if scope == "all":
        return 1.0
    if scope == "child":
        if age <= 3:
            return 2.0
        if age <= 12:
            return 1.8
        if age <= 18:
            return 1.0
        if age <= 40:
            return 0.25
        return 0.08
    if scope == "adult":
        if age < 16:
            return 0.06
        if age <= 60:
            return 1.0
        return 1.2
    if scope == "elder":
        if age < 45:
            return 0.05
        if age < 60:
            return 0.4
        if age < 75:
            return 1.3
        return 2.0
    return 1.0


def disease_weight_for(player, disease_id):
    """
    计算某种疾病相对易感程度：
        城市气候 + 季节 + 年龄人群 + 体质 + 当前体温 + 健康状态。
    疾病种类扩展到 30+ 种后，这里统一用"标签 + scope"驱动，避免逐病硬编码。
    """
    disease = DISEASES.get(disease_id) or DISEASES["cold"]
    city = get_city(player.city)
    base = float(city["disease_weights"].get(disease_id, 5))
    tags = set(disease.get("tags") or [])
    season = season_of_month(player.month)
    contagion = float(disease.get("contagion", 0) or 0)

    # ---- 季节修正 ----
    season_mod = 1.0
    if "fever" in tags or contagion >= 2:
        # 呼吸道/传染病：冬春高发
        season_mod *= {1: 1.25, 2: 0.7, 3: 1.3, 4: 1.8}.get(season, 1.0)
    if "chill" in tags:
        season_mod *= {1: 0.6, 2: 0.0, 3: 0.8, 4: 2.4}.get(season, 1.0)
    if disease_id == "heatstroke" or "heat" in tags:
        season_mod *= {1: 0.4, 2: 2.4, 3: 0.7, 4: 0.0}.get(season, 1.0)
    if disease_id in ("gastro", "food_poisoning"):
        # 夏季食物易变质
        season_mod *= {1: 1.0, 2: 1.7, 3: 1.1, 4: 0.8}.get(season, 1.0)
    if "injury" in tags:
        season_mod *= {1: 1.1, 2: 1.15, 3: 1.05, 4: 1.15}.get(season, 1.0)
    if "mental" in tags:
        # 换季与冬季情绪问题更多
        season_mod *= {1: 1.1, 2: 1.0, 3: 1.05, 4: 1.2}.get(season, 1.0)
    base *= season_mod

    # ---- 人群适用性（年龄）----
    base *= _scope_modifier(player, disease)

    # ---- 年龄修正：老人更易重症/慢性病，幼儿更易感染 ----
    age = player.age
    severity = disease.get("severity", 2)
    if age <= 6:
        if "fever" in tags or contagion >= 1:
            base *= 1.35
        if "chronic" in tags or severity >= 4:
            base *= 0.2
    elif age >= 60:
        if "chronic" in tags or severity >= 4:
            base *= 1.7
        if "fever" in tags:
            base *= 1.4
    elif age >= 45:
        if "chronic" in tags or severity >= 4:
            base *= 1.3

    # ---- 体温异常 ----
    if player.temp >= 38.0 and ("fever" in tags or severity >= 4):
        base *= 1.35
    if player.temp <= 35.2 and ("chill" in tags or "fever" in tags):
        base *= 1.45

    # ---- 体质影响易感程度（体质越好，重病概率越低）----
    sus = constitution_susceptibility(getattr(player, "constitution", CONSTITUTION_MEAN))
    base *= (0.6 + 0.5 * sus)

    # ---- 健康低时更容易病倒 ----
    if player.health <= 40:
        base *= 1.3
    return max(0.4, base)


def roll_disease(dice, player, hp_scale=1.0, forced_id=None):
    """
    用加权骰子抽取一种疾病并生成实例。
    返回 (疾病实例 或 None, DiceResult, 说明)
    说明：真正是否发病由 sickness_probability（U 型年龄曲线）决定，
          掷骰失败表示"这次没有真的病倒"，返回 None。
    """
    if forced_id:
        return make_disease(dice, forced_id, hp_scale), dice.d4("重症判定"), ""
    # ---- 是否真的生病：d100 与年龄相关的发病概率对抗 ----
    gate_roll = dice.d100("患病判定")
    prob = sickness_probability(player)
    if gate_roll.value > prob * 100.0:
        return None, gate_roll, "这次身体扛住了，没有发展成疾病"
    weight_items = []
    for key in DISEASES:
        w = disease_weight_for(player, key)
        # 用 d10 做一个轻微随机扰动，避免完全固定
        jitter = dice.d10("易感扰动").value / 10.0
        weight_items.append((key, w * (0.6 + jitter * 0.8)))
    total = sum(w for _, w in weight_items) or 1.0
    res = dice.d100("疾病判定")
    acc = 0.0
    target = (res.value - 0.5) / 100.0 * total
    chosen = weight_items[-1][0]
    for key, w in weight_items:
        acc += w
        if target <= acc:
            chosen = key
            break
    return make_disease(dice, chosen, hp_scale), res, ""
