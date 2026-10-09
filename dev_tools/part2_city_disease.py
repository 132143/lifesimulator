

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
        "disease_weights": {"cold": 20, "gastro": 8, "pneumonia": 10, "chronic": 10, "frostbite": 12, "heatstroke": 1},
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
        "disease_weights": {"cold": 18, "gastro": 12, "pneumonia": 10, "chronic": 12, "frostbite": 6, "heatstroke": 3},
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
        "disease_weights": {"cold": 16, "gastro": 18, "pneumonia": 8, "chronic": 8, "frostbite": 2, "heatstroke": 8},
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
        "disease_weights": {"cold": 12, "gastro": 16, "pneumonia": 6, "chronic": 6, "frostbite": 1, "heatstroke": 16},
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
#   days               : (最短, 最长) 持续天数
#   hp_per_day         : 每日健康扣除
#   happy_per_day      : 每日幸福扣除
#   cure_cost          : 彻底治愈费用
#   self_heal          : 每日自愈概率（0 表示不会自愈，只能花钱）
#   temp_mod           : 每日体温累积影响（发烧为正、冻伤为负）
#   needs_cure         : True 表示必须花钱治疗，否则一直持续（慢性病）
#   fatal              : True 表示危重疾病，健康过低时可能直接致死
# ==============================================================================

DISEASES = {
    "cold": {
        "id": "cold", "name": "感冒", "kind": "轻症",
        "desc": "一场小感冒，鼻塞头痛，休息几天大多能好。",
        "days": (2, 5), "hp_per_day": 2, "happy_per_day": 2,
        "cure_cost": 80.0, "self_heal": 0.55, "temp_mod": 0.12,
    },
    "gastro": {
        "id": "gastro", "name": "肠胃炎", "kind": "中症",
        "desc": "上吐下泻，浑身发软，吃点药能缓解，但拖久了伤身。",
        "days": (3, 8), "hp_per_day": 3, "happy_per_day": 3,
        "cure_cost": 320.0, "self_heal": 0.30, "temp_mod": 0.08,
    },
    "pneumonia": {
        "id": "pneumonia", "name": "肺炎", "kind": "重症",
        "desc": "高烧不退、咳嗽胸痛，必须住院治疗，否则非常危险。",
        "days": (7, 16), "hp_per_day": 6, "happy_per_day": 5,
        "cure_cost": 2600.0, "self_heal": 0.05, "temp_mod": 0.32, "fatal": True,
    },
    "chronic": {
        "id": "chronic", "name": "慢性病", "kind": "顽疾",
        "desc": "需要长期吃药控制的慢性疾病，不治会一直拖累身体。",
        "days": (20, 40), "hp_per_day": 1.5, "happy_per_day": 2,
        "cure_cost": 1800.0, "self_heal": 0.0, "temp_mod": 0.02,
        "needs_cure": True,
    },
    "frostbite": {
        "id": "frostbite", "name": "冻伤", "kind": "外伤",
        "desc": "手脚冻得失去知觉，严重时皮肤发黑，必须尽快处理。",
        "days": (3, 9), "hp_per_day": 3.5, "happy_per_day": 3,
        "cure_cost": 260.0, "self_heal": 0.25, "temp_mod": -0.30,
    },
    "heatstroke": {
        "id": "heatstroke", "name": "中暑", "kind": "急症",
        "desc": "头晕恶心、体温飙升，需要马上降温补水。",
        "days": (2, 6), "hp_per_day": 4, "happy_per_day": 4,
        "cure_cost": 300.0, "self_heal": 0.35, "temp_mod": 0.35,
    },
}

#: 疾病严重度排序（用于判断"是否更严重"，避免小病覆盖大病）
DISEASE_SEVERITY = {"cold": 1, "frostbite": 2, "heatstroke": 2, "gastro": 3,
                    "chronic": 4, "pneumonia": 5}

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


def disease_table_text():
    """疾病速查表文本（用于帮助面板）。"""
    lines = []
    for key in ("cold", "gastro", "pneumonia", "chronic", "frostbite", "heatstroke"):
        d = DISEASES[key]
        lines.append("  · %s（%s）：每日健康 -%d / 幸福 -%d，治愈费 %.0f，自愈率 %s%s" % (
            d["name"], d["kind"], d["hp_per_day"], d["happy_per_day"], d["cure_cost"],
            pct_text(d["self_heal"]) if d["self_heal"] > 0 else "无（必须治疗）",
            "，危重" if d.get("fatal") else ""))
    return "\n".join(lines)


def make_disease(dice, disease_id, hp_scale=1.0, days_bonus=0, temp_scale=1.0):
    """
    生成一个活动疾病实例（字典）。
    hp_scale  : 每日掉血倍率（受年龄、体质影响）
    days_bonus: 持续天数修正（负值表示恢复更快）
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]
    lo, hi = base["days"]
    # 用 d4/d6 决定持续天数，兼顾随机与均衡
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
        "days_roll": res.to_dict(),
    }


def disease_weight_for(player, disease_id):
    """
    计算某种疾病相对易感程度：城市气候 + 季节 + 年龄 + 当前体温。
    """
    city = get_city(player.city)
    base = float(city["disease_weights"].get(disease_id, 5))
    season = season_of_month(player.month)
    # 季节修正
    season_mod = {
        "cold": {1: 1.2, 2: 0.7, 3: 1.3, 4: 1.8},
        "pneumonia": {1: 1.1, 2: 0.6, 3: 1.2, 4: 1.8},
        "gastro": {1: 1.0, 2: 1.6, 3: 1.1, 4: 0.8},
        "chronic": {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.1},
        "frostbite": {1: 0.6, 2: 0.0, 3: 0.8, 4: 2.4},
        "heatstroke": {1: 0.5, 2: 2.4, 3: 0.8, 4: 0.0},
    }.get(disease_id, {}).get(season, 1.0)
    base *= season_mod

    # 年龄修正：老人小孩更易重症
    age = player.age
    if age <= 6:
        age_mod = 1.35 if disease_id in ("cold", "pneumonia", "gastro") else 1.1
    elif age >= 60:
        age_mod = 1.6 if disease_id in ("pneumonia", "chronic", "cold") else 1.3
    elif age >= 45:
        age_mod = 1.25 if disease_id in ("chronic", "pneumonia") else 1.05
    else:
        age_mod = 1.0
    base *= age_mod

    # 体温异常修正
    if player.temp >= 38.0 and disease_id in ("pneumonia", "cold", "heatstroke"):
        base *= 1.35
    if player.temp <= 35.2 and disease_id in ("frostbite", "cold", "pneumonia"):
        base *= 1.45

    # 健康低时更容易病倒
    if player.health <= 40:
        base *= 1.3
    return max(0.5, base)


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
