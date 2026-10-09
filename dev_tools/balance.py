# -*- coding: utf-8 -*-
"""
平衡性模拟：对比两种玩家策略下的寿命与数值分布。
  policy=rest  极端保守（一低血就狂休息，检查休息是否过强）
  policy=mixed 正常生活（按周轮换 工作/娱乐/休息，缺钱必须工作）
"""
import importlib.util
import random
import statistics
import sys

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
MAXDAYS = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
POLICY = sys.argv[4] if len(sys.argv) > 4 else "mixed"

GOOD_WORDS = ("治疗", "就医", "医院", "买药", "吃药", "降温", "疫苗", "添衣", "口罩",
              "空调", "报警", "据理", "沟通", "争取", "备考", "接受这份工作", "主动",
              "告诉老师", "承担", "认真", "联系")
BAD_WORDS = ("硬扛", "继续扛", "不管", "据为己有", "冒险", "再等等", "冷战")


def choose_option(sim, card):
    choices = card.get("choices") or []
    if not choices:
        return 0
    best_idx, best_score = 0, None
    for c in choices:
        score = 0.0
        label = c["label"]
        if any(k in label for k in GOOD_WORDS):
            score += 2.0
        if any(k in label for k in BAD_WORDS):
            score -= 1.5
        if c.get("need_money", 0) > sim.player.money:
            score -= 5.0
        if best_score is None or score > best_score:
            best_idx, best_score = c["index"], score
    return best_idx


def play(seed):
    player = ls.Player(name="平衡%d" % seed, city=ls.CITY_ORDER[seed % 4],
                       rng=random.Random(seed * 7919))
    sim = ls.Simulator(player, ls.LifeLog(None), "", seed=seed)
    days = 0
    while not player.dead and days < MAXDAYS:
        card = sim.step_roll()
        if card.get("tone") == "dead":
            break
        if card.get("tone") == "event":
            res = sim.resolve_choice(choose_option(sim, card))
            if res.get("tone") == "warn":
                sim.resolve_choice(0)
            if player.dead:
                break
        if POLICY == "rest":
            act = "rest" if (player.health < 95 or player.diseases) else "fun"
        else:
            # 正常生活：每周 3 天工作、2 天娱乐、2 天休息；生病或重伤优先休息
            if player.diseases or player.health < 35:
                act = "rest"
            elif player.money < 200:
                act = "work"
            else:
                act = ("work", "work", "fun", "work", "fun", "rest", "rest")[days % 7]
        sim.apply_daily_action(act)
        days += 1
        if player.diseases and player.health < 50:
            sim.try_cure()
    return player, days


ages, money, reasons = [], [], []
for i in range(N):
    player, days = play(1000 + i)
    ages.append(player.age)
    money.append(player.money)
    reasons.append(player.death_reason or "存活(到达天数上限)")
    print("seed=%-5d 年龄=%-3d 天数=%-6d 健康=%-6.1f 金钱=%-13.2f 患病=%-3d 治愈=%-3d 死因=%s" % (
        1000 + i, player.age, days, player.health, player.money,
        player.stats.get("disease_count", 0), player.stats.get("cure_count", 0),
        player.death_reason or "存活"))

print("\n[策略=%s] 年龄：min=%d 中位数=%.1f max=%d 平均=%.1f" % (
    POLICY, min(ages), statistics.median(ages), max(ages), statistics.mean(ages)))
print("未成年夭折 %d/%d，15-60 岁 %d，60 岁以上 %d（含存活到上限）" % (
    sum(1 for a in ages if a < 15), N,
    sum(1 for a in ages if 15 <= a < 60), sum(1 for a in ages if a >= 60)))
print("终局金钱：中位数 %.2f，最大 %.2f，负债比例 %.0f%%" % (
    statistics.median(money), max(money), sum(1 for m in money if m < 0) * 100.0 / N))
counter = {}
for r in reasons:
    counter[r] = counter.get(r, 0) + 1
print("死因分布：%s" % counter)
