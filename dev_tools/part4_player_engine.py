

# ==============================================================================
# 9. 人物（玩家）状态
# ==============================================================================

SAVE_VERSION = 1


class Player:
    """
    人物对象：保存四项核心属性、时间、城市、疾病与人生记录。
    所有属性变更都通过 apply_effects 统一处理，保证边界约束与死亡判定一致。
    """

    def __init__(self, name="无名氏", city="beijing", rng=None):
        self.name = (name or "无名氏").strip()[:12] or "无名氏"
        self.city = city if city in CITIES else "beijing"

        # ---- 四项核心属性 ----
        self.health = float(INIT_HEALTH)     # 健康 0~100，归零死亡
        self.happy = float(INIT_HAPPY)       # 幸福 0~100
        self.money = float(INIT_MONEY)       # 金钱，可负债
        self.temp = float(INIT_TEMP)         # 体温，正常 36.0~37.0

        # ---- 开局随机固定参数：体质 / 家境 ----
        _rng = rng or random.Random()
        self.constitution = round(_rng.gauss(CONSTITUTION_MEAN, CONSTITUTION_SD), 1)
        self.constitution = max(CONSTITUTION_MIN, min(CONSTITUTION_MAX, self.constitution))
        self.family_wealth = round(_rng.gauss(FAMILY_WEALTH_MEAN, FAMILY_WEALTH_SD), 1)
        self.family_wealth = max(FAMILY_WEALTH_MIN, min(FAMILY_WEALTH_MAX, self.family_wealth))
        self.family_bankrupt = False         # 家庭是否破产（破产后不再提供支持）
        self.left_home = False               # 是否已离家独立（不再接受家庭支持）
        self.family_notes = []               # 家庭相关记录

        # ---- 时间 ----
        self.age = INIT_AGE                  # 年龄（岁）
        self.year = 1                        # 第几年（从 1 开始）
        self.month = 1                       # 1~12
        self.day = 1                         # 1~30
        self.total_days = 0                  # 已度过天数
        self.birth_month = 1                 # 生日（月）
        self.birth_day = 1                   # 生日（日）

        # ---- 人生阶段与学业 ----
        self.stage = "infant"                # 当前人生阶段 id
        self.stage_history = []              # 阶段变化记录
        self.education = []                  # 学历记录（幼儿园/小学/初中/高中/大学/研究生）
        self.exam_results = {}               # 考试成绩（中考/高考/考研）
        self.university_ok = None            # 是否考上大学
        self.postgrad_ok = None              # 是否考上研究生

        # ---- 行动点（游戏内同一天最多 8 次操作）----
        self.action_points = ACTION_POINTS_PER_DAY
        self.actions_today = 0
        self.action_tally = {}               # 当天各类操作次数（用于收益衰减）
        self.days_played = 0                 # 已经历的游戏内天数

        # ---- 状态 ----
        self.diseases = []                   # 活动疾病列表
        self.employed = False                # 是否在职
        self.job_level = 0                   # 职级（影响工资）
        self.married = False                 # 已婚
        self.children = 0                    # 子女数量
        self.carried_effects = []            # 跨天持续效果
        self.milestones = []                 # 人生大事记
        self.event_history = []              # 已触发事件记录
        self.last_illness_day = None         # 上次生病的天数（用于生病间隔）
        self.plain_days = 0                  # 平凡的一天计数
        self.illness_count = 0               # 累计生病次数
        self.stats = {                       # 统计信息
            "days_worked": 0, "days_rested": 0, "days_played": 0,
            "total_income": 0.0, "total_expense": 0.0,
            "disease_count": 0, "cure_count": 0, "max_money": float(INIT_MONEY),
            "rest_streak": 0, "low_health_days": 0, "hospital_count": 0,
            "family_support_total": 0.0, "actions_total": 0, "skipped_days": 0,
            "study_points": 0, "debt": 0.0,
        }
        self.dead = False
        self.death_reason = ""
        self.death_date = ""
        self.summary_done = False

        self.ambient_temp = 15.0             # 当日气温（引擎写入）
        self.rng = rng or random.Random()    # 独立随机源（用于环境温度存盘一致性）

    # ------------------------------------------------------------------
    # 属性读写
    # ------------------------------------------------------------------
    @property
    def date_text(self):
        return "%d 年 %d 月 %d 日" % (self.year, self.month, self.day)

    @property
    def date_full(self):
        return "%d 岁 · %d 年 %d 月 %d 日" % (self.age, self.year, self.month, self.day)

    @property
    def life_stage(self):
        """根据年龄返回人生阶段描述。"""
        a = self.age
        if a <= 3:
            return "婴幼儿"
        if a <= 6:
            return "学龄前"
        if a <= 12:
            return "小学生"
        if a <= 15:
            return "初中生"
        if a <= 18:
            return "高中生"
        if a <= 22:
            return "大学生"
        if a <= 30:
            return "青年"
        if a <= 45:
            return "壮年"
        if a <= 60:
            return "中年"
        if a <= 75:
            return "老年"
        return "高龄"

    @property
    def status_text(self):
        if self.dead:
            return "已故"
        if self.health <= 20:
            return "奄奄一息"
        if self.health <= 45:
            return "虚弱"
        if self.happy <= 20:
            return "抑郁"
        if self.temp >= 38.0:
            return "高烧"
        if self.temp <= 35.0:
            return "失温"
        if self.health >= 85 and self.happy >= 60:
            return "状态良好"
        return "尚可"

    # ------------------------------------------------------------------
    # 疾病管理
    # ------------------------------------------------------------------
    def has_disease(self, disease_id):
        return any(d["id"] == disease_id for d in self.diseases)

    def disease_names(self):
        return "、".join(d["name"] for d in self.diseases) if self.diseases else "无"

    def worst_disease(self):
        """返回最严重的活动疾病（用于界面提示）。"""
        if not self.diseases:
            return None
        return max(self.diseases, key=lambda d: DISEASE_SEVERITY.get(d["id"], 0))

    def add_disease(self, disease_id, hp_scale=1.0, temp_scale=1.0, days_bonus=0,
                    dice=None, force=False):
        """
        施加疾病。若已患同类疾病则叠加病程与强度（雪上加霜）。
          * force=False（默认）：先按 U 型年龄曲线做一次"是否真的病倒"的判定，
            未通过时返回 (None, 说明)，用于模拟"多数时候身体扛得住"。
          * force=True：必定患病（用于病情必然恶化的连锁事件）。
        返回 (疾病实例 或 None, 说明文本)。
        """
        dice = dice or DiceSystem(self.rng)
        existing = next((d for d in self.diseases if d["id"] == disease_id), None)
        if existing:
            existing["days"] += 2
            existing["total_days"] += 2
            existing["hp_per_day"] = round(existing["hp_per_day"] * 1.25, 2)
            return existing, "旧病未愈，病情加重了"
        if not force:
            # 每日患病概率（万分位精度，含体质/年龄/状态/城市）
            prob = sickness_probability(self)
            roll = dice.roll(10000, 1, 0, "患病判定")
            if roll.value > max(1.0, prob * 10000.0):
                return None, "这次身体扛住了，没有真的病倒（万分位判定 %d > %.1f）" % (
                    roll.value, prob * 10000.0)
        info = make_disease(dice, disease_id, hp_scale=hp_scale,
                            days_bonus=days_bonus, temp_scale=temp_scale)
        # 体质影响病程：体质越差，病得越久
        factor = duration_factor(self.constitution)
        if factor != 1.0:
            info["days"] = max(1, int(round(info["days"] * factor)))
            info["total_days"] = info["days"]
        self.diseases.append(info)
        self.stats["disease_count"] += 1
        self.illness_count += 1
        self.last_illness_day = self.total_days
        return info, "新患病：%s（体质 %d 分，病程 %d 天）" % (
            info["name"], int(round(self.constitution)), info["days"])

    def worsen_disease(self, disease_id=None, factor=1.3, extra_days=2):
        """让疾病恶化：每日扣血更多、持续更久（强度有上限，避免数值失控）。"""
        target = None
        if disease_id:
            target = next((d for d in self.diseases if d["id"] == disease_id), None)
        target = target or self.worst_disease()
        if not target:
            return None
        base = DISEASES.get(target["id"], {}).get("hp_per_day", target["hp_per_day"])
        cap = base * 2.0                       # 单种疾病最多恶化到基础值的 2 倍
        target["hp_per_day"] = round(min(cap, target["hp_per_day"] * factor), 2)
        target["days"] += extra_days
        target["total_days"] += extra_days
        return target

    def cure_disease(self, disease_id=None):
        """
        治愈疾病。disease_id 为空时治愈最严重的一种。
        返回 (是否成功, 说明文本, 花费)
        """
        if not self.diseases:
            return False, "你身体很健康，没有需要治疗的疾病。", 0.0
        if disease_id:
            target = next((d for d in self.diseases if d["id"] == disease_id), None)
        else:
            target = self.worst_disease()
        if not target:
            return False, "没有找到对应的疾病。", 0.0
        cost = float(target["cure_cost"])
        if self.money < cost:
            return False, "金钱不足：治疗%s需要 %.2f，你只有 %.2f。" % (
                target["name"], cost, self.money), cost
        self.money = round_money(self.money - cost)
        self.stats["total_expense"] = round_money(self.stats.get("total_expense", 0.0) + cost)
        self.diseases.remove(target)
        self.stats["cure_count"] += 1
        # 治愈后体温向正常值靠拢
        self.temp = clamp_temp(self.temp + (36.5 - self.temp) * 0.6)
        return True, "你花了 %.2f 治好了%s。" % (cost, target["name"]), cost

    # ------------------------------------------------------------------
    # 效果应用（核心）
    # ------------------------------------------------------------------
    def apply_effects(self, effects, dice=None):
        """
        应用效果字典，返回 (属性差值字典, 描述文本列表)。
        差值字典包含实际生效的 health/happy/money/temp 变化量。
        """
        dice = dice or DiceSystem(self.rng)
        effects = effects or {}
        before = {"health": self.health, "happy": self.happy,
                  "money": self.money, "temp": self.temp}
        notes = []

        # 0) 未成年保护 + 巨款缩放：
        #    未成年人由家庭抚养，收入/奖金大幅缩减；
        #    大额金钱变化再按年龄与身价做一次缩放，避免"幼儿中巨奖"这类数值崩坏。
        money_change = float(effects.get("money", 0))
        if money_change != 0:
            mult = 1.0
            if self.age < 18:
                if self.age < 6:
                    mult *= 0.15
                elif self.age < 12:
                    mult *= 0.25
                elif self.age < 16:
                    mult *= 0.35
                else:
                    mult *= 0.6
            if abs(money_change) > 3000:
                # 大额金钱：随年龄增长而放大（成年后接近全额），儿童只能拿到象征性部分
                if abs(money_change) >= 100000:
                    age_factor = max(0.02, min(1.0, 0.02 + self.age * 0.033))
                else:
                    age_factor = max(0.10, min(1.0, 0.10 + self.age * 0.030))
                # 已是富豪时大额收益递减，防止数值无限膨胀
                wealth_factor = 1.0 - 0.5 * (1.0 - 1.0 / (1.0 + max(0.0, self.money) / 400000.0))
                mult *= age_factor * wealth_factor
            if abs(mult - 1.0) > 1e-9:
                effects = dict(effects)
                effects["money"] = money_change * mult
                if money_change > 0:
                    notes.append("（实际到手按年龄/身价折算：%.0f%%）" % (mult * 100))
                else:
                    notes.append("（实际支出按年龄/身价折算：%.0f%%）" % (mult * 100))

        # 1) 直接数值
        self.health = clamp_health(self.health + float(effects.get("health", 0)))
        self.happy = clamp_happy(self.happy + float(effects.get("happy", 0)))
        self.money = round_money(self.money + float(effects.get("money", 0)))
        if "temp" in effects:
            self.temp = clamp_temp(self.temp + float(effects["temp"]))

        # 2) 回复类（受上限限制，不会超过 100）
        if effects.get("health_boost"):
            boost = float(effects["health_boost"])
            self.health = clamp_health(min(HEALTH_MAX, self.health + boost))
        if effects.get("happy_boost"):
            boost = float(effects["happy_boost"])
            self.happy = clamp_happy(min(HAPPY_MAX, self.happy + boost))

        # 3) 体温趋势（次日生效）
        if effects.get("temp_drift"):
            self.carried_effects.append({
                "type": "temp_drift",
                "value": float(effects["temp_drift"]),
                "days": int(effects.get("temp_drift_days", 2)),
                "name": effects.get("title", "体温趋势"),
            })

        # 4) 疾病
        if effects.get("worsen_disease"):
            target = self.worsen_disease(effects.get("worsen_disease"))
            if target:
                notes.append("%s 恶化，每日健康 -%.1f" % (target["name"], target["hp_per_day"]))

        if effects.get("disease"):
            spec = effects["disease"]
            days_bonus = 0
            hp_scale, temp_scale = 1.0, 1.0
            force = bool(effects.get("force_disease", False))
            if isinstance(spec, (tuple, list)):
                did = spec[0]
                if len(spec) > 1:
                    days_bonus = int(spec[1])
                if len(spec) > 2:
                    hp_scale = float(spec[2])
            else:
                did = spec
            # 默认走 U 型年龄曲线的患病判定（add_disease 内部完成）
            info, msg = self.add_disease(did, hp_scale=hp_scale,
                                         temp_scale=temp_scale,
                                         days_bonus=days_bonus, dice=dice,
                                         force=force)
            if msg:
                notes.append(msg)

        if effects.get("cure"):
            cid = effects["cure"] if isinstance(effects["cure"], str) else None
            ok, msg, _cost = self.cure_disease(cid)
            notes.append(msg)

        # 5) 自定义回调
        func = effects.get("func")
        if callable(func):
            try:
                extra = func(self)
                if extra:
                    notes.extend(extra)
            except Exception as exc:
                notes.append("（效果结算出现异常：%s）" % exc)

        # 6) 额外属性（体力等扩展属性一律走 clamp）
        for key, value in (effects.get("extra") or {}).items():
            if key in ("health", "happy", "money", "temp"):
                continue
            setattr(self, key, value)

        # 7) 统计
        delta = {
            "health": round(self.health - before["health"], 2),
            "happy": round(self.happy - before["happy"], 2),
            "money": round_money(self.money - before["money"]),
            "temp": round(self.temp - before["temp"], 2),
        }
        if delta["money"] > 0:
            self.stats["total_income"] = round_money(self.stats.get("total_income", 0.0) + delta["money"])
        elif delta["money"] < 0:
            self.stats["total_expense"] = round_money(self.stats.get("total_expense", 0.0) - delta["money"])
        self.stats["max_money"] = max(self.stats.get("max_money", 0.0), self.money)
        return delta, notes

    # ------------------------------------------------------------------
    # 大事记
    # ------------------------------------------------------------------
    def add_milestone(self, text, tag="life"):
        """记录人生大事（生日、恋爱、结婚、失业、重病、死亡等）。"""
        item = {"date": self.date_full, "text": text, "tag": tag}
        self.milestones.append(item)
        if len(self.milestones) > 500:
            self.milestones = self.milestones[-500:]
        return item

    def remember_event(self, name, category, summary):
        """记录触发过的事件（用于存档与日志回看）。"""
        self.event_history.append({
            "date": self.date_full, "name": name,
            "category": category, "summary": summary[:120],
        })
        if len(self.event_history) > 3000:
            self.event_history = self.event_history[-3000:]

    # ------------------------------------------------------------------
    # 结算辅助
    # ------------------------------------------------------------------
    def net_worth(self):
        """粗略身价：现金 + 房产/资产估算（资产按职级与年限估算）。"""
        asset = self.job_level * 2000.0 + min(self.total_days, 36000) * 0.4
        return round_money(self.money + asset)

    def attribute_rows(self):
        """返回界面用的属性表：[(名称, 当前值文本, 备注, 颜色)]"""
        rows = [
            ("健康", "%.1f / %d" % (self.health, HEALTH_MAX),
             "归零即死亡" if self.health > 20 else "！！！濒临死亡", self.health_color()),
            ("幸福", "%.1f / %d" % (self.happy, HAPPY_MAX),
             "低于 %d 会持续扣健康" % LOW_HAPPY_THRESHOLD, self.happy_color()),
            ("金钱", "%.2f" % self.money, "负债状态" if self.money < 0 else "可治病 / 消费", self.money_color()),
            ("体温", "%.1f ℃" % self.temp,
             "正常 36.0~37.0" if TEMP_NORMAL_LOW <= self.temp <= TEMP_NORMAL_HIGH else "异常！每日扣健康",
             self.temp_color()),
        ]
        return rows

    def health_color(self):
        if self.health <= 20:
            return "#ff4d4d"
        if self.health <= 50:
            return "#ffa64d"
        return "#4ad07a"

    def happy_color(self):
        if self.happy < LOW_HAPPY_THRESHOLD:
            return "#ff4d4d"
        if self.happy < 45:
            return "#ffa64d"
        return "#4ad07a"

    def money_color(self):
        if self.money < 0:
            return "#ff4d4d"
        if self.money < 500:
            return "#ffa64d"
        return "#f0c040"

    def temp_color(self):
        if TEMP_NORMAL_LOW <= self.temp <= TEMP_NORMAL_HIGH:
            return "#4ad07a"
        if self.temp >= 38.5 or self.temp <= 34.5:
            return "#ff4d4d"
        return "#ffa64d"

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self):
        return {
            "name": self.name, "city": self.city,
            "health": self.health, "happy": self.happy,
            "money": self.money, "temp": self.temp,
            "constitution": self.constitution, "family_wealth": self.family_wealth,
            "family_bankrupt": self.family_bankrupt, "left_home": self.left_home,
            "family_notes": self.family_notes[-50:],
            "age": self.age, "year": self.year, "month": self.month, "day": self.day,
            "total_days": self.total_days,
            "birth_month": self.birth_month, "birth_day": self.birth_day,
            "stage": self.stage, "stage_history": self.stage_history[-100:],
            "education": self.education, "exam_results": self.exam_results,
            "university_ok": self.university_ok, "postgrad_ok": self.postgrad_ok,
            "action_points": self.action_points, "actions_today": self.actions_today,
            "action_tally": self.action_tally, "days_played": self.days_played,
            "diseases": self.diseases, "employed": self.employed,
            "job_level": self.job_level, "married": self.married,
            "children": self.children, "carried_effects": self.carried_effects,
            "last_illness_day": self.last_illness_day,
            "plain_days": self.plain_days, "illness_count": self.illness_count,
            "milestones": self.milestones, "event_history": self.event_history[-500:],
            "stats": self.stats, "dead": self.dead,
            "death_reason": self.death_reason, "death_date": self.death_date,
            "summary_done": self.summary_done, "ambient_temp": self.ambient_temp,
            "rng_state": self.rng.getstate() if hasattr(self.rng, "getstate") else None,
        }

    @classmethod
    def from_dict(cls, data, rng=None):
        """从存档字典恢复人物；字段缺失时使用默认值，保证兼容旧存档。"""
        if not isinstance(data, dict):
            raise ValueError("存档内容不是合法的对象")
        player = cls(name=data.get("name", "无名氏"),
                     city=data.get("city", "beijing"), rng=rng)
        for key, caster in (("health", clamp_health), ("happy", clamp_happy),
                            ("money", round_money), ("temp", clamp_temp)):
            try:
                setattr(player, key, caster(float(data.get(key, getattr(player, key)))))
            except Exception:
                pass
        for key in ("age", "year", "month", "day", "total_days",
                    "birth_month", "birth_day", "job_level", "children"):
            try:
                setattr(player, key, int(data.get(key, getattr(player, key))))
            except Exception:
                pass
        player.month = int(clamp(player.month, 1, MONTHS_PER_YEAR))
        player.day = int(clamp(player.day, 1, DAYS_PER_MONTH))
        player.birth_month = int(clamp(player.birth_month, 1, MONTHS_PER_YEAR))
        player.birth_day = int(clamp(player.birth_day, 1, DAYS_PER_MONTH))
        player.employed = bool(data.get("employed", False))
        player.married = bool(data.get("married", False))
        player.dead = bool(data.get("dead", False))
        player.death_reason = data.get("death_reason", "") or ""
        player.death_date = data.get("death_date", "") or ""
        player.summary_done = bool(data.get("summary_done", False))
        # ---- 体质 / 家境（旧存档没有这两个字段时按均值补齐）----
        for key, lo, hi, mean in (("constitution", CONSTITUTION_MIN, CONSTITUTION_MAX,
                                   CONSTITUTION_MEAN),
                                  ("family_wealth", FAMILY_WEALTH_MIN, FAMILY_WEALTH_MAX,
                                   FAMILY_WEALTH_MEAN)):
            try:
                setattr(player, key, max(lo, min(hi, float(data.get(key, mean)))))
            except Exception:
                setattr(player, key, mean)
        player.family_bankrupt = bool(data.get("family_bankrupt", False))
        player.left_home = bool(data.get("left_home", False))
        player.family_notes = [str(x) for x in (data.get("family_notes") or [])][-50:]
        # ---- 人生阶段 / 学业 ----
        stage = data.get("stage")
        player.stage = stage if stage in STAGE_BY_ID else stage_of_age(player.age)
        player.stage_history = [s for s in (data.get("stage_history") or [])
                               if isinstance(s, dict)][-100:]
        player.education = [str(x) for x in (data.get("education") or [])]
        exams = data.get("exam_results")
        player.exam_results = exams if isinstance(exams, dict) else {}
        player.university_ok = data.get("university_ok", None)
        player.postgrad_ok = data.get("postgrad_ok", None)
        # ---- 行动点 ----
        try:
            player.action_points = int(data.get("action_points", ACTION_POINTS_PER_DAY))
        except Exception:
            player.action_points = ACTION_POINTS_PER_DAY
        player.action_points = max(0, min(ACTION_POINTS_PER_DAY, player.action_points))
        try:
            player.actions_today = max(0, int(data.get("actions_today", 0)))
            player.days_played = max(0, int(data.get("days_played", 0)))
        except Exception:
            pass
        tally = data.get("action_tally")
        player.action_tally = tally if isinstance(tally, dict) else {}
        try:
            player.last_illness_day = (None if data.get("last_illness_day") is None
                                       else int(data.get("last_illness_day")))
            player.plain_days = max(0, int(data.get("plain_days", 0)))
            player.illness_count = max(0, int(data.get("illness_count", 0)))
        except Exception:
            pass
        try:
            player.ambient_temp = float(data.get("ambient_temp", player.ambient_temp))
        except Exception:
            pass
        # 疾病：清洗字段，避免损坏的存档导致崩溃
        diseases = []
        for item in (data.get("diseases") or []):
            if not isinstance(item, dict):
                continue
            did = item.get("id")
            if did not in DISEASES:
                continue
            base = DISEASES[did]
            diseases.append({
                "id": did,
                "name": item.get("name", base["name"]),
                "kind": item.get("kind", base["kind"]),
                "days": max(1, int(item.get("days", 1))),
                "total_days": max(1, int(item.get("total_days", 1))),
                "hp_per_day": float(item.get("hp_per_day", base["hp_per_day"])),
                "happy_per_day": float(item.get("happy_per_day", base["happy_per_day"])),
                "cure_cost": float(item.get("cure_cost", base["cure_cost"])),
                "self_heal": float(item.get("self_heal", base["self_heal"])),
                "temp_mod": float(item.get("temp_mod", base["temp_mod"])),
                "needs_cure": bool(item.get("needs_cure", base.get("needs_cure", False))),
                "fatal": bool(item.get("fatal", base.get("fatal", False))),
            })
        player.diseases = diseases
        # 持续效果
        carried = []
        for item in (data.get("carried_effects") or []):
            if isinstance(item, dict) and item.get("type"):
                carried.append({
                    "type": item.get("type"),
                    "value": float(item.get("value", 0)),
                    "days": max(0, int(item.get("days", 0))),
                    "name": item.get("name", "持续效果"),
                })
        player.carried_effects = carried
        player.milestones = [m for m in (data.get("milestones") or []) if isinstance(m, dict)][-500:]
        player.event_history = [e for e in (data.get("event_history") or []) if isinstance(e, dict)][-500:]
        stats = data.get("stats")
        if isinstance(stats, dict):
            player.stats.update({k: v for k, v in stats.items() if k in player.stats})
        return player


# ==============================================================================
# 10. 人生日志（life_log.txt）
# ==============================================================================

class LifeLog:
    """负责把每日关键事件、属性变化与人生节点写入 life_log.txt。"""

    #: 日志文件大小上限（约 8MB），超过后不再追加逐日流水（人生总结仍会写入）
    MAX_LOG_BYTES = 8 * 1024 * 1024

    def __init__(self, path=None, player_name="", city_name=""):
        self.path = path
        self.player_name = player_name
        self.city_name = city_name
        self.memory = []          # 内存中的日志行（界面回看用）
        self.error = None
        self.oversize = False     # 日志文件是否已达上限

    # ------------------------------------------------------------------
    def _write(self, text, force=False):
        """写入一行日志；写入失败只记录错误，不抛出异常。"""
        stamp = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s" % (stamp, text)
        self.memory.append(line)
        if len(self.memory) > 20000:
            self.memory = self.memory[-20000:]
        if not self.path:
            return False
        if self.oversize and not force:
            return False
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            # 控制日志体积，避免长时间挂机后文件过大
            try:
                if os.path.getsize(self.path) > self.MAX_LOG_BYTES:
                    self.oversize = True
                    with open(self.path, "a", encoding="utf-8") as fh2:
                        fh2.write("[日志已达大小上限，之后仅记录重大节点与人生总结]\n")
            except Exception:
                pass
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    # ------------------------------------------------------------------
    def start(self, player):
        """开局：写入分隔线与人物档案。"""
        self.player_name = player.name
        self.city_name = get_city(player.city)["name"]
        sep = "=" * 78
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write("\n" + sep + "\n")
                fh.write("【新的人生开始】%s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                fh.write("姓名：%s    城市：%s（%s）\n" % (
                    player.name, self.city_name, get_city(player.city)["tag"]))
                fh.write("初始属性：健康 %.0f / 幸福 %.0f / 金钱 %.2f / 体温 %.1f℃\n" % (
                    player.health, player.happy, player.money, player.temp))
                fh.write(sep + "\n")
        except Exception as exc:
            self.error = str(exc)
        self.memory.append("【新的人生开始】%s · %s" % (player.name, self.city_name))

    def daily(self, player, event_name, summary, delta, ambient=None):
        """记录一天的关键事件与属性变化。"""
        delta_text = "健康%+.1f 幸福%+.1f 金钱%+.0f 体温%+.1f" % (
            delta.get("health", 0), delta.get("happy", 0),
            delta.get("money", 0), delta.get("temp", 0))
        ambient_text = ("气温 %.1f℃" % ambient) if ambient is not None else ""
        line = "%s｜%s｜事件：%s｜%s｜%s｜当前：健康%.1f 幸福%.1f 金钱%.2f 体温%.1f℃" % (
            player.date_full, player.life_stage, event_name, summary,
            (ambient_text + "｜" if ambient_text else "") + delta_text,
            player.health, player.happy, player.money, player.temp)
        self._write(line)

    def milestone(self, player, text, tag="life"):
        """记录人生重大节点。"""
        self._write("★【%s】%s｜%s" % (tag, player.date_full, text), force=True)

    def disease(self, player, text):
        self._write("＋【疾病】%s｜%s" % (player.date_full, text), force=True)

    def settlement(self, player, text):
        self._write("￥【结算】%s｜%s" % (player.date_full, text), force=True)

    def death(self, player, reason):
        self._write("☠【死亡】%s｜%s" % (player.date_full, reason), force=True)

    # ------------------------------------------------------------------
    def life_summary(self, player):
        """生成完整人生总结（死亡时调用），并追加到日志。"""
        lines = []
        sep = "=" * 78
        lines.append("")
        lines.append(sep)
        lines.append("【人生总结】%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("姓名：%s（%s）    城市：%s" % (
            player.name, player.life_stage, get_city(player.city)["name"]))
        lines.append("享年：%d 岁（共度过 %d 天，约 %.1f 年）" % (
            player.age, player.total_days, player.total_days / float(DAYS_PER_YEAR)))
        lines.append("离世时间：%s" % (player.death_date or player.date_text))
        lines.append("离世原因：%s" % (player.death_reason or "自然衰老"))
        lines.append("-" * 78)
        lines.append("最终属性：健康 %.1f / 幸福 %.1f / 金钱 %.2f / 体温 %.1f℃" % (
            player.health, player.happy, player.money, player.temp))
        lines.append("身价估算：%.2f（最高峰 %.2f）" % (
            player.net_worth(), player.stats.get("max_money", 0.0)))
        lines.append("婚恋状况：%s    子女：%d 人    职级：%d 级" % (
            "已婚" if player.married else "未婚", player.children, player.job_level))
        lines.append("统计：工作 %d 天 / 休息 %d 天 / 患病 %d 次 / 治愈 %d 次" % (
            player.stats.get("days_worked", 0), player.stats.get("days_rested", 0),
            player.stats.get("disease_count", 0), player.stats.get("cure_count", 0)))
        lines.append("累计收入 %.2f    累计支出 %.2f" % (
            player.stats.get("total_income", 0.0), player.stats.get("total_expense", 0.0)))
        lines.append("-" * 78)
        lines.append("【生平大事记】")
        if player.milestones:
            for item in player.milestones:
                lines.append("  · %s  %s" % (item.get("date", ""), item.get("text", "")))
        else:
            lines.append("  · （这一生波澜不惊，没有什么值得特别记录的。）")
        lines.append("-" * 78)
        lines.append("【事件总览（最近 40 条）】")
        for item in player.event_history[-40:]:
            lines.append("  · %s｜%s｜%s" % (item.get("date", ""), item.get("name", ""),
                                             item.get("summary", "")))
        lines.append(sep)
        text = "\n".join(lines)
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception as exc:
            self.error = str(exc)
        self.memory.append("【人生总结】享年 %d 岁，%s" % (player.age, player.death_reason))
        return text


    def tail_lines(self, count=200):
        """读取日志文件末尾若干行（用于界面回看）。"""
        if not self.path or not os.path.isfile(self.path):
            return list(self.memory[-count:])
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            return [ln.rstrip("\n") for ln in lines[-count:]]
        except Exception as exc:
            self.error = str(exc)
            return list(self.memory[-count:])


# ==============================================================================
# 11. 存档系统（save.json）
# ==============================================================================

def save_game(path, player, log=None):
    """
    保存进度到 JSON 文件（先写临时文件再替换，避免中途失败损坏存档）。
    返回 (是否成功, 提示信息)
    """
    data = {
        "version": SAVE_VERSION,
        "app": APP_NAME,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "player": player.to_dict(),
    }
    tmp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    except Exception:
        pass
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True, "进度已保存到：\n%s" % path
    except Exception as exc:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False, "保存失败：%s" % exc


def load_game(path, rng=None):
    """
    读取存档。
    返回 (player 或 None, 提示信息)
    """
    if not path or not os.path.isfile(path):
        return None, "找不到存档文件：\n%s\n\n请先开始一局游戏并保存进度。" % (path or "(未设置路径)")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:
        return None, "读取存档失败：%s" % exc
    try:
        data = json.loads(raw)
    except Exception as exc:
        return None, "存档内容已损坏，无法解析：%s" % exc
    if not isinstance(data, dict) or "player" not in data:
        return None, "存档格式不正确（缺少人物数据）。"
    try:
        player = Player.from_dict(data["player"], rng=rng)
    except Exception as exc:
        return None, "存档人物数据异常：%s" % exc
    saved_at = data.get("saved_at", "未知时间")
    return player, "读取成功。\n存档时间：%s\n姓名：%s    时间：%s" % (
        saved_at, player.name, player.date_full)


def save_exists(path):
    return bool(path) and os.path.isfile(path)


def delete_save(path):
    """删除存档，返回 (是否成功, 提示)。"""
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True, "存档已删除。"
        return False, "没有找到可删除的存档。"
    except Exception as exc:
        return False, "删除存档失败：%s" % exc


# ==============================================================================
# 12. 每日结算引擎（模拟器）
# ==============================================================================

class DailyReport:
    """一天结算后的完整结果，供界面展示与日志记录。"""

    def __init__(self, player):
        self.player = player
        self.date = player.date_full
        self.ambient = player.ambient_temp
        self.roll_lines = []          # 骰子说明行
        self.lines = []               # 结算说明行
        self.delta = {"health": 0.0, "happy": 0.0, "money": 0.0, "temp": 0.0}
        self.event_name = ""
        self.death = False
        self.birthday = False
        self.secret = False
        self.month_settlement = None

    def add_line(self, text):
        if text:
            self.lines.append(text)

    def accumulate(self, delta):
        for key in self.delta:
            self.delta[key] = round(self.delta[key] + float(delta.get(key, 0)), 2)


class Simulator:
    """
    游戏引擎：时间推进、日月年结算、事件抽取、疾病与体温结算。
    与界面完全解耦——界面只调用 step_roll / resolve_choice / apply_daily_action。
    """

    def __init__(self, player, log=None, base_dir="", seed=None):
        self.player = player
        self.log = log
        self.base_dir = base_dir
        self.dice = DiceSystem(random.Random(seed) if seed is not None else random.Random())
        self.pending = None            # 待结算的事件卡
        self.last_report = None
        self.game_over = False
        self.pending_followup = None   # 连锁事件
        self.current_seed = seed
        self.category_last_day = {}    # 各大类事件最近一次发生的天数（冷却用）
        self.mod_hooks_used = []       # 记录本次运行里被用到的模组钩子
        # 把玩家同步为"标准流程"下该年龄的阶段（旧存档/外部构造时兜底）
        if not self.player.stage or self.player.stage not in STAGE_BY_ID:
            self.player.stage = stage_of_age(self.player.age)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _log_delta(self, report):
        if self.log:
            self.log.daily(self.player, report.event_name or "日常",
                           "；".join(report.lines[:6]) or "平静的一天",
                           report.delta, report.ambient)

    def _money(self, amount, reason="", report=None):
        """统一的金钱收支入口（保持 2 位小数并统计）。"""
        self.player.money = round_money(self.player.money + amount)
        if amount > 0:
            self.player.stats["total_income"] = round_money(
                self.player.stats.get("total_income", 0.0) + amount)
        elif amount < 0:
            self.player.stats["total_expense"] = round_money(
                self.player.stats.get("total_expense", 0.0) - amount)

    # ------------------------------------------------------------------
    # 时间推进
    # ------------------------------------------------------------------
    def advance_calendar(self):
        """推进一天：处理跨月、跨年与生日。返回跨月结算信息列表。"""
        p = self.player
        p.day += 1
        p.total_days += 1
        notes = []

        if p.day > DAYS_PER_MONTH:
            p.day = 1
            p.month += 1
            notes.append(("month", p.month))
        if p.month > MONTHS_PER_YEAR:
            p.month = 1
            p.year += 1
            p.age += 1
            notes.append(("year", p.age))

        # 生日判定：出生日为 1 月 1 日，则每年 1 月 1 日过生日
        birthday = (p.month == p.birth_month and p.day == p.birth_day)
        return notes, birthday

    def settle_month(self, report):
        """每月初结算工资收入与固定生活支出。"""
        p = self.player
        # 未满 16 岁不可能拥有正式工作（防止异常状态导致的错误收入）
        if p.age < 16 and p.employed:
            p.employed = False
            p.job_level = 0
        month_income = 0.0
        month_expense = 0.0
        detail = []

        # ---- 收入 ----
        if p.age < 6:
            month_income = 0.0
            detail.append("未成年（%d 岁），由父母抚养，无收入" % p.age)
        elif p.age < 16:
            month_income = 100.0 + 10 * p.job_level
            detail.append("零花钱收入 %.0f" % month_income)
        else:
            if p.employed:
                base = BASE_WAGE + 700.0 * max(0, p.job_level - 1)
                base += 400.0 if p.job_level >= 4 else 0.0
                age_mod = 1.0
                if p.age < 22:
                    age_mod = 0.55
                elif p.age >= 60:
                    age_mod = 0.6
                month_income = round(base * age_mod, 2)
                detail.append("职级 %d 工资 %.2f" % (p.job_level, month_income))
            else:
                # 失业补助 / 打零工
                month_income = 200.0 if p.age >= 18 else 0.0
                detail.append("无业，打零工收入 %.0f" % month_income)
        if p.age >= 60 and p.employed:
            pension = 500.0
            month_income += pension
            detail.append("退休返聘补贴 %.0f" % pension)
        # 资产增值：长期积累也会带来一点被动收益（身价越高收益越多）
        if p.money > 100000:
            passive = round(p.money * 0.0015, 2)
            month_income += passive
            detail.append("资产收益 %.2f" % passive)

        # ---- 家庭支持（成年前 / 大学毕业前由父母承担开销）----
        support = family_support_amount(p)
        fname, fdesc, _fsup = family_tier(p.family_wealth)
        if support > 0:
            month_income += support
            p.stats["family_support_total"] = round_money(
                p.stats.get("family_support_total", 0.0) + support)
            detail.append("父母供养 %.2f（%s家庭：%s）" % (support, fname, fdesc))
        elif p.family_bankrupt and p.age < 22 and p.stage in FAMILY_SUPPORT_STAGES:
            detail.append("家庭已破产，父母无力再提供任何支持")
        elif p.left_home:
            detail.append("已离家独立，一切开销自负")

        # ---- 支出 ----
        city = get_city(p.city)
        month_expense = BASE_EXPENSE * city["cost_factor"]
        month_expense += 120.0 * p.children          # 子女抚养
        if p.married:
            month_expense *= 1.30
        if p.age < 16:
            month_expense *= 0.30                    # 由家庭承担大部分
        if p.age >= 22:
            # 生活水平随身价缓慢提高（避免金钱无限积累）
            wealth_factor = 1.0 + min(2.5, max(0.0, p.money) / 50000.0)
            month_expense *= wealth_factor
        if p.diseases:
            month_expense += 120.0 * len(p.diseases)  # 医药零碎开销
        # 读书阶段（大学/读研）会有一笔学杂费
        if p.stage == "university":
            month_expense += 300.0
        elif p.stage == "postgrad":
            month_expense += 200.0
        month_expense = round(month_expense, 2)
        detail.append("生活支出 %.2f（%s 消费系数 %.2f）" % (
            month_expense, city["name"], city["cost_factor"]))

        net = round(month_income - month_expense, 2)
        # 未成年 / 在读且家庭未破产时：父母兜底，保证孩子不会因为"不能挣钱"而负债累累
        if net < 0 and support > 0 and p.age <= 25:
            covered = round(min(-net, max(0.0, p.money + support * 2)), 2)
            if covered > 0:
                net += covered
                detail.append("父母替你垫付了 %.2f 的开销" % covered)
        delta, notes = p.apply_effects({"money": net}, dice=self.dice)
        report.accumulate(delta)
        for note in notes:
            report.add_line(note)
        report.add_line("本月结算：收入 %.2f，支出 %.2f，净变化 %s" % (
            month_income, month_expense, fmt_signed(net, 2)))
        for item in detail:
            report.add_line("    · %s" % item)
        if self.log:
            self.log.settlement(p, "收入 %.2f / 支出 %.2f（%s）" % (
                month_income, month_expense, "；".join(detail)))

    # ------------------------------------------------------------------
    # 家庭破产与人生阶段推进
    # ------------------------------------------------------------------
    def settle_family_phase(self, report):
        """
        家庭破产判定：每年一次，概率极低（万分位配置，默认每年约 3‰）。
        破产后父母不再提供任何经济支持。
        """
        p = self.player
        if p.family_bankrupt or p.left_home:
            return
        if p.age < FAMILY_BANKRUPTCY_MIN_AGE or p.age > 25:
            return
        if not (p.month == p.birth_month and p.day == p.birth_day):
            return
        roll = self.dice.roll(10000, 1, 0, "家庭变故判定")
        self.dice.remember(roll, "家庭变故判定")
        threshold = FAMILY_BANKRUPTCY_PERMILLE * 10    # 3‰ = 30/10000
        # 家境越差，越容易出变故
        if p.family_wealth < 30:
            threshold = int(threshold * 2.2)
        elif p.family_wealth < 50:
            threshold = int(threshold * 1.4)
        if roll.value <= threshold:
            p.family_bankrupt = True
            msg = "【家庭变故】家中生意失败/负债累累，家庭破产了。从此父母无法再提供经济支持。"
            p.family_notes.append(p.date_full + " 家庭破产")
            p.add_milestone("家庭破产（%d 岁）" % p.age, tag="家庭")
            report.add_line(msg)
            delta, _ = p.apply_effects({"happy": -18}, dice=self.dice)
            report.accumulate(delta)
            if self.log:
                self.log.milestone(p, "家庭破产，家中再也拿不出钱", "家庭")
        else:
            report.add_line("家庭平安（变故判定 %d > %d）" % (roll.value, threshold))

    def advance_stage(self, report):
        """
        人生阶段推进：按年龄与考试结果推进
        学龄前 -> 幼儿园 -> 小学 -> 初中 -> 中考 -> 高中 -> 高考 -> 大学(有概率不上)
        -> 读研(有概率读不上) -> 工作 -> 退休
        """
        p = self.player
        stage = STAGE_BY_ID.get(p.stage) or STAGE_BY_ID["infant"]
        end_age = stage.get("end", 200)
        if p.age <= end_age:
            return
        nxt = stage.get("next")
        if not nxt:
            return
        # ---- 中考 / 高考 / 考研的分支判定 ----
        if stage.get("exam") == "zhongkao":
            ok = self._roll_exam("zhongkao", report)
            p.exam_results["zhongkao"] = "考上高中" if ok else "没考上高中"
            if not ok:
                # 没考上高中 -> 辍学打工
                self.change_stage("dropout", report, "中考失利，你提前离开校园")
                return
        elif stage.get("exam") == "gaokao":
            ok = self._roll_exam("gaokao", report)
            p.university_ok = ok
            p.exam_results["gaokao"] = "考上大学" if ok else "落榜"
            if not ok:
                self.change_stage("work", report, "高考落榜，你提前进入社会")
                return
        elif p.stage == "university":
            # 大学毕业：有概率继续读研（受家境与学业表现影响）
            ok = self._roll_exam("postgrad", report)
            p.postgrad_ok = ok
            if ok:
                self.change_stage("postgrad", report, "你考上了研究生")
                return
            p.exam_results["postgrad"] = "未考研/未考上"
            self.change_stage("work", report, "你大学毕业，开始工作")
            return
        elif p.stage == "postgrad":
            self.change_stage("work", report, "研究生毕业，你正式进入职场")
            return

        self.change_stage(nxt, report, None)

    def _roll_exam(self, exam, report):
        """
        考试判定：d100 + 学业加成 >= 目标值。
        学业表现（study_points）来自「学习充电」操作与相关事件：
            约每 40 点学业表现 +1 分，最多 +25 分
            家境好则额外 +0~4 分，健康差则 -8 分
        目标值：中考 45 / 高考 52 / 考研 58（"不学习就考不上"是合理的）
        """
        p = self.player
        target_map = {"zhongkao": 45, "gaokao": 52, "postgrad": 58}
        target = target_map.get(exam, 50)
        bonus = min(25, int(p.stats.get("study_points", 0) // 40))
        bonus += int(max(0, (p.family_wealth - 50)) // 12)
        if p.health < 50:
            bonus -= 8
        roll = self.dice.d100("考试判定")
        self.dice.remember(roll, "%s判定" % {"zhongkao": "中考", "gaokao": "高考",
                                             "postgrad": "考研"}.get(exam, exam))
        total = roll.value + bonus
        ok = total >= target
        report.add_line("考试判定：骰子 %d + 学业/家境加成 %d = %d，目标 %d → %s" % (
            roll.value, bonus, total, target, "通过" if ok else "未通过"))
        return ok

    def change_stage(self, stage_id, report=None, note=None):
        """切换人生阶段，并记录学历。"""
        p = self.player
        if stage_id not in STAGE_BY_ID:
            return
        old = p.stage
        p.stage = stage_id
        meta = STAGE_BY_ID[stage_id]
        p.stage_history.append({
            "date": p.date_full, "age": p.age,
            "from": old, "to": stage_id, "name": meta["name"],
        })
        edu_map = {"primary": "小学", "middle": "初中", "high": "高中",
                   "university": "大学", "postgrad": "研究生"}
        if stage_id in edu_map and edu_map[stage_id] not in p.education:
            p.education.append(edu_map[stage_id])
        if stage_id == "work" and not p.employed:
            p.employed = True
            p.job_level = max(1, p.job_level)
        if stage_id in ("retired",):
            p.employed = False
        text = "【人生阶段】%d 岁：进入「%s」——%s" % (p.age, meta["name"], meta["desc"])
        if note:
            text = "【人生阶段】%d 岁：%s（%s）" % (p.age, note, meta["name"])
        p.add_milestone("进入%s阶段" % meta["name"], tag="阶段")
        if report is not None:
            report.add_line(text)
        if self.log:
            self.log.milestone(p, text.replace("【人生阶段】", ""), "阶段")

    def auto_progress_stages(self, report):
        """连续推进阶段（时间跳跃后可能出现跨多个阶段的情况）。"""
        for _ in range(8):
            before = self.player.stage
            self.advance_stage(report)
            if self.player.stage == before:
                break
            if self.player.dead:
                break

    # ------------------------------------------------------------------
    # 环境与疾病每日结算
    # ------------------------------------------------------------------
    def roll_ambient(self):
        """投掷当日气温并写入人物状态。"""
        p = self.player
        ambient, res = roll_ambient_temp(self.dice, p.city, p.month)
        p.ambient_temp = ambient
        self.dice.remember(res, "当日气温")
        return ambient, res

    def settle_disease_phase(self, report):
        """疾病按天结算：扣血、扣幸福、影响体温、自愈与死亡风险。"""
        p = self.player
        if not p.diseases:
            return
        # 体质影响每日扣血（体质弱的人病得更重）
        sus = constitution_susceptibility(p.constitution)
        hp_factor = round(0.75 + 0.25 * sus, 2)
        for disease in list(p.diseases):
            hp_loss = round(disease["hp_per_day"] * hp_factor, 2)
            happy_loss = disease["happy_per_day"]
            delta, _ = p.apply_effects({"health": -hp_loss, "happy": -happy_loss,
                                        "temp": disease["temp_mod"]}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("%s 发作：健康 %s，幸福 %s，体温 %s" % (
                disease["name"], fmt_signed(delta["health"], 1),
                fmt_signed(delta["happy"], 1), fmt_signed(delta["temp"], 2)))

            # 自愈判定
            if disease["self_heal"] > 0:
                roll = self.dice.d100("自愈判定")
                self.dice.remember(roll, "%s自愈判定" % disease["name"])
                if roll.value <= disease["self_heal"] * 100:
                    p.diseases.remove(disease)
                    report.add_line("你的%s自愈了（骰子 %d ≤ %d）。" % (
                        disease["name"], roll.value, int(disease["self_heal"] * 100)))
                    if self.log:
                        self.log.disease(p, "%s 自愈" % disease["name"])
                    continue

            disease["days"] -= 1
            if disease["days"] <= 0:
                if disease["needs_cure"]:
                    # 慢性病不治疗会一直存在，只是每 10 天"提醒"一次
                    disease["days"] = 10
                    report.add_line("慢性病仍在持续，建议尽快治疗。")
                else:
                    p.diseases.remove(disease)
                    report.add_line("你的%s已经痊愈。" % disease["name"])
                    if self.log:
                        self.log.disease(p, "%s 痊愈" % disease["name"])

            # 危重疾病致死判定
            if disease.get("fatal") and p.health <= 25:
                roll = self.dice.d20("危重判定")
                self.dice.remember(roll, "危重判定")
                if roll.value <= 6:
                    report.add_line("病情危重，骰子判定失败……")
                    self.kill("因%s病情恶化，抢救无效" % disease["name"], report)
                    return

    def settle_env_phase(self, report):
        """环境结算：体温回归/偏移 + 体温异常每日扣血。"""
        p = self.player
        drift, desc, res = temperature_adjust(self.dice, p)
        self.dice.remember(res, "体温变动")
        delta, _ = p.apply_effects({"temp": drift}, dice=self.dice)
        report.accumulate(delta)
        if abs(delta["temp"]) >= 0.05:
            report.add_line("体温变动 %s%s" % (fmt_signed(delta["temp"], 2),
                                           ("（%s）" % desc) if desc else ""))

        # 体温异常 → 每日扣健康
        if p.temp > TEMP_NORMAL_HIGH:
            excess = p.temp - TEMP_NORMAL_HIGH
            loss = 1.6 + excess * 2.0
            if p.temp >= 39.0:
                loss += 3.5
            delta, _ = p.apply_effects({"health": -loss}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("体温过高（%.1f℃）→ 健康 %s" % (p.temp, fmt_signed(delta["health"], 1)))
        elif p.temp < TEMP_NORMAL_LOW:
            deficit = TEMP_NORMAL_LOW - p.temp
            loss = 1.6 + deficit * 2.0
            if p.temp <= 35.0:
                loss += 3.5
            delta, _ = p.apply_effects({"health": -loss}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("体温过低（%.1f℃）→ 健康 %s" % (p.temp, fmt_signed(delta["health"], 1)))

    def settle_recover_phase(self, report):
        """
        自然恢复：没有生病时身体会缓慢回血；带病期间恢复能力大幅下降，
        因此"生病了要休息/看病"才是正确策略。
        每日回血有上限（收益递减），避免数值无限膨胀。
        """
        p = self.player
        if p.health >= HEALTH_MAX:
            return
        gain = 0.8
        if p.diseases:
            gain *= 0.25           # 病中恢复极慢
        if p.temp < TEMP_NORMAL_LOW or p.temp > TEMP_NORMAL_HIGH:
            gain *= 0.4            # 体温异常时恢复变差
        if 16 <= p.age < 40:
            gain -= 0.2            # 成年后不再有童年红利
        if p.age <= 12:
            gain += 0.3            # 孩子恢复得更快
        elif p.age >= 55:
            gain -= 0.25           # 年长者恢复更慢
        if p.happy >= 70:
            gain += 0.3
        elif p.happy < LOW_HAPPY_THRESHOLD:
            gain -= 0.2
        if p.health < 10:
            gain += 0.8            # 危急时身体全力自救
        # 健康越高，自然恢复越慢（收益递减，避免长期顶格）
        if p.health >= 90:
            gain *= 0.4
        elif p.health >= 75:
            gain *= 0.7
        gain = max(0.15, gain)
        delta, _ = p.apply_effects({"health_boost": gain}, dice=self.dice)
        if delta["health"] > 0.01:
            report.accumulate(delta)
            report.add_line("自然恢复：健康 %s" % fmt_signed(delta["health"], 1))

    def settle_hospital_phase(self, report):
        """
        医院抢救：健康跌破危险线时自动送医治疗最严重的疾病。
          * 钱够 -> 直接付清
          * 钱不够 -> 允许按医保赊账一部分（最多自付一半），既避免必死，也带来负债压力
        另外给低健康角色一点紧急缓冲，避免"毫无操作空间地被病死"。
        """
        p = self.player
        if p.dead:
            return False
        # 危急缓冲：健康跌破 5 时，身体会强制保住最后一线生机（每天一次）
        if 0 < p.health < 5:
            delta, _ = p.apply_effects({"health_boost": 2.0}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("【求生本能】你强撑着没有倒下（健康 %s）" % fmt_signed(delta["health"], 1))
        if not p.diseases or p.health > 12:
            return False
        target = p.worst_disease()
        if target is None:
            return False
        cost = float(target["cure_cost"])
        if p.money >= cost:
            ok, msg, paid = p.cure_disease(target["id"])
        else:
            ok, msg = False, ""
            need = round(cost * 0.5, 2)
            if p.money + need >= cost:
                # 医保/亲友垫付：先借钱付清，形成负债
                borrow = round(cost - p.money, 2)
                p.money = round_money(p.money + borrow)
                p.stats["total_income"] = round_money(
                    p.stats.get("total_income", 0.0) + borrow)
                p.stats["debt"] = round_money(p.stats.get("debt", 0.0) + borrow)
                ok, msg, paid = p.cure_disease(target["id"])
                if ok:
                    msg += "（向亲友/医保借款 %.2f 支付了医药费）" % borrow
        if ok:
            p.stats["hospital_count"] = p.stats.get("hospital_count", 0) + 1
            report.add_line("【紧急送医】健康跌至 %.1f，你被送进医院：%s" % (p.health, msg))
            if self.log:
                self.log.disease(p, "紧急送医治愈%s" % target["name"])
            p.add_milestone("紧急送医：治愈%s" % target["name"], tag="疾病")
            return True
        return False

    def natural_death_roll(self, report):
        """
        自然寿命判定：每年生日掷一次"生死骰"（d100）。
        死亡率随年龄指数上升，目标是把角色的平均寿命稳定在 80 岁左右。
        返回 True 表示本轮判定死亡。
        """
        p = self.player
        if p.age < NATURAL_DEATH_START:
            return False
        rate = natural_death_rate(p.age, p.health, p.diseases)
        roll = self.dice.d100("寿命判定")
        self.dice.remember(roll, "%d 岁寿命判定" % p.age)
        report.add_line("寿命判定：%d 岁，本年自然死亡概率 %.1f%%，骰子 %d" % (
            p.age, rate * 100.0, roll.value))
        if roll.value <= rate * 100.0:
            self.kill("寿终正寝，享年 %d 岁（自然衰老）" % p.age, report)
            return True
        return False

    def settle_aging_phase(self, report):
        """
        衰老阶段：
          * 45 岁之后健康上限逐年降低（上限 = 100 - 每岁 0.35，最低 55）
          * 60 岁后每天有衰老损耗，年龄越大损耗越快
        """
        p = self.player
        if p.age >= NATURAL_DEATH_START and p.month == p.birth_month and p.day == p.birth_day:
            if self.natural_death_roll(report):
                return
        if p.age < 45:
            return
        # 健康上限随年龄降低
        cap = max(55.0, HEALTH_MAX - (p.age - 45) * 0.35)
        if p.health > cap:
            cut = round(min(p.health - cap, 1.2), 2)
            delta, _ = p.apply_effects({"health": -cut}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("岁月痕迹：健康上限降至 %.0f（健康 %s）" % (cap, fmt_signed(delta["health"], 1)))
        # 60 岁之后每天自然衰老损耗
        if p.age >= 60:
            loss = 0.5 + (p.age - 60) * 0.06
            delta, _ = p.apply_effects({"health": -round(loss, 2)}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("年老体衰：健康 %s" % fmt_signed(delta["health"], 1))

    def settle_mood_phase(self, report):
        """幸福过低 debuff：长期低于阈值会持续扣健康。"""
        p = self.player
        if p.happy < LOW_HAPPY_THRESHOLD:
            loss = 2.5 + (LOW_HAPPY_THRESHOLD - p.happy) * 0.25
            delta, _ = p.apply_effects({"health": -loss}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("幸福过低（%.1f < %d）→ 抑郁侵蚀健康 %s" % (
                p.happy, LOW_HAPPY_THRESHOLD, fmt_signed(delta["health"], 1)))
        # 幸福自然回落（避免长期顶格）
        if p.happy > 90:
            p.happy = clamp_happy(p.happy - 0.6)

    def settle_carried(self, report):
        """跨天持续效果结算（例如寒潮后的体温趋势）。"""
        p = self.player
        remain = []
        for item in p.carried_effects:
            value = float(item.get("value", 0))
            if item.get("type") == "temp_drift":
                delta, _ = p.apply_effects({"temp": value}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("%s：体温 %s" % (item.get("name", "持续效果"),
                                              fmt_signed(delta["temp"], 2)))
            elif item.get("type") == "health":
                delta, _ = p.apply_effects({"health": value}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("%s：健康 %s" % (item.get("name", "持续效果"),
                                              fmt_signed(delta["health"], 1)))
            item["days"] = int(item.get("days", 1)) - 1
            if item["days"] > 0:
                remain.append(item)
        p.carried_effects = remain

    def check_death(self, report):
        """死亡判定：健康归零、体温极端、年龄过大自然衰老。"""
        p = self.player
        if p.dead:
            return True
        if p.health <= HEALTH_MIN:
            if p.diseases:
                reason = "因%s导致身体机能衰竭" % p.worst_disease()["name"]
            elif p.temp >= TEMP_NORMAL_HIGH:
                reason = "因持续高热导致器官衰竭"
            elif p.temp < TEMP_NORMAL_LOW:
                reason = "因长期失温导致心脏骤停"
            elif p.happy < LOW_HAPPY_THRESHOLD:
                reason = "因长期抑郁、身心俱疲而离世"
            else:
                reason = "因健康状况持续恶化而离世"
            self.kill(reason, report)
            return True
        if p.temp >= TEMP_HARD_HIGH - 0.5 or p.temp <= TEMP_HARD_LOW + 0.5:
            self.kill("体温达到极端值（%.1f℃），生命体征消失" % p.temp, report)
            return True
        if p.age >= AGE_MAX_LIMIT:
            self.kill("寿终正寝，享年 %d 岁" % p.age, report)
            return True
        return False

    def kill(self, reason, report=None):
        """人物死亡：写入状态与日志。"""
        p = self.player
        if p.dead:
            return
        p.dead = True
        p.health = 0.0
        p.death_reason = reason
        p.death_date = p.date_full
        p.add_milestone("离世：%s" % reason, tag="死亡")
        if report is not None:
            report.death = True
            report.add_line("【死亡】%s" % reason)
        if self.log:
            self.log.death(p, reason)
        self.game_over = True

    # ------------------------------------------------------------------
    # 每日事件抽取
    # ------------------------------------------------------------------
    def roll_illness_opportunity(self):
        """
        每日"生病机会"判定（与普通事件独立）：
          * 概率 = sickness_probability(player)（含体质、年龄 U 型曲线、状态、城市）
          * 受"生病最短间隔"限制（默认 25 天），避免一个月生好几次病
          * 体质越好概率越低；当天的"锻炼身体"操作有额外保护
        返回 (是否生病, DiceResult 或 None, 说明文本)
        """
        p = self.player
        if not illness_gap_ok(p):
            return False, None, "距上次生病不足 %d 天，本次跳过患病判定" % MIN_ILLNESS_GAP_DAYS
        prob = sickness_probability(p)
        # 锻炼身体的保护效果（当天每锻炼一次约 -25%，最多 -60%）
        exercise = int((p.stats or {}).get("exercise_today", 0) or 0)
        if exercise > 0:
            prob *= max(0.40, 0.75 ** exercise)
        roll = self.dice.roll(10000, 1, 0, "生病机会判定")
        self.dice.remember(roll, "生病机会判定（万分位）")
        if roll.value <= max(1.0, prob * 10000.0):
            return True, roll, "生病机会判定通过（%d ≤ %.1f）：今天身体有些不舒服" % (
                roll.value, prob * 10000.0)
        return False, roll, "身体无恙（生病机会判定 %d > %.1f）" % (
            roll.value, prob * 10000.0)

    def step_roll(self):
        """
        「推进一天」：
            时间 +1 天 → 跨月/跨年结算 → 生病机会判定 → 掷骰抽事件
            → 重置行动点 → 返回待决策事件卡（一天最多触发一次事件）。
        返回 dict(tone="event" / "nothing" / "dead", ...)
        """
        if self.player.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        # 上一张卡未处理完时不允许重复推进
        if self.pending is not None:
            return {"tone": "nothing", "text": "请先处理完当前事件。"}
        self.dice.reset_today()
        self.pending_followup = None
        p = self.player
        report = DailyReport(p)
        events_notes, birthday = self.advance_calendar()
        p.days_played += 1
        p.stats["days_played"] = p.stats.get("days_played", 0) + 1

        # ---- 跨年 / 跨月提示 ----
        for kind, value in events_notes:
            if kind == "month":
                self.settle_month(report)
                self.settle_family_phase(report)
                p.add_milestone("进入第 %d 月" % value, tag="时间")
            elif kind == "year":
                self.log and self.log.milestone(p, "满 %d 岁" % p.age, "年龄")
                p.add_milestone("满 %d 岁" % p.age, tag="年龄")
                report.add_line("★ 你满 %d 岁了（%s阶段：%s）。" % (
                    p.age, stage_name(p.stage), STAGE_BY_ID[p.stage]["desc"]))

        # ---- 生日事件 ----
        forced_event = None
        if birthday:
            forced_event = EVENTS["secret_birthday"]
            p.add_milestone("生日（%d 岁）" % p.age, tag="生日")
            if self.log:
                self.log.milestone(p, "生日，%d 岁" % p.age, "生日")

        # ---- 环境 / 持续效果结算 ----
        self.roll_ambient()
        self.settle_carried(report)
        # ---- 人生阶段推进（生日后可能升学/毕业）----
        self.auto_progress_stages(report)
        if self.check_death(report):
            self.last_report = report
            self.pending = None
            self._log_delta(report)
            return {"tone": "dead", "text": "\n".join(report.lines), "report": report}

        # ---- 新的一天：重置行动点（游戏内同一天最多 8 次操作）----
        p.action_points = ACTION_POINTS_PER_DAY
        p.actions_today = 0
        p.action_tally = {}
        p.stats.pop("exercise_today", None)

        # ---- 抽取今日事件 ----
        pick = None
        illness_note = ""
        if forced_event is None:
            # 1) 生病机会（独立的每日判定，遵守最短间隔）
            sick, iroll, illness_note = self.roll_illness_opportunity()
            report.add_line(illness_note)
            if sick:
                illness_event = self._pick_illness_event()
                if illness_event is not None:
                    pick = {"event": illness_event, "category": "疾病",
                            "roll": iroll, "secret_reason": None,
                            "internal": illness_event["id"], "no_event": False}
            # 2) 普通事件（万分位精度：先判"今天有没有事"）
            if pick is None:
                pick = roll_daily_event(self.dice, p, engine=self)

        if forced_event is not None:
            pick = {"event": forced_event, "category": "隐藏",
                    "roll": self.dice.d100("生日事件"),
                    "secret_reason": "今天是你的生日，触发特殊事件。",
                    "internal": forced_event["id"], "no_event": False}

        event = pick.get("event") if pick else None
        if event is None:
            p.plain_days += 1
            chance = pick.get("chance") if pick else None
            report.add_line("今天什么也没有发生，日子平静地流过。")
            if chance is not None:
                report.add_line("（当日事件概率 %.2f%%，判定结果：无事发生）" % (chance * 100))
            report.event_name = "平静的一天"
            p.remember_event("平静的一天", "日常", "无事件")
            self.last_report = report
            self._log_delta(report)
            return {"tone": "nothing", "text": "\n".join(report.lines),
                    "report": report, "action_points": p.action_points,
                    "illness_note": illness_note}

        desc = self.dice.pick(event["descs"], "事件描述")[0] if len(event["descs"]) > 1 else event["descs"][0]
        desc = desc.replace("{name}", p.name).replace("{age}", str(p.age))
        report.event_name = event["name"]
        p.remember_event(event["name"], event["category"], desc)
        # 记录同类事件冷却
        if event["category"] in CATEGORY_BANDS_NAMES:
            self.category_last_day[event["category"]] = p.total_days

        card = {
            "tone": "event",
            "report": report,
            "event_id": event["id"],
            "event_name": event["name"],
            "category": event["category"],
            "tone_color": TRUE_TONE_COLORS.get(event["tone"], "#f0c040"),
            "special": event["special"],
            "desc": desc,
            "choices": [],
            "secret_reason": pick.get("secret_reason"),
            "roll_lines": self.dice.today_lines(),
            "settlement_lines": list(report.lines),
            "action_points": p.action_points,
            "illness_note": illness_note,
        }

        for idx, choice in enumerate(event["choices"]):
            hints = describe_effects(choice.get("outcomes", [{}])[0].get("effects", {}))
            card["choices"].append({
                "index": idx,
                "label": choice["label"],
                "hint": choice.get("hint", ""),
                "detail": "、".join(hints),
                "need_money": choice.get("need_money", 0),
                "need_disease": choice.get("need_disease", False),
                "roll": choice.get("roll", "d6"),
            })
        self.pending = {"event": event, "card": card, "report": report,
                        "followup": None}
        return card

    def _pick_illness_event(self):
        """
        生病机会命中时，挑选一个合适的疾病类事件（作为当天的"不舒服"叙事入口）。
        优先挑选轻症事件（感冒/肠胃/流感），重症留给事件链。
        """
        p = self.player
        candidates = []
        for eid in ("illness_cold", "illness_gastro", "illness_seasonal",
                    "illness_frostbite", "illness_heatstroke", "illness_pneumonia",
                    "illness_chronic", "baby_sick_care"):
            ev = EVENTS.get(eid)
            if ev is None:
                continue
            try:
                if not ev["cond"](p):
                    continue
            except Exception:
                continue
            # 重症/慢性病只在体质弱或年纪大时才优先
            if eid in ("illness_pneumonia", "illness_chronic"):
                if not (p.constitution < 35 or p.age >= 60 or p.age <= 3):
                    continue
            candidates.append(ev)
        if not candidates:
            return None
        # 用权重抽取（轻症权重更高）
        weights = {"illness_cold": 40, "illness_gastro": 25, "illness_seasonal": 20,
                   "illness_frostbite": 12, "illness_heatstroke": 12,
                   "illness_pneumonia": 8, "illness_chronic": 6, "baby_sick_care": 30}
        total = float(sum(weights.get(e["id"], 10) for e in candidates))
        res = self.dice.roll(10000, 1, 0, "疾病类型挑选")
        target = (res.value - 0.5) / 10000.0 * total
        acc = 0.0
        for ev in candidates:
            acc += weights.get(ev["id"], 10)
            if target <= acc:
                return ev
        return candidates[-1]

    # ------------------------------------------------------------------
    def resolve_choice(self, choice_index):
        """
        处理玩家在事件弹窗里的选择：
        掷骰判定结果 → 应用效果 → 疾病 / 体温 / 情绪结算 → 生成结果卡。
        """
        if self.pending is None:
            return {"tone": "nothing", "text": "当前没有待处理的事件。"}
        event = self.pending["event"]
        report = self.pending["report"]
        choices = event["choices"]
        if choice_index < 0 or choice_index >= len(choices):
            choice_index = 0
        choice = choices[choice_index]
        p = self.player

        # ---- 付费选项的金钱校验（友好提示，不崩溃）----
        need_money = float(choice.get("need_money", 0) or 0)
        if need_money > 0 and p.money < need_money:
            # 允许硬扛类选项兜底；若没有兜底选项则由界面提示
            fallback = next((i for i, c in enumerate(choices)
                             if float(c.get("need_money", 0) or 0) <= p.money), None)
            if fallback is None:
                return {"tone": "warn",
                        "text": "金钱不足：该选项需要 %.2f，你当前只有 %.2f。\n"
                                "请选择其它选项或先想办法赚钱。" % (need_money, p.money)}
            choice_index = fallback
            choice = choices[choice_index]

        outcome, roll = resolve_outcome(self.dice, choice)
        self.dice.remember(roll, "%s·结果判定" % event["name"])
        effects = dict(outcome.get("effects") or {})

        # 隐藏骰点的额外彩蛋：d100=100 时追加奖励，=1 时追加惩罚
        bonus_lines = []
        if roll.faces == 100 and roll.value == 100:
            effects = merge_effect(effects, {"money": 2000, "happy": 6})
            bonus_lines.append("【隐藏·骰运加身】满值骰点带来额外好运：金钱 +2000，幸福 +6。")
        elif roll.faces == 100 and roll.value == 1:
            effects = merge_effect(effects, {"health": -3, "happy": -3})
            bonus_lines.append("【隐藏·骰运反噬】大失败骰点带来额外打击：健康 -3，幸福 -3。")

        delta, notes = p.apply_effects(effects, dice=self.dice)
        report.accumulate(delta)

        lines = list(bonus_lines)
        if outcome.get("desc"):
            lines.append(outcome["desc"])
        lines.extend(notes)
        if roll.hidden:
            lines.append(roll.hidden)

        report.add_line("【%s】%s" % (event["name"], outcome.get("desc", "")))
        for note in notes:
            report.add_line("    · %s" % note)

        # ---- 连锁事件 ----
        followup = outcome.get("next_event")
        if followup and followup in EVENTS:
            self.pending_followup = followup

        # ---- 人生节点记录 ----
        self._record_milestones(event, outcome, delta)

        # ---- 当天其余结算（事件已处理完毕，清空待处理状态，允许继续当天操作/推进新的一天）----
        result_card = self._finish_day(report, keep_pending=False)
        result_card.update({
            "tone": "result",
            "event_name": event["name"],
            "outcome_desc": outcome.get("desc", ""),
            "delta": delta,
            "dice_lines": ["%s %s" % (choice["label"], roll)] + (
                ["隐藏骰点：%s" % roll.hidden] if roll.hidden else []),
            "extra_lines": lines,
            "roll": roll,
            "special": bool(event["special"]),
            "followup": followup,
        })
        return result_card

    def _record_milestones(self, event, outcome, delta):
        """把重大人生节点写进大事记与日志。"""
        p = self.player
        text = outcome.get("desc", "")
        tags = event.get("tags", [])
        if event["id"] == "love_marriage" and p.married:
            p.add_milestone("结婚", tag="婚姻")
            self.log and self.log.milestone(p, "结婚", "婚姻")
        if event["id"] == "love_child" and p.children > 0:
            p.add_milestone("迎来第 %d 个孩子" % p.children, tag="家庭")
            self.log and self.log.milestone(p, "迎来第 %d 个孩子" % p.children, "家庭")
        if event["id"] in ("work_unemployed",) and not p.employed:
            p.add_milestone("失业", tag="事业")
            self.log and self.log.milestone(p, "失业", "事业")
        if event["id"] == "work_gain_job" and p.employed:
            p.add_milestone("入职工作（职级 %d）" % p.job_level, tag="事业")
            self.log and self.log.milestone(p, "入职工作（职级 %d）" % p.job_level, "事业")
        if "disease" in tags:
            worst = p.worst_disease()
            if worst:
                if self.log:
                    self.log.disease(p, "患上/恶化：%s" % worst["name"])
                if DISEASE_SEVERITY.get(worst["id"], 0) >= 4:
                    p.add_milestone("重病：%s" % worst["name"], tag="疾病")
                    self.log and self.log.milestone(p, "重病：%s" % worst["name"], "疾病")
        if event["special"]:
            p.add_milestone("【%s】%s" % (event["name"], text[:40]), tag="奇遇")

    # ------------------------------------------------------------------
    def _finish_day(self, report, keep_pending=False):
        """事件结算之后的收尾：疾病 → 体温 → 情绪 → 衰老 → 恢复 → 抢救 → 死亡 → 日志。"""
        self.settle_disease_phase(report)
        if not self.player.dead:
            self.settle_env_phase(report)
        if not self.player.dead:
            self.settle_mood_phase(report)
        if not self.player.dead:
            self.settle_aging_phase(report)
        if not self.player.dead:
            self.settle_recover_phase(report)
        if not self.player.dead:
            self.settle_hospital_phase(report)
        dead = self.check_death(report)
        self.last_report = report
        self._log_delta(report)
        if not keep_pending:
            self.pending = None
        if dead:
            self.pending = None
        return {
            "tone": "dead" if dead else "day_end",
            "report": report,
            "death": dead,
            "settlement_lines": list(report.lines),
        }

    # ------------------------------------------------------------------
    # 每日操作（休息 / 工作 / 娱乐）
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 行动点系统（游戏内同一天最多 8 次操作）
    # ------------------------------------------------------------------
    def action_points_left(self):
        return max(0, int(getattr(self.player, "action_points", 0)))

    def action_cost(self, action_key):
        return int(ACTION_COST.get(action_key, 2))

    def action_decay(self, action_key):
        """
        同一天内重复做同一件事的收益衰减：
        第 2 次 85%，第 3 次 72%……最低 40%。
        """
        used = int((self.player.action_tally or {}).get(action_key, 0))
        if used <= 0:
            return 1.0
        factor = ACTION_REPEAT_DECAY ** used
        return max(ACTION_REPEAT_FLOOR, factor)

    def can_do_action(self, action_key):
        """
        检查能否执行某个操作，返回 (是否允许, 提示文本)。
        """
        p = self.player
        if p.dead:
            return False, "人物已经离世。"
        if self.pending is not None:
            return False, "当前有事件尚未处理，请先做出选择。"
        cost = self.action_cost(action_key)
        if p.action_points < cost:
            return False, ("今天的行动点不够了（需要 %d 点，剩余 %d 点）。\n"
                           "每个游戏内的一天最多 8 点行动点；\n"
                           "可以点「跳过这一天」直接进入第二天。"
                           % (cost, p.action_points))
        return True, ""

    def apply_daily_action(self, action_key):
        """
        在**当天**执行一次操作（休息 / 工作 / 娱乐 / 学习 / 社交 / 锻炼）。
        重要：操作**不会推进日期**，只消耗行动点；一天最多 8 点。
        只有 step_roll()（推进一天）或 skip_day()（跳过这一天）才进入第二天。
        返回结果卡 dict。
        """
        p = self.player
        if p.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        ok, why = self.can_do_action(action_key)
        if not ok:
            return {"tone": "warn", "text": why}

        cost = self.action_cost(action_key)
        decay = self.action_decay(action_key)
        p.action_points -= cost
        p.actions_today += 1
        p.stats["actions_total"] = p.stats.get("actions_total", 0) + 1
        tally = dict(p.action_tally or {})
        tally[action_key] = int(tally.get(action_key, 0)) + 1
        p.action_tally = tally

        report = DailyReport(p)
        title = ACTION_LABELS.get(action_key, action_key)
        repeat_note = ""
        if decay < 0.999:
            repeat_note = "（今天第 %d 次做这件事，效果只有 %.0f%%）" % (
                tally[action_key], decay * 100)
            report.add_line(repeat_note)

        if action_key == "rest":
            self._do_rest(report, decay)
        elif action_key == "work":
            self._do_work(report, decay)
        elif action_key == "fun":
            result = self._do_fun(report, decay)
            if result is not None:
                # 金钱不足等情况：退回行动点
                p.action_points += cost
                p.actions_today = max(0, p.actions_today - 1)
                tally[action_key] = max(0, tally[action_key] - 1)
                p.action_tally = tally
                return result
        elif action_key == "study":
            self._do_study(report, decay)
        elif action_key == "social":
            self._do_social(report, decay)
        elif action_key == "exercise":
            self._do_exercise(report, decay)
        else:
            p.action_points += cost
            p.actions_today = max(0, p.actions_today - 1)
            return {"tone": "warn", "text": "未知的操作：%s" % action_key}

        # 操作只影响当天状态，不做日期推进；但会做一次"当天身体反应"
        if not p.dead:
            self.settle_env_phase(report)
        if not p.dead:
            self.settle_recover_phase(report)
        self.check_death(report)
        self.last_report = report
        return {
            "tone": "dead" if p.dead else "action",
            "title": title,
            "report": report,
            "settlement_lines": list(report.lines),
            "dice_lines": self.dice.today_lines(),
            "death": p.dead,
            "action_points": p.action_points,
            "actions_today": p.actions_today,
        }

    def _do_rest(self, report, decay=1.0):
        p = self.player
        roll = self.dice.d10("休息效果")
        self.dice.remember(roll, "休息效果")
        heal = (4 + roll.value // 2) * decay
        happy_gain = (1 + roll.value // 4) * decay
        effects = {"health_boost": heal, "happy": happy_gain, "temp": (36.5 - p.temp) * 0.5}
        if roll.value >= 9:
            report.add_line("你睡了一个难得的好觉，醒来神清气爽。")
            effects["happy"] = happy_gain + 4 * decay
        elif roll.value <= 2:
            report.add_line("夜里翻来覆去，休息效果一般。")
            effects["health_boost"] = max(1.0, heal - 3)
        boredom = (1.0 - min(0.55, p.stats.get("rest_streak", 0) * 0.12))
        if boredom < 0.99:
            effects["health_boost"] = max(1.0, round(effects["health_boost"] * boredom, 2))
            effects["happy"] = round(effects["happy"] * boredom, 2)
            report.add_line("连续休息让你有些烦闷，恢复效果只有平时的 %d%%。" % (boredom * 100))
        delta, _ = p.apply_effects(effects, dice=self.dice)
        p.stats["days_rested"] += 1
        p.stats["rest_streak"] = p.stats.get("rest_streak", 0) + 1
        report.accumulate(delta)
        report.add_line("休息：健康 %s，幸福 %s，体温 %s" % (
            fmt_signed(delta["health"], 1), fmt_signed(delta["happy"], 1),
            fmt_signed(delta["temp"], 2)))

    def _do_work(self, report, decay=1.0):
        p = self.player
        stage = p.stage
        if p.age < 6:
            report.add_line("你还是个婴幼儿，只能在家里玩。")
            delta, _ = p.apply_effects({"happy": +2 * decay}, dice=self.dice)
            report.accumulate(delta)
            return
        if p.age < 16 or stage in ("primary", "middle", "kindergarten", "preschool"):
            # 学生时代：只能做点零工/跑腿，收入微薄，也不太伤身体
            roll = self.dice.d10("零工收益")
            self.dice.remember(roll, "零工收益")
            income = round((20.0 + 12.0 * roll.value) * decay, 2)
            cost_health = 0.8 + roll.value / 10.0
            delta, _ = p.apply_effects({"money": income, "health": -cost_health},
                                       dice=self.dice)
            p.stats["days_worked"] += 1
            report.accumulate(delta)
            report.add_line("打零工收入 %.2f，健康 %s（未成年/在读，收入有限）" % (
                income, fmt_signed(delta["health"], 1)))
            return
        roll = self.dice.d20("工作收益")
        self.dice.remember(roll, "工作收益")
        base = (80.0 + 30.0 * p.job_level) * (0.6 + roll.value / 20.0)
        if p.age >= 60:
            base *= 0.65
        elif not p.employed:
            base *= 0.7
        elif p.job_level == 0:
            base *= 0.8
        income = round(base * decay, 2)
        cost_health = (2.5 + roll.value / 6.0) / max(0.6, decay)
        if roll.value >= 19:
            income *= 1.8
            report.add_line("今天的工作异常顺利，客户当场追加了订单！")
        elif roll.value <= 2:
            cost_health += 3
            report.add_line("今天诸事不顺，还被上司说了一顿。")
        if p.age < 6:
            income = round(income * 0.15, 2)
        delta, _ = p.apply_effects(
            {"money": income, "health": -cost_health, "happy": -1}, dice=self.dice)
        p.stats["days_worked"] += 1
        report.accumulate(delta)
        report.add_line("工作收入 %.2f，健康 %s" % (income, fmt_signed(delta["health"], 1)))
        if p.diseases:
            report.add_line("（带病工作让身体更吃力……）")
        p.stats["rest_streak"] = 0

    def _do_fun(self, report, decay=1.0):
        """娱乐消费：金钱不足时返回提示卡（由上层退回行动点）。"""
        p = self.player
        roll = self.dice.d10("娱乐效果")
        self.dice.remember(roll, "娱乐效果")
        cost = round((120.0 + 60.0 * roll.value + 80.0 * max(0, p.job_level)) * decay, 2)
        if p.money > 20000:
            cost = round(cost * (1.0 + min(1.5, p.money / 60000.0)), 2)
        if p.money < cost:
            cheap = round(max(0.0, p.money * 0.35), 2)
            if cheap < 20:
                return {"tone": "warn",
                        "text": "金钱不足：娱乐消费需要 %.2f，你只有 %.2f。\n"
                                "建议先选择「工作赚钱」，或直接「跳过这一天」。\n"
                                "（身无分文的你什么也玩不了。）" % (cost, p.money)}
            report.add_line("你口袋里的钱不够原本的计划，只好改成低成本消遣。")
            cost = cheap
        happy_gain = (4 + roll.value + (3 if p.married or p.children else 0)) * decay
        delta, _ = p.apply_effects(
            {"money": -cost, "happy": happy_gain, "health": +1 * decay}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("娱乐消费 %.2f，幸福 %s" % (cost, fmt_signed(delta["happy"], 1)))
        p.stats["rest_streak"] = 0
        return None

    def _do_study(self, report, decay=1.0):
        """学习充电：积累学业表现（影响中考/高考/考研），消耗精力。"""
        p = self.player
        if p.age < 5:
            report.add_line("你还太小，只能看看图画书。")
            delta, _ = p.apply_effects({"happy": +1}, dice=self.dice)
            report.accumulate(delta)
            return
        roll = self.dice.d10("学习效果")
        self.dice.remember(roll, "学习效果")
        gain = int(round((1 + roll.value / 2.0) * decay))
        p.stats["study_points"] = p.stats.get("study_points", 0) + gain
        cost_health = 0.5 + roll.value / 20.0
        delta, _ = p.apply_effects({"health": -cost_health, "happy": -1}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("学习收获 %d 点学业表现（累计 %d），健康 %s" % (
            gain, p.stats["study_points"], fmt_signed(delta["health"], 1)))
        p.stats["rest_streak"] = 0

    def _do_social(self, report, decay=1.0):
        """社交联络：花钱提升幸福，可能带来机会。"""
        p = self.player
        if p.age < 4:
            report.add_line("你还不会说话，只能对着家人笑。")
            delta, _ = p.apply_effects({"happy": +2}, dice=self.dice)
            report.accumulate(delta)
            return
        roll = self.dice.d10("社交效果")
        self.dice.remember(roll, "社交效果")
        cost = round((60.0 + 40.0 * roll.value) * decay, 2)
        if p.money < cost:
            report.add_line("手头太紧，只能和家人聊聊天。")
            cost = 0.0
        happy_gain = (3 + roll.value * 0.8) * decay
        effects = {"money": -cost, "happy": happy_gain}
        if roll.value >= 9:
            effects["health"] = +1
            report.add_line("和朋友聊得很开心，还约好一起运动。")
        delta, _ = p.apply_effects(effects, dice=self.dice)
        report.accumulate(delta)
        report.add_line("社交花费 %.2f，幸福 %s" % (cost, fmt_signed(delta["happy"], 1)))
        p.stats["rest_streak"] = 0

    def _do_exercise(self, report, decay=1.0):
        """锻炼身体：小幅提升健康，并降低短期患病风险（改善体质表现）。"""
        p = self.player
        if p.age < 5:
            report.add_line("你在院子里跑来跑去，玩得满头是汗。")
            delta, _ = p.apply_effects({"health": +1, "happy": +1}, dice=self.dice)
            report.accumulate(delta)
            return
        if p.health < 25:
            report.add_line("身体太虚，强行锻炼反而吃不消。")
            delta, _ = p.apply_effects({"health": -1}, dice=self.dice)
            report.accumulate(delta)
            return
        roll = self.dice.d10("锻炼效果")
        self.dice.remember(roll, "锻炼效果")
        heal = (1.0 + roll.value / 6.0) * decay
        delta, _ = p.apply_effects({"health_boost": heal, "happy": +1 * decay,
                                    "temp": (36.5 - p.temp) * 0.3}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("锻炼：健康 %s（体质 %d 分）" % (
            fmt_signed(delta["health"], 1), int(round(p.constitution))))
        # 当天锻炼会略微降低当天的患病概率
        p.stats["exercise_today"] = p.stats.get("exercise_today", 0) + 1
        p.stats["rest_streak"] = 0

    # ------------------------------------------------------------------
    # 推进一天 / 跳过这一天
    # ------------------------------------------------------------------
    def skip_day(self, reason="今天什么也不做"):
        """
        「跳过这一天」：不消耗行动点，直接进入第二天（一天只能触发一次事件，
        跳过时会先掷骰判定当天是否发生事件；若已处理过事件则直接结束当天）。
        """
        p = self.player
        if p.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        if self.pending is not None:
            return {"tone": "warn", "text": "当前有事件尚未处理，请先做出选择。"}
        p.stats["skipped_days"] = p.stats.get("skipped_days", 0) + 1
        return self.end_day(reason=reason, allow_event=True)

    def end_day(self, reason="推进一天", allow_event=True):
        """
        结束当天：推进日期、跨月/跨年结算、阶段推进、环境与疾病结算。
        一天最多只掷骰触发一次事件（allow_event 控制）。
        """
        p = self.player
        report = DailyReport(p)
        p.stats["days_played"] = p.stats.get("days_played", 0) + 1
        calendar_notes, birthday = self.advance_calendar()
        p.days_played += 1

        for kind, value in calendar_notes:
            if kind == "month":
                self.settle_month(report)
                self.settle_family_phase(report)
                p.add_milestone("进入第 %d 月" % value, tag="时间")
            elif kind == "year":
                p.add_milestone("满 %d 岁" % p.age, tag="年龄")
                report.add_line("★ 你满 %d 岁了（%s阶段）。" % (
                    p.age, stage_name(p.stage)))
        if birthday:
            p.add_milestone("生日（%d 岁）" % p.age, tag="生日")
            report.add_line("🎂 今天是你的生日。")
            delta, _ = p.apply_effects({"happy": +3}, dice=self.dice)
            report.accumulate(delta)

        self.roll_ambient()
        self.settle_carried(report)
        self.auto_progress_stages(report)
        if self.check_death(report):
            self.last_report = report
            self.pending = None
            self._log_delta(report)
            return {"tone": "dead", "text": "\n".join(report.lines), "report": report}

        # ---- 新的一天：重置行动点 ----
        p.action_points = ACTION_POINTS_PER_DAY
        p.actions_today = 0
        p.action_tally = {}
        p.stats.pop("exercise_today", None)

        self.last_report = report
        self.pending = None
        return {
            "tone": "dead" if p.dead else "day_end",
            "report": report,
            "death": p.dead,
            "settlement_lines": list(report.lines),
            "action_points": p.action_points,
        }

    # ------------------------------------------------------------------
    # 时间跳跃：按天 / 按月 / 按年跳过（只做合理汇总，不生成逐日事件）
    # ------------------------------------------------------------------
    def skip_time(self, days=0, months=0, years=0):
        """
        跳过一段时间。为保持合理性与性能，跳过期间**不生成逐日事件**，
        只做数值汇总：
          * 按天推进日期与月度结算（工资、生活支出、家庭供养）
          * 疾病按天结算（可能自愈/恶化/治愈）
          * 环境与体温按"平均值"结算，不做极端随机
          * 到年龄节点自动推进人生阶段
        返回结果卡 dict（含汇总文本）。
        """
        p = self.player
        if p.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        total_days = int(days) + int(months) * DAYS_PER_MONTH + int(years) * DAYS_PER_YEAR
        if total_days <= 0:
            return {"tone": "warn", "text": "跳过的时长必须大于 0。"}
        max_days = SKIP_MAX_YEARS * DAYS_PER_YEAR
        if total_days > max_days:
            total_days = max_days
        report = DailyReport(p)
        report.event_name = "时间跳跃"
        report.add_line("【时间跳跃】开始跳过 %d 天（约 %.1f 年）……" % (
            total_days, total_days / float(DAYS_PER_YEAR)))
        p.stats["skipped_days"] = p.stats.get("skipped_days", 0) + total_days

        start_money = p.money
        start_health = p.health
        start_age = p.age
        illnesses = 0
        cured = 0
        months_passed = 0
        day_count = 0

        while day_count < total_days and not p.dead:
            calendar_notes, birthday = self.advance_calendar()
            day_count += 1
            p.days_played += 1
            p.stats["days_played"] = p.stats.get("days_played", 0) + 1
            for kind, _value in calendar_notes:
                if kind == "month":
                    self.settle_month(report)
                    self.settle_family_phase(report)
                    months_passed += 1
                elif kind == "year":
                    p.add_milestone("满 %d 岁" % p.age, tag="年龄")
            if birthday:
                p.add_milestone("生日（%d 岁）" % p.age, tag="生日")
            self.auto_progress_stages(report)
            # 疾病按天结算（仍然遵守自愈/恶化规则）
            if p.diseases:
                self.settle_disease_phase(report)
            if p.dead:
                break
            # 时间跳跃期间的"平均环境"：每 10 天做一次温和结算，避免逐日开销过大
            if day_count % 10 == 0:
                self.roll_ambient()
                self.settle_env_phase(report)
                self.settle_mood_phase(report)
                self.settle_aging_phase(report)
                self.settle_recover_phase(report)
                self.settle_hospital_phase(report)
            self.check_death(report)

        illnesses = max(0, p.stats.get("disease_count", 0) - 0)
        report.add_line("跳过后：%s（%d 岁，%s阶段）" % (p.date_full, p.age, stage_name(p.stage)))
        report.add_line("数值汇总：健康 %s，幸福 %s，金钱 %s，体温 %.2f℃" % (
            fmt_signed(p.health - start_health, 1), fmt_signed(0, 0),
            fmt_signed(p.money - start_money, 2), p.temp))
        report.add_line("经历 %d 个月结算，疾病累计 %d 次，学历/阶段：%s" % (
            months_passed, p.stats.get("disease_count", 0), stage_name(p.stage)))
        p.add_milestone("跳过 %d 天（到 %d 岁）" % (total_days, p.age), tag="时间")
        self.last_report = report
        return {
            "tone": "dead" if p.dead else "skip",
            "title": "时间跳跃",
            "report": report,
            "settlement_lines": list(report.lines),
            "death": p.dead,
            "days": day_count,
            "action_points": p.action_points,
        }

    # ------------------------------------------------------------------
    def try_cure(self, disease_id=None):
        """
        主界面/菜单的「花钱治病」入口。
        返回 (是否成功, 提示文本, 花费)
        """
        p = self.player
        if not p.diseases:
            return False, "你目前没有疾病，不需要治疗。", 0.0
        target = (next((d for d in p.diseases if d["id"] == disease_id), None)
                  if disease_id else p.worst_disease())
        if target is None:
            return False, "没有找到对应的疾病。", 0.0
        cost = float(target["cure_cost"])
        if p.money < cost:
            return False, ("金钱不足：治疗%s需要 %.2f，你只有 %.2f。\n"
                           "可以选择「工作赚钱」攒钱，或者靠身体硬扛。"
                           % (target["name"], cost, p.money)), cost
        ok, msg, paid = p.cure_disease(target["id"])
        if ok:
            p.add_milestone("治愈%s（花费 %.2f）" % (target["name"], paid), tag="疾病")
            if self.log:
                self.log.disease(p, "治愈%s（花费 %.2f）" % (target["name"], paid))
        return ok, msg, paid

    # ------------------------------------------------------------------
    def finish_life(self):
        """人物死亡后生成人生总结（只生成一次）。"""
        p = self.player
        if not p.dead:
            return ""
        if p.summary_done:
            return "（人生总结已生成）"
        p.summary_done = True
        if self.log:
            return self.log.life_summary(p)
        return ""

    # ------------------------------------------------------------------
    def status_panel(self):
        """生成当前状态面板文本（供菜单/界面显示）。"""
        p = self.player
        city = get_city(p.city)
        con_name, con_desc = constitution_tier(p.constitution)
        fam_name, fam_desc, fam_support = family_tier(p.family_wealth)
        stage = STAGE_BY_ID.get(p.stage) or {}
        lines = []
        lines.append("姓名：%s        城市：%s（%s）" % (p.name, city["name"], city["tag"]))
        lines.append("时间：%s        当日气温：%.1f℃（%s）" % (
            p.date_full, p.ambient_temp, season_name(p.month)))
        lines.append("-" * 52)
        lines.append("人生阶段：%s（%d 岁）" % (stage.get("name", "?"), p.age))
        lines.append("    %s" % stage.get("desc", ""))
        lines.append("学历：%s" % ("、".join(p.education) if p.education else "尚未入学"))
        if p.exam_results:
            lines.append("考试结果：%s" % "；".join(
                "%s=%s" % (k, v) for k, v in p.exam_results.items()))
        lines.append("学业表现：%d 点        行动点：%d / %d（今天已操作 %d 次）" % (
            p.stats.get("study_points", 0), p.action_points, ACTION_POINTS_PER_DAY,
            p.actions_today))
        lines.append("-" * 52)
        lines.append("体质：%.1f 分（%s）—— %s" % (p.constitution, con_name, con_desc))
        lines.append("    易感倍率 %.2f 倍，预计每年生病 %.2f 次" % (
            constitution_susceptibility(p.constitution), illness_per_year(p.age, p.constitution)))
        lines.append("家境：%.1f 分（%s）—— %s" % (p.family_wealth, fam_name, fam_desc))
        support = family_support_amount(p)
        if p.family_bankrupt:
            lines.append("    【家庭已破产】父母无法再提供任何经济支持")
        elif support > 0:
            lines.append("    父母每月供养 %.2f（成年/毕业前由家庭承担开销）" % support)
        else:
            lines.append("    已独立，不再接受家庭供养")
        lines.append("-" * 52)
        lines.append("当前状态：%s" % p.status_text)
        for name, value, note, _color in p.attribute_rows():
            lines.append("%-4s：%-14s %s" % (name, value, note))
        lines.append("-" * 52)
        lines.append("疾病：%s" % p.disease_names())
        for d in p.diseases:
            lines.append("    · %s（%s）剩余 %d 天，每日健康 -%.1f，治愈费 %.0f" % (
                d["name"], d["kind"], d["days"], d["hp_per_day"], d["cure_cost"]))
        lines.append("工作：%s（职级 %d）        婚恋：%s        子女：%d 人" % (
            "在职" if p.employed else "无业", p.job_level,
            "已婚" if p.married else "单身", p.children))
        lines.append("身价估算：%.2f" % p.net_worth())
        lines.append("统计：度过 %d 天（平凡 %d 天）/ 操作 %d 次 / 患病 %d 次 / 治愈 %d 次" % (
            p.total_days, p.plain_days, p.stats.get("actions_total", 0),
            p.stats.get("disease_count", 0), p.stats.get("cure_count", 0)))
        lines.append("家庭累计供养：%.2f" % p.stats.get("family_support_total", 0.0))
        if p.carried_effects:
            lines.append("持续效果：")
            for item in p.carried_effects:
                lines.append("    · %s（剩余 %d 天）" % (item.get("name", "效果"), item.get("days", 0)))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def diary_panel(self, count=60):
        """返回最近的人生日志（用于界面回看）。"""
        if self.log:
            return "\n".join(self.log.tail_lines(count))
        return "（暂无日志）"
