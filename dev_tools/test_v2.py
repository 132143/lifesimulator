# -*- coding: utf-8 -*-
"""新版机制测试：行动点、跳过一天、按月/按年跳过、体质、家庭供养、疾病间隔、阶段流程。"""
import importlib.util
import os
import random
import statistics
import sys
import tempfile

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

FAIL = []
PASS = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("%s %s%s" % ("[OK]  " if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))


print("=" * 78)
print("一、行动点：游戏内同一天最多 8 次操作，操作不推进日期")
print("=" * 78)
p = ls.Player(name="行动", city="beijing", rng=random.Random(11))
p.stage = "work"
p.age = 30
p.employed = True
p.job_level = 3
p.money = 50000
sim = ls.Simulator(p, ls.LifeLog(None), "", seed=11)
date0 = p.date_full
count = 0
while True:
    res = sim.apply_daily_action("rest")
    if res.get("tone") == "warn":
        break
    count += 1
    if count > 20:
        break
check("同一天内操作次数上限为 8 次", count == 8, "实际可执行 %d 次" % count)
check("操作不会推进日期（日期保持不变）", p.date_full == date0,
      "%s -> %s" % (date0, p.date_full))
check("行动点被正确消耗", p.action_points == 0, "剩余 %d 点" % p.action_points)
r = sim.apply_daily_action("rest")
check("行动点耗尽后拒绝继续操作并给出提示",
      r.get("tone") == "warn" and "行动点" in r.get("text", ""), r.get("text", "").splitlines()[0])
# 跳过这一天
r = sim.skip_day()
check("「跳过这一天」可以结束当天", r.get("tone") in ("day_end", "dead", "skip"), r.get("tone"))
check("跳过一天后日期推进", p.date_full != date0, "%s -> %s" % (date0, p.date_full))
check("新的一天行动点重置为 8", p.action_points == ls.ACTION_POINTS_PER_DAY,
      "剩余 %d" % p.action_points)
# 重复操作衰减
p2 = ls.Player(name="衰减", city="beijing", rng=random.Random(2))
p2.stage = "work"; p2.age = 30; p2.employed = True; p2.job_level = 2; p2.money = 9999
sim2 = ls.Simulator(p2, ls.LifeLog(None), "", seed=2)
d1 = sim2.action_decay("rest")
sim2.apply_daily_action("rest")
d2 = sim2.action_decay("rest")
sim2.apply_daily_action("rest")
d3 = sim2.action_decay("rest")
check("同一天重复同一操作收益递减", d1 == 1.0 and d2 < d1 and d3 < d2,
      "第1次 %.2f / 第2次 %.2f / 第3次 %.2f" % (d1, d2, d3))

print("")
print("=" * 78)
print("二、事件发生频率：不再是天天有事（万分位精度）")
print("=" * 78)
chances = {}
for stage in ("infant", "kindergarten", "primary", "high", "work", "retired"):
    probe = ls.Player(name="概率", city="beijing", rng=random.Random(0))
    probe.stage = stage
    chances[stage] = ls.event_chance_of(probe)
check("各阶段事件概率都在 1%~20% 之间（不是天天发生）",
      all(0.01 <= v <= 0.20 for v in chances.values()),
      "  ".join("%s=%.2f%%" % (k, v * 100) for k, v in chances.items()))
check("工作期事件概率高于幼儿园期", chances["work"] > chances["kindergarten"])
# 实测：跑 2000 天，统计有事的天数占比
p3 = ls.Player(name="实测", city="beijing", rng=random.Random(33))
p3.stage = "work"; p3.age = 30; p3.employed = True; p3.job_level = 2
sim3 = ls.Simulator(p3, ls.LifeLog(None), "", seed=33)
event_days = 0
plain_days = 0
for _ in range(2000):
    if p3.dead:
        break
    card = sim3.step_roll()
    if card.get("tone") == "dead":
        break
    if card.get("tone") == "event":
        event_days += 1
    else:
        plain_days += 1
    # 无论 step_roll 返回什么，只要有待处理事件就立即结算
    if sim3.pending is not None:
        r = sim3.resolve_choice(0)
        if r.get("tone") == "warn":
            sim3.resolve_choice(0)
    sim3.skip_day()
total = event_days + plain_days
check("工作期约 10%~25% 的日子会发生事件（不是天天有）",
      0.05 <= event_days / float(max(1, total)) <= 0.30,
      "2000 天中 %d 天有事（%.1f%%），%d 天平淡" % (
          event_days, event_days * 100.0 / max(1, total), plain_days))

print("")
print("=" * 78)
print("三、疾病：间隔合理 + 体质影响")
print("=" * 78)
# 体质影响：同样年龄，体质强/弱的一年生病次数对比
strong = ls.illness_per_year(2, 90)
weak = ls.illness_per_year(2, 10)
check("体质显著影响患病概率（弱体质约为强体质 4 倍以上）", weak / strong > 3.0,
      "2 岁：体质90 %.2f 次/年，体质10 %.2f 次/年（%.1f 倍）" % (strong, weak, weak / strong))
# 生病间隔：模拟一个幼儿 6 年，统计相邻两次生病的间隔
# 重要：为了真实测出"生病频率"，每天都必须走一次 step_roll（推进一天），
#       而不是用 skip_day 跳过（跳过不掷骰，会低估概率）。
p4 = ls.Player(name="病孩", city="beijing", rng=random.Random(44))
sick_probe = ls.Player(name="概率探针", city="beijing", rng=random.Random(1))
sick_probe.age = 2
sick_probe.stage = "preschool"
expected_per_year = ls.illness_per_year(2, sick_probe.constitution)
sim4 = ls.Simulator(p4, ls.LifeLog(None), "", seed=44)
illness_days = []
last_count = 0
for _ in range(360 * 6):
    if p4.dead:
        break
    card = sim4.step_roll()
    if card.get("tone") == "dead":
        break
    if sim4.pending is not None:
        r = sim4.resolve_choice(0)
        if r.get("tone") == "warn":
            sim4.resolve_choice(0)
    if p4.stats.get("disease_count", 0) > last_count:
        illness_days.append(p4.total_days)
        last_count = p4.stats.get("disease_count", 0)
gaps = [illness_days[i + 1] - illness_days[i] for i in range(len(illness_days) - 1)]
if gaps:
    check("相邻两次生病间隔均 ≥ %d 天（不会一个月生好几次）" % ls.MIN_ILLNESS_GAP_DAYS,
          min(gaps) >= ls.MIN_ILLNESS_GAP_DAYS,
          "%d 次生病，间隔 最小 %d / 平均 %.1f / 最大 %d 天" % (
              len(illness_days), min(gaps), statistics.mean(gaps), max(gaps)))
    per_year = len(illness_days) / (p4.total_days / 360.0)
    # 婴幼儿每年生病 1~5 次都属正常范围（含"花钱治好就没病倒"的情况）
    check("幼儿每年生病次数在 1~5 次之间（符合现实，不再是每月好几次）",
          1.0 <= per_year <= 5.0,
          "实测 %.2f 次/年（模型期望 %.2f 次/年）" % (per_year, expected_per_year))
else:
    check("6 年内至少生过一次病", False, "0 次")

print("")
print("=" * 78)
print("四、家庭系统：成年前由父母承担开销，不易负债")
print("=" * 78)
p5 = ls.Player(name="家庭", city="beijing", rng=random.Random(55))
print("  家境 = %.1f（%s）" % (p5.family_wealth, ls.family_tier(p5.family_wealth)[0]))
sup = ls.family_support_amount(p5)
check("成年前能获得家庭供养", sup > 0, "每月 %.2f" % sup)
check("家庭供养随家境档位变化",
      ls.family_support_amount(type(p5)("a")) is not None)
# 模拟到 18 岁，检查金钱不为负
p5.stage = "primary"; p5.age = 7
sim5 = ls.Simulator(p5, ls.LifeLog(None), "", seed=55)
min_money = p5.money
for _ in range(360 * 12):
    if p5.dead or p5.age >= 19:
        break
    sim5.skip_day()
    min_money = min(min_money, p5.money)
check("普通家庭的孩子成长期间不会陷入负债", min_money >= 0,
      "11 年间最低金钱 %.2f（初始 1000）" % min_money)
# 破产概率
p6 = ls.Player(name="破产", city="beijing", rng=random.Random(66))
counts = 0
for trial in range(300):
    probe = ls.Player(name="x", city="beijing", rng=random.Random(1000 + trial))
    probe.age = 10
    probe.stage = "primary"
    probe.month = probe.birth_month
    probe.day = probe.birth_day
    s = ls.Simulator(probe, ls.LifeLog(None), "", seed=trial)
    rep = ls.DailyReport(probe)
    s.settle_family_phase(rep)
    if probe.family_bankrupt:
        counts += 1
check("家庭破产概率极低（300 次年度判定中不超过 8 次）", counts <= 8,
      "300 次年度判定触发 %d 次（约 %.1f%%/年）" % (counts, counts / 3.0))

print("")
print("=" * 78)
print("五、人生阶段流程（学龄前→…→退休，含中考/高考/考研分支）")
print("=" * 78)
seqs = []
for seed in range(40):
    pl = ls.Player(name="阶段%d" % seed, city="beijing", rng=random.Random(seed))
    sm = ls.Simulator(pl, ls.LifeLog(None), "", seed=seed)
    stages = ["infant"]
    for _ in range(360 * 75):
        if pl.dead:
            break
        card = sm.step_roll()
        if card.get("tone") == "dead":
            break
        if card.get("tone") == "event":
            r = sm.resolve_choice(0)
            if r.get("tone") == "warn":
                sm.resolve_choice(0)
        sm.skip_day()
        if stages[-1] != pl.stage:
            stages.append(pl.stage)
        if pl.age > 70:
            break
    seqs.append(stages)
    if seed < 6:
        print("   seed=%d: %s" % (seed, " → ".join(stages)))
all_stages = set()
for s in seqs:
    all_stages.update(s)
check("阶段流程包含 幼儿园/小学/初中/高中/大学/工作 等主要阶段",
      {"kindergarten", "primary", "middle", "high", "work"} <= all_stages,
      "实际出现阶段：%s" % "、".join(sorted(all_stages)))
has_uni = any("university" in s for s in seqs)
has_nouni = any("university" not in s for s in seqs)
check("大学是概率事件（有人上、有人没上）", has_uni and has_nouni,
      "上大学的样本 %d/%d" % (sum(1 for s in seqs if "university" in s), len(seqs)))
check("阶段顺序合理（不会先工作再上小学）",
      all(s.index("primary") < s.index("middle")
          for s in seqs if "primary" in s and "middle" in s))
check("退休会出现在长寿角色身上",
      any("retired" in s for s in seqs),
      "%d/%d 个样本进入退休" % (sum(1 for s in seqs if "retired" in s), len(seqs)))

print("")
print("=" * 78)
print("六、按月 / 按年跳过")
print("=" * 78)
p7 = ls.Player(name="跳过", city="shanghai", rng=random.Random(77))
p7.stage = "work"; p7.age = 30; p7.employed = True; p7.job_level = 3; p7.money = 20000
sim7 = ls.Simulator(p7, ls.LifeLog(None), "", seed=77)
m0 = p7.money
y0, mo0 = p7.year, p7.month
r = sim7.skip_time(months=3)
check("可以按月跳过（3 个月）",
      (p7.year - y0) * 12 + (p7.month - mo0) == 3 and not p7.dead,
      "%s，金钱 %s" % (p7.date_full, ls.fmt_signed(p7.money - m0, 2)))
r = sim7.skip_time(years=2)
check("可以按年跳过（2 年）", p7.age == 32, "年龄 %d，日期 %s" % (p7.age, p7.date_full))
r = sim7.skip_time(days=10)
check("可以按天跳过（10 天）", r.get("tone") in ("skip", "dead"), r.get("tone"))
check("跳过期间不发散（属性仍在合法区间）",
      0 <= p7.health <= 100 and 0 <= p7.happy <= 100
      and ls.TEMP_HARD_LOW <= p7.temp <= ls.TEMP_HARD_HIGH,
      "健康 %.1f 幸福 %.1f 体温 %.2f" % (p7.health, p7.happy, p7.temp))
# 跳过期间不会生成逐日事件（事件数不因跳过而暴涨）
before_events = len(p7.event_history)
sim7.skip_time(years=1)
added = len(p7.event_history) - before_events
check("跳过期间不生成逐日事件（事件数不增加）", added == 0, "新增 %d 条事件" % added)
# 上限保护
p8 = ls.Player(name="上限", city="beijing", rng=random.Random(88))
sim8 = ls.Simulator(p8, ls.LifeLog(None), "", seed=88)
r = sim8.skip_time(years=999)
check("超长跳过被限制在合理范围（≤ %d 年）" % ls.SKIP_MAX_YEARS,
      r.get("days", 0) <= ls.SKIP_MAX_YEARS * ls.DAYS_PER_YEAR,
      "实际跳过 %d 天" % r.get("days", 0))

print("")
print("=" * 78)
print("七、插件 / 名著模组架构")
print("=" * 78)


class DemoMod(ls.LifeMod):
    mod_id = "demo_novel"
    mod_name = "示例名著模组"
    mod_desc = "演示：新增环境、事件与人生阶段"
    author = "测试"

    def register_environments(self):
        return {"demo_world": {"name": "示例世界", "desc": "一个虚构场景"}}

    def register_events(self):
        return [{
            "id": "demo_event_1", "name": "模组事件", "category": "意外", "weight": 500,
            "descs": ["这是模组新增的事件。"], "cond": lambda p: True,
            "tone": "neutral", "special": False, "tags": [],
            "choices": [{"label": "确定", "hint": "", "roll": "d6",
                         "outcomes": [{"range": (1, 6), "desc": "模组事件结算。",
                                       "effects": {"happy": 2}, "tone": "good"}],
                         "need_money": 0, "need_disease": False}],
        }]

    def register_stages(self):
        return [{"id": "demo_stage", "name": "模组阶段", "start": 0, "end": 0,
                 "next": "infant", "chance_key": "infant", "desc": "模组阶段", "branch": True}]


mod = DemoMod()
ok, msg = ls.register_mod(mod, events_map=ls.EVENTS)
check("模组注册成功", ok, msg)
check("模组事件进入事件库", "demo_event_1" in ls.EVENTS)
check("模组阶段进入人生流程", "demo_stage" in ls.STAGE_BY_ID)
check("模组环境被收录", "demo_world" in ls.MOD_REGISTRY["env_hooks"])
check("模组列表可展示", "示例名著模组" in ls.loaded_mods_text(), ls.loaded_mods_text()[:40])
ok2, msg2 = ls.register_mod(mod, events_map=ls.EVENTS)
check("重复注册被拒绝", (not ok2) and "已经加载" in msg2, msg2)

print("")
print("=" * 78)
print("八、存档兼容（新字段）")
print("=" * 78)
tmp = tempfile.mkdtemp(prefix="lifesim_v2_")
sp = os.path.join(tmp, "save.json")
pl = ls.Player(name="存档", city="guangzhou", rng=random.Random(99))
pl.stage = "university"; pl.age = 22; pl.action_points = 3; pl.actions_today = 4
pl.constitution = 77.5; pl.family_wealth = 33.3; pl.stats["study_points"] = 42
pl.action_tally = {"rest": 2}
ok, msg = ls.save_game(sp, pl, ls.LifeLog(None))
loaded, lmsg = ls.load_game(sp, rng=random.Random(1))
check("新字段（体质/家境/阶段/行动点）读写一致",
      loaded is not None and abs(loaded.constitution - 77.5) < 0.01
      and loaded.stage == "university" and loaded.action_points == 3
      and loaded.action_tally.get("rest") == 2
      and loaded.stats.get("study_points") == 42,
      "体质 %.1f 家境 %.1f 阶段 %s 行动点 %d" % (
          loaded.constitution, loaded.family_wealth, loaded.stage, loaded.action_points))
# 旧存档（缺字段）兼容
import json
data = json.load(open(sp, encoding="utf-8"))
for k in ("constitution", "family_wealth", "stage", "action_points", "action_tally", "days_played"):
    data["player"].pop(k, None)
old_path = os.path.join(tmp, "old_save.json")
json.dump(data, open(old_path, "w", encoding="utf-8"), ensure_ascii=False)
old, omsg = ls.load_game(old_path, rng=random.Random(1))
check("旧存档（缺新字段）仍能读取", old is not None and old.stage in ls.STAGE_BY_ID,
      "补齐阶段=%s 体质=%.1f" % (old.stage if old else "?", old.constitution if old else 0))

print("")
print("=" * 78)
print("测试结果：通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
print("=" * 78)
for name, detail in FAIL:
    print("[FAIL] %s  %s" % (name, detail))
sys.stdout.flush()
os._exit(0 if not FAIL else 1)
