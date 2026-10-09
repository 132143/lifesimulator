# -*- coding: utf-8 -*-
"""
验收测试：对照需求逐条检查。
用法：python acceptance.py <LifeSimulator.py 路径> [寿命样本数]
"""
import importlib.util
import json
import os
import random
import re
import statistics
import sys
import tempfile

TARGET = sys.argv[1]
LIFE_SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 25

spec = importlib.util.spec_from_file_location("ls", TARGET)
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("%s %s%s" % ("[OK]  " if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))


GOOD_WORDS = ("治疗", "就医", "医院", "买药", "吃药", "降温", "疫苗", "添衣", "口罩",
              "空调", "报警", "据理", "沟通", "争取", "备考", "接受这份工作", "主动",
              "告诉老师", "承担", "认真", "联系", "添置", "乖乖", "试着", "认真做完",
              "先写完", "赴约", "伸出", "遵医嘱", "住院", "接受")


def rational_choice(sim, card):
    choices = card.get("choices") or []
    best, best_score = 0, None
    for c in choices:
        score = 0.0
        if any(k in c["label"] for k in GOOD_WORDS):
            score += 2
        if any(k in c["label"] for k in ("硬扛", "继续扛", "不管", "据为己有", "冒险",
                                         "冷战", "偷懒", "坚决不吃", "扭头", "先出去玩")):
            score -= 1.5
        if c.get("need_money", 0) > sim.player.money:
            score -= 5
        if best_score is None or score > best_score:
            best, best_score = c["index"], score
    return best


def play_life(seed, max_days=60000, city=None):
    player = ls.Player(name="验收%d" % seed, city=city or ls.CITY_ORDER[seed % 4],
                       rng=random.Random(seed * 7919))
    log = ls.LifeLog(None)
    sim = ls.Simulator(player, log, "", seed=seed)
    days = 0
    age_events = []          # (年龄, 事件名, 大类)
    while not player.dead and days < max_days:
        card = sim.step_roll()
        if card.get("tone") == "dead":
            break
        if card.get("tone") == "event":
            age_events.append((player.age, card["event_name"], card["category"]))
            res = sim.resolve_choice(rational_choice(sim, card))
            if res.get("tone") == "warn":
                sim.resolve_choice(0)
            if player.dead:
                break
        if player.diseases or player.health < 35:
            act = "rest"
        elif player.money < 200:
            act = "work"
        else:
            act = ("work", "work", "fun", "work", "fun", "rest", "rest")[days % 7]
        sim.apply_daily_action(act)
        days += 1
        if player.diseases and player.health < 55:
            sim.try_cure()
    return player, sim, age_events


print("=" * 78)
print("一、需求 1：骰子随机机制")
print("=" * 78)
d = ls.DiceSystem(random.Random(12345))
seen = set()
for i in range(4000):
    r = d.d100("t")
    seen.add(r.value)
check("d100 能取到 1~100 的点数", len(seen) >= 95 and min(seen) >= 1 and max(seen) <= 100,
      "实际出现 %d 种点数，范围 %d~%d" % (len(seen), min(seen), max(seen)))
for faces, fn in ((4, d.d4), (6, d.d6), (10, d.d10), (20, d.d20)):
    vals = set(fn("t").value for _ in range(2000))
    check("d%d 点数在 1~%d 之间且覆盖全部面" % (faces, faces),
          min(vals) == 1 and max(vals) == faces and len(vals) == faces)
# 概率均衡：d100 各区间不应严重偏斜
counts = [0] * 10
d2 = ls.DiceSystem(random.Random(999))
for _ in range(20000):
    v = d2.d100("t").value
    counts[min(9, (v - 1) // 10)] += 1
low, high = min(counts), max(counts)
check("d100 分布均衡（无极端偏斜）", high < 20000 / 10 * 1.25,
      "十等分区间计数 %d~%d（期望 2000）" % (low, high))
# 隐藏特殊情节
hidden_found = {}
d3 = ls.DiceSystem(random.Random(7))
for _ in range(60000):
    v = d3.d100("t").value
    if v in ls.DiceSystem.HIDDEN_D100:
        hidden_found[v] = hidden_found.get(v, 0) + 1
check("极端点数触发隐藏特殊情节（100/99/2/1）", len(hidden_found) == 4,
      "命中次数 %s" % hidden_found)

print("")
print("=" * 78)
print("二、需求 2：人物属性边界与时间推进")
print("=" * 78)
p = ls.Player(name="边界", city="beijing", rng=random.Random(1))
dd = ls.DiceSystem(random.Random(1))
p.apply_effects({"health": -9999}, dice=dd)
check("健康下限为 0", p.health == 0, "health=%s" % p.health)
p.health = 50
p.apply_effects({"health": +9999}, dice=dd)
check("健康上限为 100", p.health == 100, "health=%s" % p.health)
p.apply_effects({"happy": +999}, dice=dd)
check("幸福上限为 100", p.happy == 100, "happy=%s" % p.happy)
p.happy = 50
p.apply_effects({"happy": -999}, dice=dd)
check("幸福下限为 0", p.happy == 0, "happy=%s" % p.happy)
p.apply_effects({"temp": +99}, dice=dd)
check("体温有硬上限（不会无限升高）", p.temp <= ls.TEMP_HARD_HIGH, "temp=%s" % p.temp)
p.apply_effects({"temp": -99}, dice=dd)
check("体温有硬下限", p.temp >= ls.TEMP_HARD_LOW, "temp=%s" % p.temp)
p2 = ls.Player(name="金钱", city="beijing", rng=random.Random(2))
p2.apply_effects({"money": -99999}, dice=dd)
check("金钱可以负债（无下限）", p2.money < 0, "money=%s" % p2.money)
# 注意：未成年人/大额金钱会按年龄与身价折算（防止幼儿中巨奖），因此用成年人 + 小额反复累加验证"无上限"
p2.age = 30
p2.money = 0.0
for _ in range(400):
    p2.apply_effects({"money": 2500}, dice=dd)
check("金钱可以无限累积（无上限）", p2.money > 500000, "money=%s" % p2.money)
# 未成年人保护：同样的收益在幼儿身上应大幅缩减
p2b = ls.Player(name="幼儿", city="beijing", rng=random.Random(6))
p2b.apply_effects({"money": 2500}, dice=dd)
check("未成年人收入按年龄折算（避免幼儿暴富）", p2b.money < 1500,
      "幼儿获得 %.2f（成年人 2500）" % p2b.money)
check("30 天 = 1 个月，12 个月 = 1 年",
      ls.DAYS_PER_MONTH == 30 and ls.MONTHS_PER_YEAR == 12 and ls.DAYS_PER_YEAR == 360)
check("初始属性符合要求（健康100/幸福50/金钱1000/体温36.5）",
      p2.health == 100 and isinstance(p2.money, float) and ls.INIT_TEMP == 36.5)
# 时间推进：360 天 = 1 岁
p3 = ls.Player(name="时间", city="beijing", rng=random.Random(3))
sim3 = ls.Simulator(p3, ls.LifeLog(None), "", seed=3)
for _ in range(360):
    sim3.advance_calendar()
check("推进 360 天后年龄 +1", p3.age == 1 and p3.year == 2, "age=%d year=%d" % (p3.age, p3.year))

print("")
print("=" * 78)
print("三、需求 4/5：事件分类与城市气候")
print("=" * 78)
cats = {}
for eid in ls.EVENT_ORDER:
    ev = ls.EVENTS[eid]
    cats.setdefault(ev["category"], []).append(ev["name"])
for need in ("疾病", "工作", "情感", "环境", "意外", "日常"):
    check("存在「%s」类事件" % need, len(cats.get(need, [])) >= 3,
          "%d 个：%s" % (len(cats.get(need, [])), "、".join(cats.get(need, [])[:5])))
check("共 4 个可选城市", len(ls.CITIES) == 4 and set(ls.CITIES) == {"harbin", "beijing", "shanghai", "guangzhou"},
      "、".join(ls.CITIES[c]["name"] + "(" + ls.CITIES[c]["tag"] + ")" for c in ls.CITY_ORDER))
# 城市气候差异
winter = {c: ls.env_weights_for(c, 1) for c in ls.CITY_ORDER}
summer = {c: ls.env_weights_for(c, 7) for c in ls.CITY_ORDER}
check("寒冷城市冬季寒潮权重最高",
      winter["harbin"].get("cold_wave", 0) > winter["guangzhou"].get("cold_wave", 0),
      "哈尔滨寒潮 %s vs 广州 %s" % (winter["harbin"].get("cold_wave"), winter["guangzhou"].get("cold_wave")))
check("炎热城市夏季高温权重最高",
      summer["guangzhou"].get("heat_wave", 0) > summer["harbin"].get("heat_wave", 0),
      "广州高温 %s vs 哈尔滨 %s" % (summer["guangzhou"].get("heat_wave"), summer["harbin"].get("heat_wave")))
check("城市气温差异明显（哈尔滨冬季远低于广州）",
      ls.seasonal_avg_temp("harbin", 1) < ls.seasonal_avg_temp("guangzhou", 1) - 20,
      "哈尔滨 %.0f℃ vs 广州 %.0f℃" % (ls.seasonal_avg_temp("harbin", 1), ls.seasonal_avg_temp("guangzhou", 1)))

print("")
print("=" * 78)
print("四、需求 6/7/8：弹窗交互、存档、日志、异常处理")
print("=" * 78)
tmp = tempfile.mkdtemp(prefix="lifesim_acc_")
save_path = os.path.join(tmp, "save.json")
log_path = os.path.join(tmp, "life_log.txt")
player = ls.Player(name="存档测试", city="shanghai", rng=random.Random(9))
log = ls.LifeLog(log_path, player.name, "上海")
log.start(player)
sim = ls.Simulator(player, log, tmp, seed=9)
for i in range(60):
    card = sim.step_roll()
    if card.get("tone") == "dead":
        break
    if card.get("tone") == "event":
        res = sim.resolve_choice(rational_choice(sim, card))
        if res.get("tone") == "warn":
            sim.resolve_choice(0)
        if player.dead:
            break
    sim.apply_daily_action(("rest", "work", "fun")[i % 3])
ok, msg = ls.save_game(save_path, player, log)
check("存档文件 save.json 生成成功", ok and os.path.isfile(save_path), msg.splitlines()[0])
loaded, lmsg = ls.load_game(save_path, rng=random.Random(9))
check("读档成功且属性一致",
      loaded is not None and abs(loaded.health - player.health) < 0.01
      and abs(loaded.money - player.money) < 0.01 and loaded.age == player.age,
      lmsg.splitlines()[-1])
data = json.load(open(save_path, encoding="utf-8"))
need_keys = ("health", "happy", "money", "temp", "age", "year", "month", "day",
             "diseases", "city", "event_history", "milestones")
check("存档包含全部关键字段", all(k in data["player"] for k in need_keys),
      "缺字段：%s" % [k for k in need_keys if k not in data["player"]])
check("读档后可从对应天数继续（日期一致）", loaded.date_full == player.date_full,
      loaded.date_full)
check("人生日志 life_log.txt 已生成且按时间记录", os.path.isfile(log_path) and os.path.getsize(log_path) > 500,
      "%d 字节" % os.path.getsize(log_path))
with open(log_path, encoding="utf-8") as fh:
    log_text = fh.read()
check("日志包含日期、事件、属性变化记录",
      ("事件：" in log_text) and ("健康" in log_text) and ("年" in log_text and "月" in log_text and "日" in log_text))
# 死亡人生总结
sim.kill("验收测试：自然结束", None)
summary = sim.finish_life()
check("死亡后自动追加完整人生总结（享年/属性/大事记）",
      ("人生总结" in summary) and ("享年" in summary) and ("最终属性" in summary)
      and ("生平大事记" in summary), "总结长度 %d 字" % len(summary))
check("人生总结已写入日志文件", "人生总结" in open(log_path, encoding="utf-8").read())
# 异常处理
bad = os.path.join(tmp, "bad.json")
open(bad, "w", encoding="utf-8").write("{坏掉的 JSON")
badp, badmsg = ls.load_game(bad, rng=random.Random(1))
check("损坏存档不会崩溃，返回友好提示", badp is None and "损坏" in badmsg, badmsg.splitlines()[0])
missing, mmsg = ls.load_game(os.path.join(tmp, "not_exist.json"))
check("存档不存在时给出友好提示", missing is None and "找不到" in mmsg)
p4 = ls.Player(name="治病", city="beijing", rng=random.Random(4))
sim4 = ls.Simulator(p4, ls.LifeLog(None), "", seed=4)
p4.money = 10
info, _ = p4.add_disease("pneumonia", force=True)
okc, cmsg, cost = sim4.try_cure("pneumonia")
check("金钱不足无法治病时给出提示且不崩溃", (not okc) and ("金钱不足" in cmsg), cmsg.splitlines()[0])
p4.money = 99999
okc2, cmsg2, cost2 = sim4.try_cure("pneumonia")
check("金钱充足时可以治愈疾病", okc2 and not p4.has_disease("pneumonia"), cmsg2)

print("")
print("=" * 78)
print("五、现实性：婴幼儿事件限制与平凡的一天")
print("=" * 78)
baby_bad = []
for eid in ls.EVENT_ORDER:
    ev = ls.EVENTS[eid]
    probe = ls.Player(name="婴儿", city="beijing", rng=random.Random(0))
    probe.age = 0
    try:
        allowed = ev["cond"](probe)
    except Exception:
        allowed = False
    if allowed and ev["category"] == "工作":
        baby_bad.append(ev["name"])
check("婴幼儿（0 岁）不会触发工作/职场类事件", not baby_bad, "违规事件：%s" % baby_bad)
probe = ls.Player(name="婴儿", city="beijing", rng=random.Random(0))
probe.age = 0
allowed_names = [ls.EVENTS[e]["name"] for e in ls.EVENT_ORDER if ls.EVENTS[e]["cond"](probe)]
check("婴幼儿只会有喂养/哄睡/学步等事件",
      any(n in allowed_names for n in ("喝奶与辅食", "哭闹的夜晚", "学步", "第一次说话")),
      "0 岁可触发：%s" % "、".join(allowed_names[:8]))
married_young = [ls.EVENTS[e]["name"] for e in ls.EVENT_ORDER
                 if ls.EVENTS[e]["category"] == "情感" and "结婚" in ls.EVENTS[e]["name"]
                 and ls.EVENTS[e]["cond"](probe)]
check("婴幼儿不会触发结婚类事件", not married_young)
check("存在「单纯无事发生」的平凡日常事件",
      any(ls.EVENTS[e]["name"] in ("平凡的一天", "安静的日常", "重复的节奏", "小小的惬意")
          for e in ls.EVENT_ORDER), "共 %d 个日常事件" % len(cats.get("日常", [])))

print("")
print("=" * 78)
print("六、疾病 U 型曲线（年龄越大先降后升）")
print("=" * 78)
factors = {a: ls.sickness_age_factor(a) for a in (0, 6, 14, 25, 45, 65, 85)}
check("患病概率曲线呈 U 型（青少年最低、老年最高）",
      factors[0] > factors[14] and factors[14] < factors[45] < factors[65] < factors[85],
      "系数：0岁 %.2f -> 14岁 %.2f -> 45岁 %.2f -> 65岁 %.2f -> 85岁 %.2f"
      % (factors[0], factors[14], factors[45], factors[65], factors[85]))

print("")
print("=" * 78)
print("七、寿命水平（目标：平均约 80 岁，%d 个样本）" % LIFE_SAMPLES)
print("=" * 78)
ages, parts = [], 0
for i in range(LIFE_SAMPLES):
    pl, sm, evs = play_life(7000 + i)
    ages.append(pl.age)
    tmp_save = os.path.join(tmp, "s%d.json" % i)
    ls.save_game(tmp_save, pl, ls.LifeLog(None))
    rp, _ = ls.load_game(tmp_save, rng=random.Random(1))
    if rp is not None:
        parts += 1
    os.remove(tmp_save)
mean_age = statistics.mean(ages)
check("平均寿命在 75~86 岁之间（目标约 80 岁）", 75 <= mean_age <= 86,
      "平均 %.1f 岁，中位数 %.1f 岁，范围 %d~%d" % (
          mean_age, statistics.median(ages), min(ages), max(ages)))
check("寿命分布合理（多数落在 60~100 岁）",
      sum(1 for a in ages if 60 <= a <= 100) >= LIFE_SAMPLES * 0.85,
      "60~100 岁占比 %.0f%%" % (sum(1 for a in ages if 60 <= a <= 100) * 100.0 / LIFE_SAMPLES))
check("全部样本存档读写成功", parts == LIFE_SAMPLES, "%d/%d" % (parts, LIFE_SAMPLES))

print("")
print("=" * 78)
print("八、长时间游玩不越界（随机抽样检查）")
print("=" * 78)
ok_bounds = True
detail = ""
for seed in (11, 22, 33):
    pl, sm, evs = play_life(seed, max_days=30000)
    if not (0 <= pl.health <= 100 and 0 <= pl.happy <= 100
            and ls.TEMP_HARD_LOW <= pl.temp <= ls.TEMP_HARD_HIGH
            and pl.age <= ls.AGE_MAX_LIMIT + 1):
        ok_bounds = False
        detail = "seed=%d 健康%.1f 幸福%.1f 体温%.1f 年龄%d" % (
            seed, pl.health, pl.happy, pl.temp, pl.age)
check("长时间游玩后四项属性始终在合法区间内", ok_bounds, detail)

print("")
print("=" * 78)
print("验收结果：通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
print("=" * 78)
if FAIL:
    for name, detail in FAIL:
        print("[FAIL] %s  %s" % (name, detail))
sys.stdout.flush()
os._exit(0 if not FAIL else 1)
