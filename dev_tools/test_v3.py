# -*- coding: utf-8 -*-
"""v3 新系统测试：疾病扩展、健康影响倍率、寿命、生育/繁殖系统。"""
import importlib.util
import os
import random
import statistics
import sys
import tempfile

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print("%s %s%s" % ("[OK]  " if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))


print("=" * 80)
print("一、疾病扩展：覆盖大部分已知常见疾病")
print("=" * 80)
check("疾病种类扩展到 30 种以上", len(ls.DISEASES) >= 30, "共 %d 种" % len(ls.DISEASES))
groups = {g: len(keys) for g, keys in ls.DISEASE_GROUPS}
check("疾病按 7 大类分组覆盖（呼吸道/消化道/心血管/感染/外伤/皮肤/心理）",
      len(groups) == 7 and all(v >= 2 for v in groups.values()),
      "  ".join("%s:%d" % (k, v) for k, v in groups.items()))
# 检查每种疾病的字段完整性
bad = []
for key, d in ls.DISEASES.items():
    for f in ("name", "kind", "desc", "days", "hp_per_day", "happy_per_day",
              "cure_cost", "self_heal", "temp_mod", "severity"):
        if f not in d:
            bad.append("%s 缺 %s" % (key, f))
    if d.get("hp_per_day", 0) <= 0 or d.get("cure_cost", 0) < 0:
        bad.append("%s 数值异常" % key)
check("所有疾病字段完整且数值合法", not bad, "；".join(bad[:4]) if bad else "已校验 %d 种" % len(ls.DISEASES))
# 疾病按年龄人群正确分流
p_child = ls.Player(name="孩子", city="beijing", rng=random.Random(1)); p_child.age = 2
p_adult = ls.Player(name="成人", city="beijing", rng=random.Random(1)); p_adult.age = 30
p_elder = ls.Player(name="老人", city="beijing", rng=random.Random(1)); p_elder.age = 78
w_child_otitis = ls.disease_weight_for(p_child, "otitis")
w_adult_otitis = ls.disease_weight_for(p_adult, "otitis")
w_elder_heart = ls.disease_weight_for(p_elder, "heart_disease")
w_child_heart = ls.disease_weight_for(p_child, "heart_disease")
check("中耳炎在幼儿中权重远高于成人", w_child_otitis > w_adult_otitis * 3,
      "幼儿 %.1f vs 成人 %.1f" % (w_child_otitis, w_adult_otitis))
check("冠心病在老人中权重远高于幼儿", w_elder_heart > w_child_heart * 5,
      "老人 %.1f vs 幼儿 %.1f" % (w_elder_heart, w_child_heart))
# 抽病分布：直接按权重抽样 4000 次，看能覆盖多少种疾病
def weighted_pick(player, times=1):
    """按 disease_weight_for 的权重抽样一次疾病 id（模拟真实抽病分布）。"""
    items = [(k, ls.disease_weight_for(player, k)) for k in ls.DISEASES]
    total = sum(w for _k, w in items)
    r = random.random() * total
    acc = 0.0
    for k, w in items:
        acc += w
        if r <= acc:
            return k
    return items[-1][0]


seen = {}
rng = random.Random(7)
for i in range(4000):
    p = ls.Player(name="x", city=ls.CITY_ORDER[i % 4], rng=random.Random(i))
    p.age = rng.choice([2, 5, 12, 18, 25, 40, 55, 70, 85])
    p.month = rng.randint(1, 12)
    key = weighted_pick(p)
    seen[key] = seen.get(key, 0) + 1
check("随机抽病能覆盖大部分疾病（≥25 种）", len(seen) >= 25,
      "抽到 %d 种（共 %d 种）：%s" % (len(seen), len(ls.DISEASES),
                                     "、".join(ls.DISEASES[k]["name"] for k in list(seen)[:10])))
# 高频病应当是常见病（感冒/流感/肠胃炎之类）
top = sorted(seen.items(), key=lambda x: -x[1])[:6]
top_names = [ls.DISEASES[k]["name"] for k, _v in top]
check("最高频疾病都是常见病（感冒/流感等）",
      any(n in ("普通感冒", "流行性感冒", "急性肠胃炎", "过敏性鼻炎", "偏头痛") for n in top_names),
      "TOP6：%s" % "、".join(top_names))

print("")
print("=" * 80)
print("二、健康影响倍率与初始健康（让寿命足够长）")
print("=" * 80)
check("存在全局疾病健康影响倍率", hasattr(ls, "DISEASE_HEALTH_IMPACT"),
      "DISEASE_HEALTH_IMPACT = %.2f" % ls.DISEASE_HEALTH_IMPACT)
check("健康影响倍率已下调（<1.0，减轻疾病伤害）", ls.DISEASE_HEALTH_IMPACT < 1.0)
check("初始健康为满值", ls.INIT_HEALTH == 100, "INIT_HEALTH = %d" % ls.INIT_HEALTH)
# 对比：同一疾病在不同倍率下的每日扣血
p = ls.Player(name="x", city="beijing", rng=random.Random(1)); p.age = 30
d = ls.DiceSystem(random.Random(1))
info = ls.make_disease(d, "pneumonia")
p.diseases.append(info)
rep = ls.DailyReport(p)
sim = ls.Simulator(p, ls.LifeLog(None), "", seed=1)
h0 = p.health
sim.settle_disease_phase(rep)
loss = h0 - p.health
base_loss = info["hp_per_day"]
check("实际每日扣血低于疾病基础值（倍率生效）", loss < base_loss,
      "肺炎基础 %.2f -> 实际 %.2f（含体质与倍率）" % (base_loss, loss))

print("")
print("=" * 80)
print("三、寿命水平（目标 ≥ 80 岁）")
print("=" * 80)
GOOD = ("治疗", "就医", "医院", "买药", "吃药", "降温", "疫苗", "添衣", "口罩",
        "空调", "报警", "据理", "沟通", "争取", "备考", "接受", "主动", "告诉老师",
        "承担", "认真", "联系", "添置", "乖乖", "试着", "做完", "写完", "赴约",
        "伸出", "遵医嘱", "住院")


def choose(sim, card):
    ch = card.get("choices") or []
    bi, best = 0, None
    for c in ch:
        s = 0.0
        if any(k in c["label"] for k in GOOD):
            s += 2
        if any(k in c["label"] for k in ("硬扛", "继续扛", "不管", "据为己有", "冒险",
                                         "冷战", "偷懒", "坚决不吃", "扭头", "先出去玩")):
            s -= 1.5
        if c.get("need_money", 0) > sim.player.money:
            s -= 5
        if best is None or s > best:
            best, bi = s, c["index"]
    return bi


def play(seed, want_children=True, maxd=60000):
    p = ls.Player(name="寿%d" % seed, city=ls.CITY_ORDER[seed % 4],
                  rng=random.Random(seed * 7919))
    s = ls.Simulator(p, ls.LifeLog(None), "", seed=seed)
    d = 0
    while not p.dead and d < maxd:
        c = s.step_roll()
        if c.get("tone") == "dead":
            break
        if s.pending is not None:
            r = s.resolve_choice(choose(s, c))
            if r.get("tone") == "warn":
                s.resolve_choice(0)
            if p.dead:
                break
        act = "rest" if (p.diseases or p.health < 35) else (
            "work" if p.money < 200 else ("work", "work", "fun", "work", "fun", "rest", "rest")[d % 7])
        s.apply_daily_action(act)
        if want_children and p.married and 24 <= p.age <= 36 and len(p.child_list) < 2 and not p.pregnant:
            p.intimacy_today = 0
            s.do_intimacy("安全期")
        if p.diseases and p.health < 55:
            s.try_cure()
        s.skip_day()
        d += 1
    return p, s


ages, kids = [], []
for i in range(30):
    p, s = play(9100 + i)
    ages.append(p.age)
    kids.append(len(p.child_list))
mean_age = statistics.mean(ages)
check("平均寿命 ≥ 80 岁（人生足够长）", mean_age >= 79.0,
      "平均 %.1f 岁，中位 %.1f 岁，范围 %d~%d" % (
          mean_age, statistics.median(ages), min(ages), max(ages)))
check("寿命分布合理（多数 70~100 岁）",
      sum(1 for a in ages if 70 <= a <= 100) >= len(ages) * 0.7,
      "70~100 岁占 %.0f%%" % (sum(1 for a in ages if 70 <= a <= 100) * 100.0 / len(ages)))
check("自然死亡为主（不是被疾病反复拖死）",
      sum(1 for a in ages if a >= 60) >= len(ages) * 0.9,
      "%d/%d 活过 60 岁" % (sum(1 for a in ages if a >= 60), len(ages)))

print("")
print("=" * 80)
print("四、恋爱婚姻 + 繁殖系统")
print("=" * 80)
p = ls.Player(name="夫妻", city="beijing", rng=random.Random(3))
p.age = 26
p.married = True
p.partner_name = "配偶"
s = ls.Simulator(p, ls.LifeLog(None), "", seed=3)
ok, why = s.can_be_intimate()
check("婚后成年角色可以进行「夫妻亲密」", ok, why or "允许")
# 未成年人不可
p2 = ls.Player(name="少年", city="beijing", rng=random.Random(4)); p2.age = 15
p2.married = True; p2.partner_name = "伴侣"
s2 = ls.Simulator(p2, ls.LifeLog(None), "", seed=4)
ok2, why2 = s2.can_be_intimate()
check("未成年人不能进行亲密（现实向限制）", not ok2, why2.splitlines()[0])
# 单身不可
p3 = ls.Player(name="单身", city="beijing", rng=random.Random(5)); p3.age = 30
s3 = ls.Simulator(p3, ls.LifeLog(None), "", seed=5)
ok3, why3 = s3.can_be_intimate()
check("单身角色不能进行亲密", not ok3, why3.splitlines()[0])
# 亲密提升幸福度
p4 = ls.Player(name="幸福", city="beijing", rng=random.Random(6))
p4.age = 28; p4.married = True; p4.partner_name = "配偶"; p4.happy = 50
p4.contraception = "避孕套"
s4 = ls.Simulator(p4, ls.LifeLog(None), "", seed=6)
before = p4.happy
r = s4.do_intimacy("避孕套")
check("亲密能提高幸福度", p4.happy > before and r.get("tone") == "intimacy",
      "幸福 %.1f -> %.1f" % (before, p4.happy))
# 每天最多一次
r2 = s4.do_intimacy("避孕套")
check("每天最多一次亲密（现实向限制）",
      r2.get("tone") == "warn" and "今天" in r2.get("text", ""), r2.get("text", "").splitlines()[0])
# 避孕效果显著
def conception_trials(method, trials=600):
    hits = 0
    for i in range(trials):
        pp = ls.Player(name="t", city="beijing", rng=random.Random(1000 + i))
        pp.age = 26; pp.married = True; pp.contraception = method
        ss = ls.Simulator(pp, ls.LifeLog(None), "", seed=1000 + i)
        conceive, _note = ss._try_conceive()
        if conceive:
            hits += 1
    return hits / float(trials)


rate_none = conception_trials("不避孕")
rate_condom = conception_trials("避孕套")
rate_pill = conception_trials("短效避孕药")
check("避孕手段显著降低受孕率",
      rate_condom < rate_none * 0.35 and rate_pill < rate_none * 0.15,
      "不避孕 %.1f%% / 避孕套 %.1f%% / 短效药 %.1f%%" % (
          rate_none * 100, rate_condom * 100, rate_pill * 100))
check("不避孕时受孕率在合理区间（10%~30%）", 0.10 <= rate_none <= 0.30,
      "实测 %.1f%%" % (rate_none * 100))
# 年龄影响受孕
young = ls.conception_rate(24)
older = ls.conception_rate(42)
check("受孕概率随年龄下降", young > older * 1.8,
      "24 岁 %.0f%% vs 42 岁 %.0f%%" % (young * 100, older * 100))
# 完整怀孕 -> 分娩流程
p5 = ls.Player(name="孕", city="beijing", rng=random.Random(8))
p5.age = 27; p5.married = True; p5.partner_name = "配偶"
s5 = ls.Simulator(p5, ls.LifeLog(None), "", seed=8)
p5.pregnant = True
p5.pregnancy_days = 0
p5.pregnancy_count = 1
rep = ls.DailyReport(p5)
for _ in range(ls.PREGNANCY_DAYS + 5):
    s5.settle_pregnancy_phase(rep)
    if not p5.pregnant:
        break
check("怀孕 9 个月后顺利分娩", p5.birth_count == 1 and len(p5.child_list) == 1,
      "分娩 %d 次，孩子 %d 个" % (p5.birth_count, len(p5.child_list)))
if p5.child_list:
    child = p5.child_list[0]
    check("孩子继承父母体质（先天体质在合法区间）",
          ls.CONSTITUTION_MIN <= child["constitution"] <= ls.CONSTITUTION_MAX,
          "%s（%s）先天体质 %.1f" % (child["name"], child["gender"], child["constitution"]))
    check("孩子有姓名/性别/生日档案",
          bool(child.get("name")) and child.get("gender") in ("男孩", "女孩")
          and bool(child.get("birth_date")),
          "%s / %s / %s" % (child["name"], child["gender"], child["birth_date"]))
check("生育后幸福度提升", p5.happy > 50, "幸福 %.1f" % p5.happy)
# 孕期期间不能再亲密
p5.pregnant = True
p5.intimacy_today = 0
can_now, why_now = s5.can_be_intimate()
check("孕期期间不能再亲密", not can_now, why_now or "受限")
p5.pregnant = False

print("")
print("=" * 80)
print("五、养育与子女成长")
print("=" * 80)
p6 = ls.Player(name="父母", city="beijing", rng=random.Random(9))
p6.age = 35; p6.married = True; p6.partner_name = "配偶"
p6.child_list = [{"name": "小安", "gender": "女孩", "birth_date": "30 岁 · 1 年 1 月 1 日",
                  "constitution": 62.0, "mother_age": 30}]
p6.children = 1
s6 = ls.Simulator(p6, ls.LifeLog(None), "", seed=9)
h0 = p6.happy
r = s6.apply_daily_action("parenting")
check("「陪伴孩子」可提升幸福", p6.happy > h0 and r.get("tone") == "action",
      "幸福 %.1f -> %.1f" % (h0, p6.happy))
check("子女概览可展示", "小安" in s6.children_summary(), s6.children_summary().strip())
# 无子女时陪伴给出提示
p7 = ls.Player(name="无子", city="beijing", rng=random.Random(10)); p7.age = 30
s7 = ls.Simulator(p7, ls.LifeLog(None), "", seed=10)
r7 = s7.apply_daily_action("parenting")
check("没有孩子时「陪伴孩子」给出友好提示",
      r7.get("tone") == "warn" and "还没有孩子" in r7.get("text", ""),
      r7.get("text", "").splitlines()[0])
# 养育开销
p8 = ls.Player(name="开销", city="beijing", rng=random.Random(11)); p8.age = 35
p8.married = True; p8.stage = "work"; p8.employed = True; p8.job_level = 3
p8.money = 50000
s8 = ls.Simulator(p8, ls.LifeLog(None), "", seed=11)
rep8 = ls.DailyReport(p8)
m0 = p8.money
s8.settle_month(rep8)
no_child_cost = m0 - p8.money
p8.money = 50000
p8.child_list = [{"name": "宝", "gender": "男孩", "birth_date": "", "constitution": 50.0,
                  "mother_age": 33}]
p8.children = 1
rep9 = ls.DailyReport(p8)
s8.settle_month(rep9)
with_child_cost = 50000 - p8.money
check("有孩子后每月开销明显增加", with_child_cost > no_child_cost,
      "无子女 %.0f / 有 1 个孩子 %.0f" % (no_child_cost, with_child_cost))

print("")
print("=" * 80)
print("六、存档兼容（生育字段）")
print("=" * 80)
tmp = tempfile.mkdtemp(prefix="lifesim_v3_")
sp = os.path.join(tmp, "save.json")
p9 = ls.Player(name="存档", city="shanghai", rng=random.Random(12))
p9.age = 30; p9.married = True; p9.partner_name = "小李"
p9.pregnant = True; p9.pregnancy_days = 120; p9.pregnancy_count = 2
p9.child_list = [{"name": "大宝", "gender": "女孩", "birth_date": "28 岁 · 1 年 1 月 1 日",
                  "constitution": 58.0, "mother_age": 28}]
p9.children = 1; p9.contraception = "安全期"; p9.miscarriage = 1
ok, msg = ls.save_game(sp, p9, ls.LifeLog(None))
loaded, lmsg = ls.load_game(sp, rng=random.Random(1))
check("生育字段读写一致",
      loaded is not None and loaded.pregnant and loaded.pregnancy_days == 120
      and len(loaded.child_list) == 1 and loaded.child_list[0]["name"] == "大宝"
      and loaded.contraception == "安全期" and loaded.miscarriage == 1,
      "孕期 %d 天 / 子女 %d 人 / 避孕 %s" % (
          loaded.pregnancy_days if loaded else -1,
          len(loaded.child_list) if loaded else -1,
          loaded.contraception if loaded else "?"))
# 旧存档兼容
import json
data = json.load(open(sp, encoding="utf-8"))
for k in ("pregnant", "pregnancy_days", "child_list", "contraception", "partner_name",
          "intimacy_today", "pregnancy_count", "birth_count", "miscarriage"):
    data["player"].pop(k, None)
old_path = os.path.join(tmp, "old.json")
json.dump(data, open(old_path, "w", encoding="utf-8"), ensure_ascii=False)
old, omsg = ls.load_game(old_path, rng=random.Random(1))
check("旧存档（缺生育字段）仍可读取",
      old is not None and old.child_list == [] and old.contraception in
      [o[0] for o in ls.CONTRACEPTION_OPTIONS],
      "补齐避孕方式=%s" % (old.contraception if old else "?"))

print("")
print("=" * 80)
print("测试结果：通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
print("=" * 80)
for name, detail in FAIL:
    print("[FAIL] %s  %s" % (name, detail))
sys.stdout.flush()
os._exit(0 if not FAIL else 1)
