# -*- coding: utf-8 -*-
"""验证患病率的 U 型年龄曲线：统计各年龄段的年均患病次数。"""
import importlib.util
import random
import sys

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
BANDS = [(0, 2), (2, 6), (6, 12), (12, 18), (18, 30), (30, 45),
         (45, 55), (55, 65), (65, 75), (75, 85), (85, 130)]

GOOD_WORDS = ("治疗", "就医", "医院", "买药", "吃药", "降温", "疫苗", "添衣", "口罩",
              "空调", "报警", "据理", "沟通", "争取", "备考", "接受这份工作", "主动",
              "告诉老师", "承担", "认真", "联系", "添置", "乖乖", "试着", "认真做完",
              "先写完", "赴约", "伸出", "遵医嘱", "住院", "接受")


def choose(sim, card):
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


#: 统计每个年龄段"经过了多少天"与"新增了多少次疾病"
days_by_band = {b: 0 for b in BANDS}
sick_by_band = {b: 0 for b in BANDS}
mortality_by_band = {b: 0 for b in BANDS}

for i in range(N):
    seed = 5000 + i
    player = ls.Player(name="U%d" % seed, city=ls.CITY_ORDER[seed % 4],
                       rng=random.Random(seed * 7919))
    sim = ls.Simulator(player, ls.LifeLog(None), "", seed=seed)
    days = 0
    prev_disease_count = 0
    prev_age = player.age
    while not player.dead and days < 60000:
        age_before = player.age
        card = sim.step_roll()
        if card.get("tone") == "dead":
            band = next((b for b in BANDS if b[0] <= player.age < b[1]), None)
            if band:
                mortality_by_band[band] += 1
            break
        if card.get("tone") == "event":
            res = sim.resolve_choice(choose(sim, card))
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
        band = next((b for b in BANDS if b[0] <= age_before < b[1]), None)
        if band:
            days_by_band[band] += 1
            new_sick = player.stats.get("disease_count", 0) - prev_disease_count
            if new_sick > 0:
                sick_by_band[band] += new_sick
        prev_disease_count = player.stats.get("disease_count", 0)

print("年龄段        总天数     新增患病   每 10 年患病次数")
for b in BANDS:
    d = days_by_band[b]
    s = sick_by_band[b]
    rate = (s / (d / 3650.0)) if d else 0.0
    bar = "#" * int(min(40, rate * 3))
    print("%3d-%3d 岁  %8d  %8d   %6.2f  %s" % (b[0], b[1], d, s, rate, bar))
print("\n自然死亡年龄落点统计：%s" % {
    "%d-%d" % b: mortality_by_band[b] for b in BANDS if mortality_by_band[b]})
