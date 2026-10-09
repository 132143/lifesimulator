# -*- coding: utf-8 -*-
"""
寿命参数标定：扫描 NATURAL_DEATH_BASE，找到使理性玩家平均寿命 ≈ 80 岁的取值。
用法：python calibrate.py <LifeSimulator.py> [每组种子数]
"""
import importlib.util
import random
import statistics
import sys

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

N = int(sys.argv[2]) if len(sys.argv) > 2 else 25

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


def run(seed):
    player = ls.Player(name="标定%d" % seed, city=ls.CITY_ORDER[seed % 4],
                       rng=random.Random(seed * 7919))
    sim = ls.Simulator(player, ls.LifeLog(None), "", seed=seed)
    days = 0
    while not player.dead and days < 60000:
        card = sim.step_roll()
        if card.get("tone") == "dead":
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
        if player.diseases and player.health < 55:
            sim.try_cure()
    return player


print("当前参数：BASE_RATE=%.4f  GROWTH=%.4f  FLOOR=%.0f  START=%d" % (
    ls.NATURAL_DEATH_BASE_RATE, ls.NATURAL_DEATH_GROWTH,
    ls.NATURAL_DEATH_FLOOR_AGE, ls.NATURAL_DEATH_START))
print("理论死亡率（满健康）：50岁 %.3f%% | 60岁 %.3f%% | 70岁 %.3f%% | 80岁 %.3f%% | 90岁 %.3f%% | 100岁 %.2f%%" % (
    ls.natural_death_rate(50) * 100, ls.natural_death_rate(60) * 100,
    ls.natural_death_rate(70) * 100, ls.natural_death_rate(80) * 100,
    ls.natural_death_rate(90) * 100, ls.natural_death_rate(100) * 100))
print("")

for growth in (1.040, 1.048, 1.056, 1.064, 1.072):
    ls.NATURAL_DEATH_GROWTH = growth
    ages = [run(4000 + i).age for i in range(N)]
    print("GROWTH=%.4f -> 平均寿命 %.1f 岁，中位数 %.1f，范围 %d~%d，超过100岁比例 %.0f%%" % (
        growth, statistics.mean(ages), statistics.median(ages), min(ages), max(ages),
        sum(1 for a in ages if a > 100) * 100.0 / N))
