

# ==============================================================================
# 8. 事件库
# ==============================================================================
# 每个事件包含：
#   id / name / category : 标识、名称、大类
#   weight               : 基础权重（越高越容易抽到）
#   cond(player)         : 触发条件
#   descs                : 事件描述模板（支持 {name} {age} 等占位符）
#   choices              : [{"label":..., "hint":..., "roll":"d6", "outcomes":[...]}]
#        每个 outcome: {"range":(low,high), "desc":..., "effects":{...}, "tone":...}
#   tone                 : 事件基调（good/bad/neutral/secret）
#   special              : 是否为隐藏特殊事件
# ==============================================================================

TRUE_TONE_COLORS = {
    "good": "#4ad07a",
    "bad": "#ff6b6b",
    "neutral": "#f0c040",
    "secret": "#b98cff",
}

EVENTS = {}
EVENT_ORDER = []


def register_event(event, internal=False):
    """
    注册事件到全局事件表。
    internal=True 表示该事件不作为候选（例如"感冒加重"只能由感冒硬扛失败触发）。
    """
    EVENTS[event["id"]] = event
    if not internal:
        EVENT_ORDER.append(event["id"])
    return event


def _ev(eid, name, category, weight, descs, choices, cond=None, tone="neutral",
        special=False, tags=None, internal=False):
    """事件注册辅助函数。"""
    return register_event({
        "id": eid,
        "name": name,
        "category": category,
        "weight": weight,
        "descs": descs,
        "choices": choices,
        "cond": cond or (lambda p: True),
        "tone": tone,
        "special": special,
        "tags": tags or [],
    }, internal=internal)


def _out(lo, hi, desc, effects=None, tone="neutral", next_event=None):
    """
    构造一个结果区间。
    next_event 用于"连锁事件"：结算完本结果后立刻追加一个后续事件。
    """
    return {"range": (lo, hi), "desc": desc, "effects": effects or {},
            "tone": tone, "next_event": next_event}


def _choice(label, hint="", roll="d6", outcomes=None, need_money=0, need_disease=False):
    return {
        "label": label,
        "hint": hint,
        "roll": roll,
        "outcomes": outcomes or [],
        "need_money": need_money,
        "need_disease": need_disease,
    }


# ------------------------------------------------------------------------------
# 8.1 疾病类事件
# ------------------------------------------------------------------------------

def _apply_disease_factory(disease_id, hp_scale=1.0, temp_scale=1.0, days_bonus=0):
    """
    生成一个强制施加指定疾病的 func（用于"病情必然加重"的连锁事件）。
    注意：普通患病事件请使用 _apply_disease_gate，让患病概率遵守 U 型年龄曲线。
    """
    def _apply(player):
        if player.has_disease(disease_id):
            return ["你身上的%s还没好，这次是雪上加霜。" % DISEASES[disease_id]["name"]]
        info, _ = player.add_disease(disease_id, hp_scale=hp_scale,
                                     temp_scale=temp_scale, days_bonus=days_bonus,
                                     force=True)
        if not info:
            return []
        return ["患上了%s（预计持续 %d 天，每日健康 -%.1f）"
                % (info["name"], info["days"], info["hp_per_day"])]
    return _apply


def _apply_disease_gate(disease_id, hp_scale=1.0, temp_scale=1.0):
    """
    生成一个"先判定再患病"的 func：
    若玩家当前没有该疾病，则按 U 型年龄曲线 + 体质判定是否真的病倒。
    （用于"是否发病还不确定"的场景，例如硬扛之后病情加重）
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]

    def _apply(player):
        if player.has_disease(disease_id):
            return ["你身上的%s还没好，这次是雪上加霜。" % base["name"]]
        info, _ = player.add_disease(disease_id, hp_scale=hp_scale,
                                     temp_scale=temp_scale)
        if not info:
            return ["幸好这次身体扛住了，没有真的病倒。"]
        return ["患上了%s（预计持续 %d 天，每日健康 -%.1f）"
                % (info["name"], info["days"], info["hp_per_day"])]
    return _apply


def _apply_disease_definite(disease_id, hp_scale=1.0, temp_scale=1.0, days_bonus=0):
    """
    生成一个"确定患病"的 func（不再判定概率）。
    用于生病机会已经判定通过的场景：此时角色确实已经不舒服，
    因此选择"硬扛/不治疗"就必然发展成真正的疾病。
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]

    def _apply(player):
        if player.has_disease(disease_id):
            return ["你身上的%s还没好，这次是雪上加霜。" % base["name"]]
        info, _ = player.add_disease(disease_id, hp_scale=hp_scale,
                                     temp_scale=temp_scale,
                                     days_bonus=days_bonus, force=True)
        if not info:
            return []
        return ["患上了%s（预计持续 %d 天，每日健康 -%.1f）"
                % (info["name"], info["days"], info["hp_per_day"])]
    return _apply


_ev("illness_cold", "着凉感冒", "疾病", 26,
    ["夜里窗户没关严，第二天起来嗓子发紧、喷嚏不断，一看就是感冒了。",
     "换季时节气温反复，你开始流鼻涕、头晕，典型的感冒症状。"],
    [_choice("花钱买药治好", "小额支出，基本立刻康复", "d10", [
        _out(1, 9, "药到病除，你很快就恢复了精神。", {"money": -80, "temp": 0.1, "cure": True}, "good"),
        _out(10, 10, "药没压住，还是病倒了。",
             {"money": -80, "func": _apply_disease_definite("cold", 0.8)}, "bad"),
    ]),
     _choice("多喝热水硬扛", "大部分能自愈，也可能真的病倒", "d6", [
        _out(1, 2, "硬扛了几天越来越重，炎症往下走了。",
             {"func": _apply_disease_definite("cold", 1.0)}, "bad",
             next_event="illness_cold_worse"),
        _out(3, 6, "睡了几觉，感冒自己好了。", {"happy": +1}, "good"),
    ])],
    tone="bad", tags=["disease"])

# 「感冒加重」为连锁事件：只能由「着凉感冒-硬扛失败」触发，不参与日常抽取
_ev("illness_cold_worse", "感冒加重", "疾病", 0,
    ["感冒没好利索，咳嗽越来越深，夜里开始发烧。"],
    [_choice("花钱去医院", "正规治疗，快速恢复", "d4", [
        _out(1, 4, "输液之后症状明显缓解。", {"money": -260, "happy": +2}, "good"),
    ]),
     _choice("继续硬扛", "可能发展成肺炎", "d6", [
        _out(1, 2, "病情失控，发展成了肺炎！", {"func": _apply_disease_factory("pneumonia", 1.0, 1.0)}, "bad"),
        _out(3, 6, "终于靠着休息扛过去了。", {"health": -4}, "neutral"),
    ])],
    tone="bad", tags=["disease"], internal=True)

_ev("illness_gastro", "吃坏肚子", "疾病", 22,
    ["路边摊的宵夜格外香，半夜你的肚子开始翻江倒海。",
     "一顿火锅配冰啤，第二天早上你抱着马桶站不起来。"],
    [_choice("买药调理", "花小钱稳妥解决", "d10", [
        _out(1, 9, "吃了药，肠胃很快平静下来。", {"money": -120, "cure": True, "health": +2}, "good"),
        _out(10, 10, "药吃晚了，还是拉了两天。",
             {"money": -120, "func": _apply_disease_definite("gastro", 0.8)}, "bad"),
    ]),
     _choice("饿两天挺过去", "省钱但风险高", "d6", [
        _out(1, 2, "越拖越严重，落下了肠胃炎。", {"func": _apply_disease_definite("gastro", 1.0)}, "bad"),
        _out(3, 6, "清汤寡水两天，居然好了。", {"health": -2, "happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["disease"])

_ev("illness_pneumonia", "高烧不退", "疾病", 10,
    ["连续几天高烧不退，咳嗽时胸口像被撕开一样疼。",
     "半夜咳醒，呼吸都带着杂音，家人催你赶紧去医院。"],
    [_choice("住院治疗", "费用高昂但救命", "d4", [
        _out(1, 4, "住院一周后，病情终于控制住了。", {"money": -2000, "happy": +5, "health": -3, "cure": True}, "good"),
    ]),
     _choice("吃退烧药硬撑", "极度危险", "d6", [
        _out(1, 3, "病情急剧恶化，你被送进了急诊室。",
             {"func": _apply_disease_definite("pneumonia", 1.3)}, "bad"),
        _out(4, 6, "烧退了，但身体虚得厉害。", {"health": -10, "happy": -6}, "neutral"),
    ])],
    tone="bad", tags=["disease"], cond=lambda p: p.age >= 5)

_ev("illness_chronic", "查出慢性病", "疾病", 9,
    ["体检报告上出现了一个不太友好的名词，医生建议长期服药控制。",
     "最近总是乏力、失眠，检查后发现是慢性疾病在作祟。"],
    [_choice("遵医嘱长期治疗", "花钱买健康", "d4", [
        _out(1, 4, "按时吃药复查，指标慢慢稳定了。", {"money": -1500, "happy": -2, "health": +2}, "neutral"),
    ]),
     _choice("先不管它", "省下钱，但身体会持续受损", "d6", [
        _out(1, 4, "慢性病就这么拖了下来，身体一天不如一天。",
             {"func": _apply_disease_definite("chronic")}, "bad"),
        _out(5, 6, "你调整作息、锻炼身体，竟没留下病根。", {"happy": +3, "health": -2}, "good"),
    ])],
    tone="bad", tags=["disease"], cond=lambda p: p.age >= 30)

_ev("illness_seasonal", "流感季节", "疾病", 18,
    ["季节交替，办公室一半人都在咳嗽，你也开始觉得发冷。",
     "新闻里说最近流感高发，你恰好在这个节骨眼上不舒服了。"],
    [_choice("打疫苗 + 休息", "小投入大回报", "d6", [
        _out(1, 5, "你成功躲过了这波流感。", {"money": -200, "happy": +2}, "good"),
        _out(6, 6, "疫苗也没挡住，还是中招了。",
             {"func": _apply_disease_definite("cold", 0.8)}, "bad"),
    ]),
     _choice("照常生活", "碰运气", "d6", [
        _out(1, 3, "你病倒了，发烧三天。", {"func": _apply_disease_definite("cold", 1.1)}, "bad"),
        _out(4, 6, "你的免疫力意外地强，毫发无伤。", {"happy": +1}, "good"),
    ])],
    tone="bad", tags=["disease"])

_ev("illness_frostbite", "冻伤", "疾病", 12,
    ["在室外待得太久，手脚先麻后疼，指尖泛起青紫色。",
     "寒风像刀子一样刮在脸上，回屋后你的耳朵和手指失去了知觉。"],
    [_choice("立刻就医处理", "快速止损", "d4", [
        _out(1, 4, "医生处理及时，只是轻微冻伤。", {"money": -260, "temp": +0.2, "cure": True}, "good"),
    ]),
     _choice("用雪搓一搓", "民间偏方，风险很大", "d6", [
        _out(1, 3, "偏方没用，冻伤加重了。", {"func": _apply_disease_definite("frostbite", 1.2)}, "bad"),
        _out(4, 6, "不知是运气还是偏方有效，居然缓过来了。", {"health": -4}, "neutral"),
    ])],
    tone="bad", tags=["disease"],
    cond=lambda p: get_city(p.city)["tag"] == "寒冷" or p.ambient_temp <= 0)

_ev("illness_heatstroke", "中暑", "疾病", 12,
    ["太阳晒得柏油路都在冒热气，你突然一阵天旋地转。",
     "高温下你出了太多汗，喝水的速度完全跟不上流失。"],
    [_choice("马上降温补水", "及时处理", "d4", [
        _out(1, 4, "在阴凉处缓了一会儿，只是轻微中暑。", {"money": -80, "temp": -0.2, "cure": True}, "good"),
    ]),
     _choice("咬牙继续干活", "硬扛高温", "d6", [
        _out(1, 3, "你眼前一黑，被送去了医院。",
             {"func": _apply_disease_definite("heatstroke", 1.2)}, "bad"),
        _out(4, 6, "靠着意志力撑了过去。", {"health": -5, "happy": -3}, "neutral"),
    ])],
    tone="bad", tags=["disease"],
    cond=lambda p: get_city(p.city)["tag"] == "炎热" or p.ambient_temp >= 30)


# ------------------------------------------------------------------------------
# 8.2 工作事业类事件
# ------------------------------------------------------------------------------

def _func_join_work(level=1, happiness=3):
    def _apply(player):
        if player.employed:
            return []
        player.employed = True
        player.job_level = max(1, level)
        return ["你正式入职，开始了打工人生涯（职级 %d）。" % player.job_level]
    return _apply


def _func_promote(level=1):
    def _apply(player):
        if not player.employed:
            return []
        player.job_level = min(10, player.job_level + level)
        return ["职级提升到 %d 级。" % player.job_level]
    return _apply


def _func_fire(reason="被裁员"):
    def _apply(player):
        if not player.employed:
            return []
        player.employed = False
        player.job_level = 0
        return ["你失去了工作。"]
    return _apply


_ev("work_gain_job", "找到工作", "工作", 16,
    ["你投出的简历终于有了回音，HR 约你下周一入职。",
     "几轮面试之后，你拿到了一份还算满意的 offer。"],
    [_choice("接受这份工作", "开始稳定收入", "d6", [
        _out(1, 4, "你顺利入职，工资按职级发放。", {"happy": +6, "func": _func_join_work(1)}, "good"),
        _out(5, 6, "入职第一天就发现团队氛围极好，你干劲十足。", {"happy": +10, "func": _func_join_work(2)}, "good"),
    ]),
     _choice("再等等更好的机会", "空窗期继续", "d6", [
        _out(1, 3, "更好的机会没来，你还得继续找。", {"happy": -3}, "bad"),
        _out(4, 6, "三天后你等到了一个待遇更好的岗位。", {"happy": +8, "func": _func_join_work(2)}, "good"),
    ])],
    tone="good", tags=["work"], cond=lambda p: (not p.employed) and p.age >= 18)

_ev("work_hard_work", "工作任务", "工作", 20,
    ["主管把一个棘手的项目丢给了你，说「年轻人多锻炼」。",
     "季度考核临近，桌面上堆着做不完的报表。"],
    [_choice("加班加点完成", "健康换钱", "d10", [
        _out(1, 3, "你熬了通宵，成果不错，但身体透支了。", {"money": +600, "health": -6, "happy": -4}, "neutral"),
        _out(4, 8, "项目顺利完成，拿到了绩效奖金。", {"money": +1000, "happy": +3, "health": -3}, "good"),
        _out(9, 10, "你的方案被高层看中，全组通报表扬。", {"money": +1800, "happy": +10, "func": _func_promote(1)}, "good"),
    ]),
     _choice("按部就班不加班", "保住生活节奏", "d6", [
        _out(1, 3, "进度落后，被主管约谈了一顿。", {"happy": -6}, "bad"),
        _out(4, 6, "你按时交付，虽然不出彩，但也没出错。", {"money": +300}, "neutral"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: p.employed)

_ev("work_promotion", "升职机会", "工作", 12,
    ["部门要提拔一名骨干，名单里出现了你的名字。",
     "领导找你谈话，暗示有一个晋升名额正在考虑你。"],
    [_choice("主动争取", "表现欲拉满", "d20", [
        _out(1, 4, "你用力过猛，反而让领导觉得你浮躁。", {"happy": -8}, "bad"),
        _out(5, 15, "你的积极态度被认可，顺利升职。", {"money": +1200, "happy": +10, "func": _func_promote(1)}, "good"),
        _out(16, 20, "你在关键汇报中大放异彩，连升两级！", {"money": +2400, "happy": +16, "func": _func_promote(2)}, "good"),
    ]),
     _choice("谦虚观望", "稳中求进", "d6", [
        _out(1, 3, "机会给了别人，你只能看着。", {"happy": -5}, "bad"),
        _out(4, 6, "领导觉得你沉稳可靠，下次优先考虑你。", {"happy": +4}, "neutral"),
    ])],
    tone="good", tags=["work"], cond=lambda p: p.employed and p.job_level >= 1)

_ev("work_unemployed", "裁员风波", "工作", 12,
    ["公司业绩下滑，会议室里传出裁员的消息。",
     "HR 把你叫进小房间，桌上放着一份赔偿协议。"],
    [_choice("争取赔偿后离开", "体面收场", "d6", [
        _out(1, 3, "赔偿谈得很难看，只拿到一半。", {"money": +1500, "happy": -10, "func": _func_fire()}, "bad"),
        _out(4, 6, "你拿到了 N+1 赔偿，平静地离开了。", {"money": +4000, "happy": -4, "func": _func_fire()}, "neutral"),
    ]),
     _choice("接受降薪留下", "保住饭碗", "d6", [
        _out(1, 3, "留下后你被边缘化，处处受限。", {"happy": -12, "money": -200}, "bad"),
        _out(4, 6, "公司熬过了寒冬，你也保住了职位。", {"happy": -2, "money": -500}, "neutral"),
    ])],
    tone="bad", tags=["work"], cond=lambda p: p.employed)

_ev("work_side_job", "副业机会", "工作", 14,
    ["朋友介绍你一个周末做外包的活儿，报酬不错。",
     "你在网上看到有人靠副业月入过万，心动了。"],
    [_choice("接下来做", "牺牲休息换钱", "d10", [
        _out(1, 3, "活儿比想象中麻烦，客户还拖欠尾款。", {"money": +200, "happy": -5, "health": -3}, "bad"),
        _out(4, 9, "副业收入稳定进账。", {"money": +1400, "health": -3, "happy": +2}, "good"),
        _out(10, 10, "副业意外爆单，收入超过主业。", {"money": +3600, "happy": +8, "health": -4}, "good"),
    ]),
     _choice("专心主业", "保持生活质量", "d6", [
        _out(1, 6, "你把时间用在了休息和学习上。", {"happy": +4, "health": +2}, "good"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: p.employed and p.age >= 18)

_ev("work_conflict", "职场矛盾", "工作", 12,
    ["同事把你做的方案署上了自己的名字，你气得手抖。",
     "跨部门沟通时对方当众否定你，会议室气氛瞬间凝固。"],
    [_choice("当场据理力争", "正面刚", "d20", [
        _out(1, 6, "你情绪失控，反而被扣上「不好合作」的标签。", {"happy": -12}, "bad"),
        _out(7, 18, "你拿出了证据，赢得了同事的尊重。", {"happy": +8}, "good"),
        _out(19, 20, "你的表现被大领导看到，获得了额外赏识。", {"happy": +12, "money": +800, "func": _func_promote(1)}, "good"),
    ]),
     _choice("私下沟通化解", "以柔克刚", "d10", [
        _out(1, 3, "对方不吃这套，矛盾反而加深了。", {"happy": -8}, "bad"),
        _out(4, 10, "你们把话说开了，之后配合顺畅很多。", {"happy": +5}, "good"),
    ])],
    tone="bad", tags=["work"], cond=lambda p: p.employed)

_ev("work_salary_up", "加薪谈判", "工作", 12,
    ["你所在岗位的市场价涨了不少，你决定找领导谈加薪。",
     "年底调薪窗口开启，你准备了一份业绩清单。"],
    [_choice("开门见山提数字", "强硬姿态", "d20", [
        _out(1, 5, "领导觉得你太急功近利，谈判失败。", {"happy": -8}, "bad"),
        _out(6, 17, "你的业绩有说服力，加薪成功。", {"money": +1500, "happy": +8}, "good"),
        _out(18, 20, "领导不仅加了薪，还给你配了团队。", {"money": +2500, "happy": +12, "func": _func_promote(1)}, "good"),
    ]),
     _choice("聊聊职业发展", "迂回策略", "d10", [
        _out(1, 3, "领导画了一堆大饼，什么都没落地。", {"happy": -5}, "bad"),
        _out(4, 10, "虽然没有立刻加薪，但获得了培训机会。", {"happy": +3, "money": +300}, "neutral"),
    ])],
    tone="good", tags=["work"], cond=lambda p: p.employed and p.job_level >= 1)

_ev("work_startup", "创业邀请", "工作", 8,
    ["老同学拉你合伙创业，说「这次风口是真的」。",
     "一个投资人看上了你的想法，愿意投一笔启动资金。"],
    [_choice("押上积蓄全力以赴", "高风险高回报", "d20", [
        _out(1, 8, "项目半年就黄了，钱打了水漂。", {"money": -6000, "happy": -18}, "bad"),
        _out(9, 17, "业务慢慢跑起来了，开始有稳定分红。", {"money": +3000, "happy": +10, "func": _func_promote(1)}, "good"),
        _out(18, 20, "你踩中了风口，收入翻了好几倍！", {"money": +20000, "happy": +20}, "good"),
    ]),
     _choice("婉拒，稳住工作", "不冒风险", "d6", [
        _out(1, 6, "后来那家公司真的上市了，你只能感慨。", {"happy": -4}, "neutral"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: p.age >= 22 and p.money >= 3000)

_ev("work_overtime_sick", "过度加班", "工作", 10,
    ["连续两周每天工作到凌晨，你的身体开始报警。",
     "项目冲刺期，你在工位上连续坐了十二个小时。"],
    [_choice("请病假休息", "少赚点钱", "d6", [
        _out(1, 3, "主管不太高兴，扣了全勤。", {"money": -400, "health": +4, "happy": +2}, "neutral"),
        _out(4, 6, "好好睡了两天，身体恢复了不少。", {"health": +6, "happy": +5}, "good"),
    ]),
     _choice("咬牙继续扛", "健康换绩效", "d10", [
        _out(1, 3, "你的身体彻底撑不住，晕倒在工位上。", {"health": -14, "happy": -10, "money": -800}, "bad"),
        _out(4, 8, "项目按时上线，奖金到手。", {"money": +1600, "health": -6}, "neutral"),
        _out(9, 10, "你成了团队里公认的铁人。", {"money": +2200, "health": -4, "happy": +4, "func": _func_promote(1)}, "good"),
    ])],
    tone="bad", tags=["work"], cond=lambda p: p.employed)


# ------------------------------------------------------------------------------
# 8.2b 成长与家庭类事件（覆盖童年 / 求学 / 中年人生阶段）
# ------------------------------------------------------------------------------

_ev("grow_baby", "咿呀学语", "情感", 18,
    ["你含糊地发出了第一个像样的音节，全家欢呼。",
     "你扶着桌沿摇摇晃晃地站了起来，迈出了第一步。"],
    [_choice("扑进父母怀里", "被爱包围的童年", "d6", [
        _out(1, 4, "家里给你办了小小的庆祝，你笑得停不下来。", {"happy": +6}, "good"),
        _out(5, 6, "父母把这一刻录成了视频，珍藏了很多年。", {"happy": +8, "health": +2}, "good"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: p.age <= 3)

_ev("grow_school", "开学第一天", "情感", 16,
    ["你背上新书包，站在陌生的教室门口有点紧张。",
     "老师点名时你举手的动作慢了半拍，全班都笑了。"],
    [_choice("努力当个好学生", "从小自律", "d10", [
        _out(1, 4, "功课有点跟不上，你被留下来补作业。", {"happy": -4}, "bad"),
        _out(5, 9, "你很快交到了好朋友，成绩也不错。", {"happy": +8, "money": -200}, "good"),
        _out(10, 10, "你第一次考试就拿了满分，被老师当众表扬。", {"happy": +12, "money": -200}, "good"),
    ]),
     _choice("只想玩", "快乐教育", "d6", [
        _out(1, 3, "家长被请去学校谈话，你被训了一顿。", {"happy": -6}, "bad"),
        _out(4, 6, "你在操场上度过了最快乐的时光。", {"happy": +7, "health": +2}, "good"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 5 <= p.age <= 9)

_ev("grow_exam", "重要考试", "工作", 14,
    ["这场考试的成绩，可能会决定你未来几年的去向。",
     "考场外站满了陪考的家长，你深吸了一口气走进教室。"],
    [_choice("全力备考", "拼一把", "d20", [
        _out(1, 6, "压力太大，考场上脑子一片空白。", {"happy": -12, "health": -4}, "bad"),
        _out(7, 17, "成绩出来，你考上了理想的学校。", {"happy": +16, "money": -800}, "good"),
        _out(18, 20, "你成了当年的状元，亲友纷纷来道贺。", {"happy": +24, "money": +2000}, "good"),
    ]),
     _choice("尽力就好", "不给自己压力", "d10", [
        _out(1, 5, "成绩平平，你多少有点遗憾。", {"happy": -4}, "neutral"),
        _out(6, 10, "结果比预想中好，你挺满意。", {"happy": +6}, "good"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: p.age in (15, 18, 22))

_ev("grow_bully", "校园摩擦", "情感", 12,
    ["有人故意把你的作业本扔到了地上。",
     "放学路上，几个高个子堵住了你的去路。"],
    [_choice("告诉老师家长", "寻求帮助", "d6", [
        _out(1, 3, "事情被压下去了，但对方变本加厉。", {"happy": -10}, "bad"),
        _out(4, 6, "老师严肃处理，再没人敢欺负你。", {"happy": +8}, "good"),
    ]),
     _choice("自己解决", "硬碰硬", "d10", [
        _out(1, 4, "你吃了亏，脸上挂了彩。", {"health": -6, "happy": -8}, "bad"),
        _out(5, 10, "你据理力争，对方反倒退了。", {"happy": +4, "health": -2}, "neutral"),
    ])],
    tone="bad", tags=["growth"], cond=lambda p: 8 <= p.age <= 18)

_ev("grow_parents", "父母生病", "情感", 12,
    ["电话那头母亲的声音很虚弱，说只是小毛病。",
     "父亲住院了，检查单上写着你不太懂的术语。"],
    [_choice("承担医药费并陪护", "尽孝", "d6", [
        _out(1, 3, "治疗费用高昂，你几乎花光了积蓄。", {"money": -8000, "happy": -6, "health": -4}, "neutral"),
        _out(4, 6, "父母康复了，你心里踏实了许多。", {"money": -4000, "happy": +8}, "good"),
    ]),
     _choice("先忙完工作再说", "现实的压力", "d10", [
        _out(1, 5, "你赶到时已经晚了，心里留下永远的遗憾。", {"happy": -22}, "bad"),
        _out(6, 10, "家人理解你的难处，病情也没恶化。", {"happy": -6}, "neutral"),
    ])],
    tone="bad", tags=["family"], cond=lambda p: p.age >= 25)

_ev("grow_midlife", "中年危机", "工作", 12,
    ["你突然发现自己成了公司里年纪最大的那批人。",
     "体检报告、房贷账单和孩子的学费同时摆在桌上。"],
    [_choice("转型学习新技能", "投资自己", "d20", [
        _out(1, 8, "学了半年没派上用场，还花了钱。", {"money": -3000, "happy": -8}, "bad"),
        _out(9, 17, "新技能让你在职场重新有了竞争力。", {"money": +4000, "happy": +12, "func": _func_promote(1)}, "good"),
        _out(18, 20, "你抓住行业风口，收入翻了倍。", {"money": +15000, "happy": +18}, "good"),
    ]),
     _choice("稳住现状", "不折腾", "d10", [
        _out(1, 5, "行业变化太快，你越来越吃力。", {"happy": -10, "money": -1000}, "bad"),
        _out(6, 10, "虽然没突破，但日子过得安稳。", {"happy": +2}, "neutral"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: 38 <= p.age <= 58)

_ev("grow_retire", "退休生活", "情感", 14,
    ["你办完了退休手续，工牌被收回的那一刻有些不真实。",
     "早上不用再定闹钟，你反而醒得更早了。"],
    [_choice("培养爱好，享受生活", "辛苦半生，值得", "d6", [
        _out(1, 3, "你把时间都花在了钓鱼和书法上。", {"happy": +14, "money": -1000, "health": +4}, "good"),
        _out(4, 6, "你加入了社区合唱团，认识了很多新朋友。", {"happy": +18, "health": +6, "money": -500}, "good"),
    ]),
     _choice("返聘继续赚钱", "闲不下来", "d10", [
        _out(1, 4, "身体吃不消，你很快又辞了。", {"health": -8, "money": +3000}, "neutral"),
        _out(5, 10, "返聘收入不错，你干得挺起劲。", {"money": +8000, "health": -4, "happy": +4}, "good"),
    ])],
    tone="good", tags=["family"], cond=lambda p: p.age >= 60)

_ev("grow_memory", "回忆往事", "情感", 12,
    ["翻看旧相册，你发现很多人已经很久没见了。",
     "老同学群里传来一条消息，说有人已经离开了。"],
    [_choice("联系老朋友", "珍惜眼前人", "d6", [
        _out(1, 6, "你们聊了很久，仿佛回到年少时。", {"happy": +10}, "good"),
    ]),
     _choice("把感慨留在心里", "独自消化", "d4", [
        _out(1, 4, "你泡了杯茶，安静地坐了一下午。", {"happy": +3}, "neutral"),
    ])],
    tone="neutral", tags=["social"], cond=lambda p: p.age >= 45)


# ------------------------------------------------------------------------------
# 8.2c 婴幼儿 / 童年专属事件（0~12 岁：不会说话、不能独自出门、食物有限）
# ------------------------------------------------------------------------------

_ev("baby_feed", "喝奶与辅食", "情感", 26,
    ["你还不会说话，饿了只能用哭声表达。妈妈试着换了两种奶粉。",
     "大人把米糊调得稀稀的，一勺一勺喂进你嘴里。"],
    [_choice("乖乖喝完", "吃饱就睡，最幸福的年纪", "d6", [
        _out(1, 4, "你一口气喝完了，打了个小小的嗝。", {"health": +1, "happy": +4}, "good"),
        _out(5, 6, "你喝得满脸都是，逗得全家大笑。", {"health": +2, "happy": +7}, "good"),
    ]),
     _choice("扭头不肯吃", "挑食的小脾气", "d6", [
        _out(1, 3, "你哭闹了半天，最后只喝了半瓶。", {"happy": -2, "health": -1}, "bad"),
        _out(4, 6, "换成另一种口味后你终于肯吃了。", {"happy": +3, "money": -80}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: p.age <= 2)

_ev("baby_sleep", "哭闹的夜晚", "情感", 24,
    ["半夜你又哭醒了，父母轮流抱着你在屋里走来走去。",
     "你被噩梦惊醒，怎么哄都不肯睡。"],
    [_choice("被抱着哄睡", "有安全感的孩子", "d6", [
        _out(1, 4, "你在妈妈的怀里很快又睡着了。", {"health": +1, "happy": +5}, "good"),
        _out(5, 6, "大人一夜没睡，第二天顶着黑眼圈上班。", {"happy": +3}, "neutral"),
    ]),
     _choice("自己哭到累", "大人实在太困了", "d6", [
        _out(1, 3, "你哭到嗓子哑了，全家都没休息好。", {"health": -2, "happy": -3}, "bad"),
        _out(4, 6, "哭累了之后你自己睡着了。", {"happy": -1}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: p.age <= 3)

_ev("baby_sick_care", "发烧的婴儿", "疾病", 16,
    ["你半夜烧到 38.6℃，还不会说话的只能一直哼哼。",
     "大人摸你的额头觉得烫手，赶紧翻出体温计。"],
    [_choice("连夜去医院", "婴儿病情不能拖", "d6", [
        _out(1, 6, "医生说是普通感染，开了药，第二天就退烧了。", {"money": -400, "health": -1, "happy": +3}, "good"),
    ]),
     _choice("物理降温观察", "先试试看", "d10", [
        _out(1, 4, "烧一直退不下来，最后还是去了医院。", {"money": -600, "health": -4, "happy": -3}, "bad"),
        _out(5, 10, "温水擦身之后体温慢慢降了下来。", {"health": -1}, "neutral"),
    ])],
    tone="bad", tags=["disease", "growth"], cond=lambda p: p.age <= 4)

_ev("baby_first_word", "第一次说话", "情感", 22,
    ["你清晰地喊出了人生第一个词，全家人愣了两秒后笑作一团。",
     "你指着窗外，含含糊糊地说出了一个像样的音节。"],
    [_choice("继续学新词", "语言爆发期", "d6", [
        _out(1, 4, "你很快学会了「爸爸」「妈妈」，家里天天充满笑声。", {"happy": +9}, "good"),
        _out(5, 6, "你学会的词越来越多，还会学大人说话的语气。", {"happy": +12, "health": +1}, "good"),
    ]),
     _choice("只顾着玩", "说话的事不着急", "d4", [
        _out(1, 4, "你还是更喜欢用哭声和手指表达。", {"happy": +2}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 1 <= p.age <= 4)

_ev("baby_crawl", "学步", "情感", 20,
    ["你扶着沙发摇摇晃晃地站起来，朝玩具的方向挪了两步。",
     "你扶着墙一点点往前挪，膝盖一软又坐到了地上。"],
    [_choice("继续练", "摔了也不哭", "d6", [
        _out(1, 3, "你摔了好几次，膝盖蹭破了点皮。", {"health": -1, "happy": +4}, "neutral"),
        _out(4, 6, "你终于能自己走几步了，全家鼓掌。", {"health": +2, "happy": +10}, "good"),
    ]),
     _choice("抱着不撒手", "大人怕你摔", "d6", [
        _out(1, 6, "你被抱在怀里，安安静静地看着别人跑跳。", {"happy": +2}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 1 <= p.age <= 3)

_ev("baby_kindergarten", "幼儿园第一天", "情感", 18,
    ["你被送进幼儿园，转身发现妈妈已经走了，眼泪一下子涌出来。",
     "小朋友们在玩积木，你抱着自己的小书包站在门口不敢进去。"],
    [_choice("试着融入大家", "迈出社交第一步", "d6", [
        _out(1, 3, "你想妈妈想了半天，午睡时偷偷哭了。", {"happy": -4}, "bad"),
        _out(4, 6, "老师牵着你一起搭积木，你很快交到了第一个朋友。", {"happy": +10}, "good"),
    ]),
     _choice("不想上幼儿园", "抱着门框不撒手", "d6", [
        _out(1, 6, "大人在门口哄了你半个小时。", {"happy": -2}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 3 <= p.age <= 6)

_ev("child_chore", "被安排做家务", "情感", 14,
    ["父母让你把自己的玩具收好，说「自己的事情自己做」。",
     "家里大扫除，你被分配了擦桌子的活儿。"],
    [_choice("认真做完", "从小养成习惯", "d6", [
        _out(1, 4, "你把桌子擦得干干净净，得到了表扬。", {"happy": +6}, "good"),
        _out(5, 6, "你还顺便整理了书架，妈妈奖励了你零花钱。", {"happy": +8, "money": +50}, "good"),
    ]),
     _choice("偷懒溜走", "去看动画片", "d6", [
        _out(1, 3, "你被抓了回来，还被没收了遥控器。", {"happy": -6}, "bad"),
        _out(4, 6, "你成功溜掉了，看得正开心。", {"happy": +3}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 4 <= p.age <= 12)

_ev("child_pocket_money", "零花钱", "情感", 16,
    ["过年收到的红包被妈妈「帮忙保管」了，你手里只剩下一点零钱。",
     "你攒了两个月的零花钱，正犹豫要买什么。"],
    [_choice("买心心念念的玩具", "童年的快乐", "d6", [
        _out(1, 4, "你把玩具抱回家，玩了整整一个下午。", {"money": -100, "happy": +9}, "good"),
        _out(5, 6, "玩具比想象中好玩，你还和同学交换着玩。", {"money": -100, "happy": +12}, "good"),
    ]),
     _choice("存起来", "小小理财家", "d6", [
        _out(1, 6, "你把钱塞进了储蓄罐，看着数字变多很有成就感。", {"happy": +4}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 5 <= p.age <= 14)

_ev("child_food_limit", "挑食", "情感", 16,
    ["餐桌上是你不爱吃的青菜，你把碗推开了一点。",
     "家里条件有限，今晚的菜色和昨天差不多。"],
    [_choice("乖乖吃完", "不挑食长得高", "d6", [
        _out(1, 4, "你把青菜吃完了，妈妈给你盛了第二碗饭。", {"health": +2, "happy": +3}, "good"),
        _out(5, 6, "你渐渐习惯了这种味道，身体也结实了些。", {"health": +3, "happy": +4}, "good"),
    ]),
     _choice("坚决不吃", "饿着也不碰", "d6", [
        _out(1, 3, "你饿了一顿，半夜爬起来找饼干。", {"health": -1, "happy": -3}, "bad"),
        _out(4, 6, "大人无奈，给你煮了个鸡蛋。", {"happy": +2}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 2 <= p.age <= 12)

_ev("child_homework", "写不完的作业", "工作", 18,
    ["明天要交的作业还剩一大半，你的铅笔却越写越慢。",
     "老师布置的卷子摊在桌上，窗外传来小伙伴的笑声。"],
    [_choice("先写完再玩", "自律的孩子", "d10", [
        _out(1, 4, "你写到很晚，眼皮一直在打架。", {"health": -2, "happy": -2}, "neutral"),
        _out(5, 9, "你把作业写完才出门，玩得特别踏实。", {"happy": +6}, "good"),
        _out(10, 10, "作业全对，老师在班上念了你的名字。", {"happy": +10}, "good"),
    ]),
     _choice("先出去玩", "明天再说", "d10", [
        _out(1, 5, "你玩到天黑，回家被批评了一顿，作业写到半夜。", {"happy": -6, "health": -1}, "bad"),
        _out(6, 10, "你玩得开心，作业赶在睡前写完了。", {"happy": +5}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 6 <= p.age <= 15)

_ev("child_parent_trip", "全家出游", "情感", 12,
    ["父母带你去了动物园，你第一次见到真的长颈鹿。",
     "一家人坐了很远的车去海边，你的鞋里全是沙子。"],
    [_choice("尽情玩耍", "童年最好的回忆", "d6", [
        _out(1, 4, "你玩到太阳落山，回家路上在车上睡着了。", {"money": -500, "happy": +12}, "good"),
        _out(5, 6, "你拍了很多照片，多年后还会翻出来看。", {"money": -500, "happy": +16}, "good"),
    ]),
     _choice("嫌累不想走", "闹起了脾气", "d6", [
        _out(1, 3, "你在景区门口哭闹，全家行程被打乱。", {"money": -300, "happy": -4}, "bad"),
        _out(4, 6, "吃了冰淇淋之后你又开心起来了。", {"money": -400, "happy": +6}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 3 <= p.age <= 14)


# ------------------------------------------------------------------------------
# 8.2d 平凡的一天（无事发生）：占比最高，让日子不总是跌宕起伏
# ------------------------------------------------------------------------------

_ev("plain_day_1", "平凡的一天", "日常", 40,
    ["今天和往常没什么两样：起床、吃饭、做事、睡觉。",
     "平淡的一天过去了，没有什么值得记录的事。"],
    [_choice("就这样过去", "风平浪静", "d6", [
        _out(1, 4, "一天平平淡淡地结束了。", {"happy": +1}, "neutral"),
        _out(5, 6, "你在路上看到一场很美的晚霞。", {"happy": +3}, "good"),
    ])],
    tone="neutral", tags=["plain"], cond=lambda p: True)

_ev("plain_day_2", "安静的日常", "日常", 34,
    ["今天没有意外，也没有惊喜，日子按部就班。",
     "你把该做的事都做完了，剩下的时间发了一会儿呆。"],
    [_choice("享受平静", "平淡是福", "d6", [
        _out(1, 4, "你在窗边坐了一会儿，心里很安静。", {"happy": +2}, "neutral"),
        _out(5, 6, "你顺手整理了房间，心情也清爽了。", {"happy": +4, "health": +1}, "good"),
    ])],
    tone="neutral", tags=["plain"], cond=lambda p: True)

_ev("plain_day_3", "重复的节奏", "日常", 30,
    ["闹钟、通勤、三餐、睡觉——今天几乎和昨天一模一样。",
     "一整天的安排都被填满，却又好像什么都没发生。"],
    [_choice("照常度过", "生活本来的样子", "d6", [
        _out(1, 3, "你在重复的节奏里感到一点疲惫。", {"happy": -1}, "neutral"),
        _out(4, 6, "习惯了之后，你反而觉得踏实。", {"happy": +2}, "good"),
    ])],
    tone="neutral", tags=["plain"], cond=lambda p: True)

_ev("plain_day_4", "小小的惬意", "日常", 26,
    ["你给自己泡了杯热茶，看着窗外发了会儿呆。",
     "今天天气不错，你把被子拿出去晒了晒。"],
    [_choice("慢慢过日子", "给自己一点温柔", "d6", [
        _out(1, 4, "你睡了个舒服的午觉。", {"health": +1, "happy": +3}, "good"),
        _out(5, 6, "你随手拍下一张照片，觉得这一天很好。", {"happy": +5}, "good"),
    ])],
    tone="good", tags=["plain"], cond=lambda p: True)



# ------------------------------------------------------------------------------
# 8.3 情感社交类事件（婚恋、社交；婴幼儿不会说话、不能独自出门，故有严格年龄限制）
# ------------------------------------------------------------------------------

def _func_marry():
    def _apply(player):
        if player.married:
            return []
        player.married = True
        return ["你结婚了，从此有了一个家。"]
    return _apply


def _func_child():
    def _apply(player):
        player.children += 1
        return ["家里迎来了第 %d 个孩子。" % player.children]
    return _apply


_ev("love_meet", "邂逅", "情感", 16,
    ["在朋友的聚会上，你遇到了一个让你心跳加速的人。",
     "地铁上有人帮你捡起掉落的书，抬头时你们对视了一秒。"],
    [_choice("主动要联系方式", "勇敢一点", "d20", [
        _out(1, 6, "你紧张得说错了话，对方礼貌地走开了。", {"happy": -5}, "bad"),
        _out(7, 17, "你们聊得很投机，约好了下次见面。", {"happy": +14}, "good"),
        _out(18, 20, "你遇见了灵魂伴侣，感情迅速升温。", {"happy": +22}, "good"),
    ]),
     _choice("把心动留在心里", "安全但平淡", "d6", [
        _out(1, 3, "你后悔了很久，总觉得错过了什么。", {"happy": -4}, "bad"),
        _out(4, 6, "你很快就把这件事忘了。", {}, "neutral"),
    ])],
    tone="good", tags=["love"], cond=lambda p: p.age >= 16)

_ev("love_fall", "恋爱", "情感", 14,
    ["你们开始频繁约会，街边的每一家店都留下了你们的影子。",
     "对方在深夜发来一条消息：「我们在一起吧。」"],
    [_choice("认真投入这段感情", "全心付出", "d10", [
        _out(1, 3, "你付出太多，反而让对方感到压力。", {"happy": -6, "money": -800}, "bad"),
        _out(4, 9, "恋爱让你整个人都亮了起来。", {"happy": +18, "money": -600}, "good"),
        _out(10, 10, "你们认定彼此就是那个人。", {"happy": +26, "money": -400}, "good"),
    ]),
     _choice("保持距离观察", "理性派", "d6", [
        _out(1, 3, "对方觉得你不够真诚，选择了离开。", {"happy": -8}, "bad"),
        _out(4, 6, "你们以朋友的身份继续相处。", {"happy": +3}, "neutral"),
    ])],
    tone="good", tags=["love"], cond=lambda p: p.age >= 16 and not p.married)

_ev("love_breakup", "分手", "情感", 10,
    ["争吵越来越多，你们终于坐在了咖啡馆里谈「结束」。",
     "对方的手机里出现了别人的名字，你选择了摊牌。"],
    [_choice("平静地放手", "及时止损", "d6", [
        _out(1, 3, "你还是难过了很久。", {"happy": -14}, "bad"),
        _out(4, 6, "分开之后你反而轻松了。", {"happy": -4}, "neutral"),
    ]),
     _choice("努力挽回", "再试一次", "d20", [
        _out(1, 10, "挽回失败，还消耗了最后的体面。", {"happy": -18, "money": -500}, "bad"),
        _out(11, 20, "你们重新开始，感情比以前更好。", {"happy": +10}, "good"),
    ])],
    tone="bad", tags=["love"], cond=lambda p: p.age >= 16 and not p.married)

_ev("love_marriage", "结婚", "情感", 12,
    ["双方父母见了面，婚期被提上了日程。",
     "你们决定领证，把这段关系变成一辈子的事。"],
    [_choice("办一场体面的婚礼", "花钱买仪式感", "d6", [
        _out(1, 3, "预算超支，为钱吵了一架。", {"money": -12000, "happy": +8}, "neutral"),
        _out(4, 6, "婚礼圆满，亲友都为你高兴。", {"money": -8000, "happy": +22, "func": _func_marry()}, "good"),
    ]),
     _choice("简单领证旅行结婚", "省钱实惠", "d6", [
        _out(1, 6, "两个人在海边拍了照，幸福很简单。", {"money": -2000, "happy": +16, "func": _func_marry()}, "good"),
    ])],
    tone="good", tags=["love"], cond=lambda p: p.age >= 22 and not p.married)

_ev("love_child", "迎接新生命", "情感", 12,
    ["检查报告显示：家里要多一个小成员了。",
     "产房外你来回踱步，直到听到那声响亮的啼哭。"],
    [_choice("迎接孩子的到来", "人生新阶段", "d10", [
        _out(1, 3, "养育的辛苦远超想象，你几乎没睡过整觉。", {"money": -6000, "happy": +10, "health": -4, "func": _func_child()}, "neutral"),
        _out(4, 10, "抱着孩子的那一刻，你觉得一切都值得。", {"money": -5000, "happy": +24, "func": _func_child()}, "good"),
    ])],
    tone="good", tags=["family"],
    cond=lambda p: p.married and 22 <= p.age <= 50 and p.children < 3)

_ev("love_friend_gather", "朋友聚会", "情感", 16,
    ["老同学组了个局，微信群里热闹了一整天。",
     "几个好朋友约你撸串，说好久没见了。"],
    [_choice("赴约叙旧", "花点钱换快乐", "d6", [
        _out(1, 3, "酒喝多了，第二天头疼欲裂。", {"money": -300, "happy": +6, "health": -3}, "neutral"),
        _out(4, 6, "聊到深夜，心里的郁结都散了。", {"money": -200, "happy": +12}, "good"),
    ]),
     _choice("在家休息", "省钱省力", "d4", [
        _out(1, 4, "你在家看了部老电影，也挺好。", {"happy": +3, "health": +1}, "good"),
    ])],
    tone="good", tags=["social"])

_ev("love_quarrel", "和亲近的人吵架", "情感", 12,
    ["一句话没说好，你和最亲近的人吵得面红耳赤。",
     "积压的情绪终于爆发，家里气氛降到了冰点。"],
    [_choice("主动道歉和解", "放下面子", "d6", [
        _out(1, 3, "对方还在气头上，道歉没被接受。", {"happy": -6}, "bad"),
        _out(4, 6, "你们抱在一起，把话说开了。", {"happy": +8}, "good"),
    ]),
     _choice("冷战到底", "谁也不低头", "d10", [
        _out(1, 5, "冷战持续了很久，关系出现裂痕。", {"happy": -14, "health": -3}, "bad"),
        _out(6, 10, "时间冲淡了怒气，日子照旧。", {"happy": -4}, "neutral"),
    ])],
    tone="bad", tags=["social"], cond=lambda p: p.age >= 6)

_ev("love_help_stranger", "帮助陌生人", "情感", 14,
    ["路口有位老人摔倒，围观的人都不敢上前。",
     "有人在地铁里急得直哭，说是钱包和证件全丢了。"],
    [_choice("伸出援手", "善意可能被辜负，也可能被回报", "d10", [
        _out(1, 3, "你被误会成肇事者，费了好大劲才说清。", {"happy": -10, "money": -300}, "bad"),
        _out(4, 9, "对方连声道谢，你心里暖暖的。", {"happy": +12}, "good"),
        _out(10, 10, "受助者恰是某公司高管，后来给了你一份大礼。", {"happy": +16, "money": +5000}, "good"),
    ]),
     _choice("拍视频报警后离开", "理性处理", "d6", [
        _out(1, 6, "警察及时赶到，事情妥善解决。", {"happy": +4}, "neutral"),
    ])],
    tone="good", tags=["social"])

_ev("love_gift", "送礼", "情感", 10,
    ["爸妈的生日快到了，你想买点像样的礼物。",
     "朋友帮了你一个大忙，你觉得该表示一下。"],
    [_choice("买份贵重礼物", "心意到位", "d6", [
        _out(1, 6, "对方收到礼物时眼睛都亮了。", {"money": -1200, "happy": +12}, "good"),
    ]),
     _choice("手写一封信", "用心不花钱", "d6", [
        _out(1, 3, "对方觉得你有点敷衍。", {"happy": -3}, "bad"),
        _out(4, 6, "朴实的话语让对方红了眼眶。", {"happy": +9}, "good"),
    ])],
    tone="good", tags=["social"], cond=lambda p: p.age >= 12)


# ------------------------------------------------------------------------------
# 8.4 环境气候类事件
# ------------------------------------------------------------------------------

_ev("env_cold_wave", "寒潮来袭", "环境", 18,
    ["气象台发布寒潮蓝色预警，气温一夜之间掉了十几度。",
     "寒风呼啸，路上的行人都缩着脖子快步走。"],
    [_choice("添置厚衣、开足暖气", "花钱保暖", "d6", [
        _out(1, 4, "穿得严严实实，寒潮对你影响不大。", {"money": -500, "temp": -0.1}, "good"),
        _out(5, 6, "暖气坏了，夜里还是冻得发抖。", {"money": -500, "temp": -0.6, "health": -2}, "neutral"),
    ]),
     _choice("硬扛过去", "省下开销，身体受罪", "d10", [
        _out(1, 4, "你在寒风里冻得嘴唇发紫。", {"temp": -1.2, "happy": -4}, "bad"),
        _out(5, 8, "多穿了两件旧衣服，勉强撑住。", {"temp": -0.5}, "neutral"),
        _out(9, 10, "你的抗寒能力出乎意料地强。", {"happy": +3}, "good"),
    ])],
    tone="bad", tags=["env"], cond=lambda p: p.ambient_temp <= 12 or get_city(p.city)["tag"] == "寒冷")

_ev("env_heat_wave", "高温预警", "环境", 18,
    ["连续三天最高气温超过 38℃，空调外机嗡嗡作响。",
     "柏油路被晒得发软，新闻里反复提醒减少外出。"],
    [_choice("开空调宅在家", "电费换舒适", "d6", [
        _out(1, 6, "屋里凉爽，你安稳地度过了热浪。", {"money": -400, "temp": +0.1}, "good"),
    ]),
     _choice("照常出门办事", "硬碰高温", "d10", [
        _out(1, 4, "你在烈日下头晕目眩。", {"temp": +1.1, "happy": -4}, "bad"),
        _out(5, 8, "你躲进商场蹭了空调，问题不大。", {"temp": +0.3}, "neutral"),
        _out(9, 10, "傍晚出门，居然赶上了难得的凉风。", {"happy": +3}, "good"),
    ])],
    tone="bad", tags=["env"], cond=lambda p: p.ambient_temp >= 24 or get_city(p.city)["tag"] == "炎热")

_ev("env_rain", "暴雨", "环境", 14,
    ["暴雨如注，路面很快积起了水。",
     "雨点砸在窗户上啪啪作响，出门成了难题。"],
    [_choice("打车通勤", "花钱买干爽", "d6", [
        _out(1, 3, "堵在路上两个小时，还是湿了鞋。", {"money": -200, "happy": -4}, "bad"),
        _out(4, 6, "顺利抵达，衣服一点没湿。", {"money": -150, "happy": +1}, "good"),
    ]),
     _choice("冒雨出行", "省钱但狼狈", "d10", [
        _out(1, 3, "你淋成了落汤鸡，第二天开始打喷嚏。", {"temp": -0.4, "happy": -4, "health": -2}, "bad"),
        _out(4, 10, "一把伞走天下，居然没怎么淋到。", {"happy": +1}, "neutral"),
    ])],
    tone="neutral", tags=["env"])

_ev("env_haze", "雾霾天", "环境", 12,
    ["窗外一片灰黄，能见度不足两百米。",
     "空气质量指数爆表，口罩成了出门必备。"],
    [_choice("买口罩和净化器", "保护呼吸道", "d6", [
        _out(1, 6, "呼吸顺畅，雾霾对你影响很小。", {"money": -600, "health": +1}, "good"),
    ]),
     _choice("将就一下", "省钱的代价", "d10", [
        _out(1, 4, "你咳了整整一周，喉咙发炎。", {"health": -5, "happy": -3}, "bad"),
        _out(5, 10, "只是嗓子有点干，没什么大碍。", {"health": -1}, "neutral"),
    ])],
    tone="bad", tags=["env"])

_ev("env_blizzard", "暴雪封路", "环境", 10,
    ["一夜暴雪，小区门口的车全被埋了。",
     "公交停运、航班取消，城市几乎停摆。"],
    [_choice("囤好物资在家办公", "稳妥应对", "d6", [
        _out(1, 6, "你提前囤了菜，安稳地过了两天。", {"money": -300, "happy": +2, "temp": -0.2}, "good"),
    ]),
     _choice("冒险出门", "危险系数高", "d10", [
        _out(1, 4, "你在雪地里滑倒，扭伤了脚踝。", {"health": -8, "happy": -6, "temp": -0.8}, "bad"),
        _out(5, 10, "你小心翼翼地走完了全程。", {"temp": -0.4, "happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["env"], cond=lambda p: get_city(p.city)["tag"] == "寒冷" or p.ambient_temp <= 0)

_ev("env_sandstorm", "沙尘暴", "环境", 10,
    ["天空变成土黄色，风里全是沙粒。",
     "沙尘暴过境，出门五分钟嘴里都是土。"],
    [_choice("关窗戴口罩", "防护到位", "d6", [
        _out(1, 6, "你安然度过了沙尘天。", {"money": -200, "health": -1}, "good"),
    ]),
     _choice("照常外出", "沙尘直冲口鼻", "d10", [
        _out(1, 4, "你的眼睛和喉咙都被刺激得通红。", {"health": -5, "happy": -4}, "bad"),
        _out(5, 10, "回来后洗了把脸就没事了。", {"health": -1}, "neutral"),
    ])],
    tone="bad", tags=["env"],
    cond=lambda p: p.city in ("harbin", "beijing") and p.month in (3, 4, 5))

_ev("env_heatstroke_risk", "闷热难耐", "环境", 8,
    ["梅雨天湿度接近饱和，走两步就一身汗。",
     "夜里闷热得睡不着，空调开了又怕感冒。"],
    [_choice("买个除湿机", "改善环境", "d4", [
        _out(1, 4, "屋里清爽多了，睡眠质量明显提升。", {"money": -900, "happy": +6, "health": +1}, "good"),
    ]),
     _choice("忍着", "省钱", "d6", [
        _out(1, 3, "你整夜没睡好，白天昏昏沉沉。", {"happy": -5, "health": -3}, "bad"),
        _out(4, 6, "身体慢慢适应了这种天气。", {}, "neutral"),
    ])],
    tone="neutral", tags=["env"], cond=lambda p: p.city in ("shanghai", "guangzhou"))


# ------------------------------------------------------------------------------
# 8.5 随机意外类事件
# ------------------------------------------------------------------------------

_ev("rand_lottery", "买彩票", "意外", 14,
    ["路过彩票店，你鬼使神差地买了两注。",
     "朋友凑钱合买刮刮乐，硬塞给你一张。"],
    [_choice("试试运气", "小赌怡情", "d100", [
        _out(1, 60, "什么都没中，彩票成了书签。", {"money": -50}, "neutral"),
        _out(61, 95, "中了个小奖，够吃顿好的。", {"money": +500, "happy": +8}, "good"),
        _out(96, 99, "中了大奖，你反复确认了三遍号码。", {"money": +20000, "happy": +25}, "good"),
        _out(100, 100, "【隐藏·天降横财】你中了大奖，金额高到需要去省城领奖。", {"money": +80000, "happy": +30}, "good"),
    ]),
     _choice("不参与", "踏实过日子", "d4", [
        _out(1, 4, "你觉得钱还是攥在手里最实在。", {"happy": +2}, "neutral"),
    ])],
    tone="neutral", tags=["random"])

_ev("rand_lose_money", "丢钱", "意外", 16,
    ["手机不见了，你翻遍了所有口袋。",
     "钱包被划开一道口子，现金全没了。"],
    [_choice("报警并挂失", "减少损失", "d6", [
        _out(1, 3, "追回来的希望渺茫，你只能自认倒霉。", {"money": -1500, "happy": -8}, "bad"),
        _out(4, 6, "警察很快找回了丢失的物品。", {"happy": +4}, "good"),
    ]),
     _choice("算了，破财免灾", "心态放平", "d6", [
        _out(1, 6, "你安慰自己：钱没了可以再赚。", {"money": -1200, "happy": -3}, "neutral"),
    ])],
    tone="bad", tags=["random"])

_ev("rand_injury", "意外受伤", "意外", 14,
    ["下楼梯时一脚踩空，脚踝传来剧痛。",
     "搬东西时腰闪了一下，直都直不起来。"],
    [_choice("立刻去医院", "规范治疗", "d6", [
        _out(1, 3, "医生说需要静养两周，医药费不便宜。", {"money": -1200, "health": -6, "happy": -4}, "neutral"),
        _out(4, 6, "只是软组织挫伤，包扎后就回家了。", {"money": -300, "health": -3}, "neutral"),
    ]),
     _choice("自己贴膏药", "能省则省", "d10", [
        _out(1, 4, "没处理好，落下了老毛病。", {"health": -10, "happy": -6}, "bad"),
        _out(5, 10, "休息几天就好了。", {"health": -4, "happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["random"])

_ev("rand_adventure", "奇遇", "意外", 10,
    ["你在旧书摊上淘到一本泛黄的手稿，里面写满了奇怪的符号。",
     "深夜加班回家，你在天桥上遇到一个自称会算命的老先生。"],
    [_choice("认真研究 / 听他说完", "可能改变人生", "d20", [
        _out(1, 7, "对方只是想骗点钱，你损失了一笔。", {"money": -600, "happy": -6}, "bad"),
        _out(8, 17, "你从中得到灵感，做出了一个不错的副业产品。", {"money": +3000, "happy": +10}, "good"),
        _out(18, 20, "手稿里夹着一张旧邮票，鉴定后价值不菲。", {"money": +30000, "happy": +18}, "good"),
    ]),
     _choice("一笑而过", "不理会", "d6", [
        _out(1, 6, "你继续过自己的日子。", {"happy": +1}, "neutral"),
    ])],
    tone="neutral", tags=["random"])

_ev("rand_gift", "意外之财", "意外", 10,
    ["大学同学突然转来一笔钱，说是当年借的。",
     "公司年会上你被抽中了一台新手机。"],
    [_choice("欣然接受", "好事成双", "d6", [
        _out(1, 6, "这笔意外收入让你心情大好。", {"money": +2000, "happy": +10}, "good"),
    ])],
    tone="good", tags=["random"])

_ev("rand_car_accident", "交通事故", "意外", 8,
    ["过马路时一辆电动车擦着你飞驰而过。",
     "前方车辆急刹，你差一点就撞了上去。"],
    [_choice("立刻检查伤情", "谨慎为上", "d6", [
        _out(1, 3, "你被撞倒在地，膝盖擦破了很大一片。", {"money": -800, "health": -8, "happy": -6}, "bad"),
        _out(4, 6, "只是虚惊一场，衣服蹭脏了。", {"happy": -4}, "neutral"),
    ]),
     _choice("自认倒霉继续走", "懒得纠缠", "d10", [
        _out(1, 4, "伤情比想象中严重，后来还是去了医院。", {"money": -1500, "health": -6}, "bad"),
        _out(5, 10, "确实没什么事，你快步离开了现场。", {"happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["random"], cond=lambda p: p.age >= 6)

_ev("rand_found_money", "捡到钱包", "意外", 10,
    ["路边有个鼓鼓的钱包，四下无人。",
     "自动取款机吐出一张没人认领的钞票。"],
    [_choice("交给警察", "心安理得", "d6", [
        _out(1, 5, "失主赶来时对你千恩万谢。", {"happy": +12}, "good"),
        _out(6, 6, "失主是本地企业家，硬塞给你一笔谢礼。", {"money": +3000, "happy": +14}, "good"),
    ]),
     _choice("据为己有", "良心不安", "d10", [
        _out(1, 3, "钱包主人的朋友正好看到，你被当场抓住。", {"money": -2000, "happy": -18}, "bad"),
        _out(4, 10, "你把钱花了，但心里一直不舒服。", {"money": +1500, "happy": -6}, "neutral"),
    ])],
    tone="neutral", tags=["random"])


# ------------------------------------------------------------------------------
# 8.6 隐藏特殊事件（极端骰点触发）
# ------------------------------------------------------------------------------

_ev("secret_special_100", "天命所归", "隐藏", 0,
    ["骰子掷出满值 100——命运的齿轮发出清脆的响声。",
     "你从未想过，随手的善举会引来如此巨大的回响。"],
    [_choice("接受这份馈赠", "骰神站在你这边", "d20", [
        _out(1, 4, "一份神秘遗产落到你手里。", {"money": +50000, "happy": +20}, "good"),
        _out(5, 12, "你被贵人提携，事业一步登天。", {"money": +30000, "happy": +22, "func": _func_promote(2)}, "good"),
        _out(13, 20, "你的人生从此开挂：财富、健康、幸福全面爆发。", {"money": +88888, "health": +30, "happy": +30, "func": _func_promote(3)}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_disaster_1", "天崩开局", "隐藏", 0,
    ["骰子掷出大失败 1——今天似乎做什么都不顺。",
     "一早醒来，你就有一种说不出的不祥预感。"],
    [_choice("稳住心态，减少损失", "灾祸中保住底线", "d20", [
        _out(1, 6, "你被连环霉运击中，钱财与健康双双受损。", {"money": -5000, "health": -18, "happy": -16, "temp": +0.8}, "bad"),
        _out(7, 14, "虽然损失不小，但你及时止损了。", {"money": -2000, "health": -8, "happy": -8, "temp": +0.4}, "bad"),
        _out(15, 20, "你靠着冷静与一点运气，只擦破了皮。", {"money": -500, "health": -3, "happy": -3}, "neutral"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_lucky_99", "一线生机", "隐藏", 0,
    ["骰子掷出 99——在最绝望的地方，你看见了一道光。"],
    [_choice("抓住它", "绝境翻盘", "d20", [
        _out(1, 10, "你抓住了机会，境况明显好转。", {"money": +8000, "happy": +14, "health": +10}, "good"),
        _out(11, 20, "这不仅是一次转机，而是人生的分水岭。", {"money": +30000, "happy": +20, "health": +20}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_omen_2", "劫数初现", "隐藏", 0,
    ["骰子掷出 2——冥冥之中，阴影正在靠近。"],
    [_choice("提前防备", "是否能避开？", "d20", [
        _out(1, 8, "预警毫无作用，厄运还是降临了。", {"money": -3000, "health": -10, "happy": -10}, "bad"),
        _out(9, 20, "你提前做了准备，把损失降到了最低。", {"money": -300, "happy": -2}, "neutral"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_windfall_d20", "大成功", "隐藏", 0,
    ["d20 掷出 20——你从未想过事情能顺利到这种程度。"],
    [_choice("乘胜追击", "机会难得", "d6", [
        _out(1, 6, "你把这份好运扩大了三倍。", {"money": +12000, "happy": +18, "health": +8}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_catastrophe_d20", "大失败", "隐藏", 0,
    ["d20 掷出 1——所有糟糕的可能性同时发生了。"],
    [_choice("咬牙承受", "活着就有希望", "d6", [
        _out(1, 6, "你损失惨重，但还没到绝境。", {"money": -4000, "health": -12, "happy": -12, "temp": +0.5}, "bad"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_birthday", "生日", "隐藏", 0,
    ["今天是你的生日，朋友圈里刷满了祝福。",
     "手机一早就开始响，都是记得你生日的朋友。"],
    [_choice("好好庆祝一下", "一年只有一次", "d6", [
        _out(1, 3, "你请自己吃了顿大餐。", {"money": -600, "happy": +12}, "good"),
        _out(4, 6, "亲友们凑在一起为你庆生，你收到了很多礼物。", {"money": +300, "happy": +18, "health": +3}, "good"),
    ]),
     _choice("安静地度过", "平淡也是幸福", "d4", [
        _out(1, 4, "你给自己写了一封信，回顾这一年。", {"happy": +8}, "good"),
    ])],
    tone="secret", special=True, tags=["secret", "birthday"])

_ev("secret_milestone", "人生里程碑", "隐藏", 0,
    ["回望这一年，你发现自己已经走了很远。"],
    [_choice("记录下来", "为人生留个纪念", "d6", [
        _out(1, 6, "你为自己的人生写下了一页总结。", {"happy": +6}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])


# ------------------------------------------------------------------------------
# 8.7 事件抽取逻辑
# ------------------------------------------------------------------------------
# 事件概率采用**万分之一**精度（d10000）：
#   1) 先用 d10000 判定"今天是否发生值得记录的事件"（各人生阶段概率不同）
#   2) 再用 d10000 在允许的大类里按权重抽取
# 这样事件不再天天发生（例如幼儿园阶段约 7% 的日子有事，工作期约 16%）。
# ------------------------------------------------------------------------------

#: 隐藏事件触发条件：骰面 -> 事件id
SECRET_BY_D100 = {
    100: "secret_special_100",
    99: "secret_lucky_99",
    2: "secret_omen_2",
    1: "secret_disaster_1",
}
SECRET_BY_D20 = {20: "secret_windfall_d20", 1: "secret_catastrophe_d20"}

#: 大类抽取权重（万分位，总和 10000）——「日常」占比最高，避免天天跌宕起伏
CATEGORY_BANDS = [
    ("日常", 1, 3800),
    ("疾病", 3801, 5400),
    ("工作", 5401, 6800),
    ("情感", 6801, 8400),
    ("环境", 8401, 9200),
    ("意外", 9201, 10000),
]

#: 旧接口兼容：百分位区间（供外部工具/测试引用）
CATEGORY_BANDS_PERCENT = [
    ("日常", 1, 38),
    ("疾病", 39, 54),
    ("工作", 55, 68),
    ("情感", 69, 84),
    ("环境", 85, 92),
    ("意外", 93, 100),
]

#: 全部大类名称（含"日常/隐藏/综合"，用于冷却记录与展示）
CATEGORY_BANDS_NAMES = tuple([name for name, _l, _h in CATEGORY_BANDS]
                             + ["隐藏", "综合"])

#: 按人生阶段划分可触发的事件大类（孩子不会遇到职场与婚恋事件）
STAGE_CATEGORY_RULES = {
    "infant":       ("日常", "疾病", "情感"),
    "preschool":    ("日常", "疾病", "情感", "环境"),
    "kindergarten": ("日常", "疾病", "情感", "环境"),
    "primary":      ("日常", "疾病", "情感", "环境", "意外"),
    "middle":       ("日常", "疾病", "情感", "环境", "意外"),
    "zhongkao":     ("日常", "疾病", "情感", "环境", "意外"),
    "high":         ("日常", "疾病", "情感", "环境", "意外"),
    "gaokao":       ("日常", "疾病", "情感", "环境"),
    "university":   ("日常", "疾病", "情感", "环境", "意外", "工作"),
    "postgrad":     ("日常", "疾病", "情感", "环境", "意外", "工作"),
    "work":         ("日常", "疾病", "工作", "情感", "环境", "意外"),
    "retired":      ("日常", "疾病", "情感", "环境", "意外"),
    "dropout":      ("日常", "疾病", "工作", "情感", "环境", "意外"),
    "jobless":      ("日常", "疾病", "工作", "情感", "环境", "意外"),
}

#: 按年龄的兜底规则（当阶段信息缺失时使用）
AGE_CATEGORY_RULES = [
    (3, ("日常", "疾病", "情感")),
    (6, ("日常", "疾病", "情感", "环境")),
    (12, ("日常", "疾病", "情感", "环境", "意外")),
    (16, ("日常", "疾病", "情感", "环境", "意外")),
    (22, ("日常", "疾病", "情感", "环境", "意外")),
    (60, ("日常", "疾病", "工作", "情感", "环境", "意外")),
    (200, ("日常", "疾病", "情感", "环境", "意外")),
]


def categories_for_stage(stage_id, age=None):
    """返回该人生阶段允许触发的事件大类集合。"""
    rules = STAGE_CATEGORY_RULES.get(stage_id)
    if rules:
        return set(rules)
    return categories_for_age(age if age is not None else 0)


def categories_for_age(age):
    """返回该年龄允许触发的事件大类集合（兜底）。"""
    for limit, categories in AGE_CATEGORY_RULES:
        if age <= limit:
            return set(categories)
    return {name for name, _l, _h in CATEGORY_BANDS}


def category_from_roll(value):
    """根据 d10000 点数决定事件大类。"""
    for name, low, high in CATEGORY_BANDS:
        if low <= value <= high:
            return name
    return "意外"


def event_allowed_today(player, event, category, engine=None):
    """
    事件过滤：除"阶段允许"外，还做现实性校验与同类冷却：
      * 幼年（<6 岁）的"出门 / 通勤 / 独自行动"类事件必须由父母带领
      * 同一大类事件在 EVENT_CATEGORY_COOLDOWN_DAYS 天内不重复
      * 疾病类事件还要满足生病间隔（由引擎负责）
    """
    tags = set(event.get("tags") or [])

    # 1) 幼年出门限制：需要父母陪同
    if player.age < 6 and ("outdoor" in tags or "commute" in tags):
        if not event.get("with_parents", False):
            return False

    # 2) 上学/工作在读阶段才有的校园、职场类事件
    if "school" in tags and getattr(player, "age", 0) < 5:
        return False

    # 3) 同类事件冷却
    if engine is not None:
        last_days = getattr(engine, "category_last_day", {}) or {}
        last = last_days.get(category)
        if last is not None and (player.total_days - last) < EVENT_CATEGORY_COOLDOWN_DAYS:
            return False
    return True


def available_events(category, player, allow_special=False, engine=None):
    """筛选当前条件下可触发的普通事件。"""
    result = []
    for eid in EVENT_ORDER:
        ev = EVENTS[eid]
        if ev["category"] != category:
            continue
        if ev["special"] and not allow_special:
            continue
        if ev["weight"] <= 0:
            continue
        try:
            if not ev["cond"](player):
                continue
        except Exception:
            continue
        if not event_allowed_today(player, ev, category, engine):
            continue
        result.append(ev)
    return result


def pick_event_weighted(dice, candidates, tag="事件抽取"):
    """
    加权抽取事件（万分位精度），返回 (事件, DiceResult)。
    """
    if not candidates:
        return None, dice.roll(10000, 1, 0, tag)
    res = dice.roll(10000, 1, 0, tag)
    total = float(sum(max(0.0, ev["weight"]) for ev in candidates)) or 1.0
    target = (res.value - 0.5) / 10000.0 * total
    acc = 0.0
    for ev in candidates:
        acc += max(0.0, ev["weight"])
        if target <= acc:
            return ev, res
    return candidates[-1], res


def roll_daily_event(dice, player, engine=None):
    """
    每日事件抽签主入口（万分位精度）。
    返回 dict：
        {"event": 事件或None, "category": 大类, "roll": DiceResult,
         "secret_reason": 隐藏触发说明 或 None, "internal": 事件id,
         "no_event": True/False}
    抽签规则：
        1. 先掷 d10000 判定"今天是否发生值得记录的事件"
           （各阶段概率在 EVENT_CHANCE_D10000 中配置，如幼儿园 700/10000 = 7%）
        2. 事件日再掷 d100 决定大类（极端点数 100/99/2/1 触发隐藏剧情）
        3. 大类受人生阶段限制（孩子不会遇到职场与婚恋事件）
        4. 最后用 d10000 在对应大类里按权重抽具体事件
    """
    # ---- 第一步：今天有没有事 ----
    chance_roll = dice.roll(10000, 1, 0, "事件发生判定")
    chance = event_chance_of(player)
    dice.remember(chance_roll, "事件发生判定（万分位）")
    if chance_roll.value > max(1.0, chance * 10000.0):
        return {"event": None, "category": "日常", "roll": chance_roll,
                "secret_reason": None, "internal": "", "no_event": True,
                "chance": chance}

    # ---- 第二步：事件大类 + 隐藏剧情 ----
    roll = dice.d100("事件大类判定")
    dice.remember(roll, "事件大类")
    secret_reason = roll.hidden
    if roll.value in SECRET_BY_D100 and not roll.flat:
        eid = SECRET_BY_D100[roll.value]
        return {"event": EVENTS[eid], "category": "隐藏", "roll": roll,
                "secret_reason": secret_reason, "internal": eid, "no_event": False,
                "chance": chance}

    allowed = categories_for_stage(getattr(player, "stage", None), getattr(player, "age", 0))
    category = category_from_roll(roll.value * 100) if False else category_from_d100(roll.value)
    if category not in allowed:
        ordered = [name for name, _l, _h in CATEGORY_BANDS if name in allowed]
        if not ordered:
            ordered = [name for name, _l, _h in CATEGORY_BANDS]
        reroll = dice.d100("阶段事件重抽")
        dice.remember(reroll, "阶段事件重抽")
        category = ordered[(reroll.value - 1) % len(ordered)]

    candidates = available_events(category, player, engine=engine)
    if not candidates:
        for name in sorted(allowed):
            candidates.extend(available_events(name, player, engine=engine))
        category = "综合"
    if not candidates:
        return {"event": None, "category": category, "roll": roll,
                "secret_reason": secret_reason, "internal": "", "no_event": True,
                "chance": chance}
    event, pick_roll = pick_event_weighted(dice, candidates, "%s事件挑选" % category)
    dice.remember(pick_roll, "%s事件挑选" % category)
    return {"event": event, "category": category, "roll": roll,
            "secret_reason": secret_reason, "internal": event["id"] if event else "",
            "no_event": False, "chance": chance}


def category_from_d100(value):
    """把 d100 结果映射到万分位大类区间（保持与 CATEGORY_BANDS 一致）。"""
    scaled = value * 100
    if scaled > 10000:
        scaled = 10000
    return category_from_roll(scaled)



def resolve_outcome(dice, choice):
    """
    根据选项掷骰并匹配结果区间，返回 (outcome, DiceResult)。
    区间写法 "d6" / "2d6" / "d100"；区间不覆盖时取最接近的一个。
    """
    res = dice.roll_notation(choice.get("roll", "d6"), "结果判定")
    outcomes = choice.get("outcomes") or []
    if not outcomes:
        return _out(0, 999, "什么也没有发生。"), res
    for out in outcomes:
        lo, hi = out["range"]
        if lo <= res.value <= hi:
            return out, res
    # 越界兜底：取区间距离最近的结果
    best = outcomes[0]
    best_dist = None
    for out in outcomes:
        lo, hi = out["range"]
        dist = 0 if lo <= res.value <= hi else min(abs(res.value - lo), abs(res.value - hi))
        if best_dist is None or dist < best_dist:
            best, best_dist = out, dist
    return best, res
