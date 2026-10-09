# -*- coding: utf-8 -*-
"""
寿命标定实验：多种子跑完整人生，统计平均寿命。
目标：理性玩家（mixed 策略）平均寿命 ≈ 80 岁，且分布合理（多数 70~95 岁）。
用法：python lifespan.py <LifeSimulator.py> [种子数] [策略]
"""
import importlib.util
import random
import statistics
import sys

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
POLICY = sys.argv[3] if len(sys.argv) > 3 else "mixed"

GOOD_WORDS = ("治疗", "就医", "医院", "买药", "吃药", "降温", "疫苗", "添衣", "口罩",
              "空调", "报警", "据理", "沟通", "争取", "备考", "接受这份工作", "主动",
              "告诉老师", "承担", "认真", "联系", "添置", "乖乖", "试着", "认真做完",
              "先写完", "赴约", "伸出", "遵医嘱", "住院")


def choose(sim, card):
    choices = card.get("choices") or []
    best, score_best = 0, None
    for c in choices:
        score = 0.0
        if any(k in c["label"] for k in GOOD_WORDS):
            score += 2
        if any(k in c["label"] for k in ("硬扛", "继续扛", "不管", "据为己有", "冒险",
                                         "冷战", "偷懒", "坚决不吃", "扭头")):
            score -= 1.5
        if c.get("need_money", 0) > sim.player.money:
            score -= 5
        if score_best is None or score > score_best:
            best, score_best = c["index"], score
    return best


def play(seed, max_days=40000):
    player = ls.Player(name="寿命%d" % seed, city=ls.CITY_ORDER[seed % 4],
                       rng=random.Random(seed * 7919))
    sim = ls.Simulator(player, ls.LifeLog(None), "", seed=seed)
    days = 0
    while not player.dead and days < max_days:
        card = sim.step_roll()
        if card.get("tone") == "dead":
            break
        if card.get("tone") == "event":
            res = sim.resolve_choice(choose(sim, card))
            if res.get("tone") == "warn":
                sim.resolve_choice(0)
            if player.dead:
                break
        if POLICY == "mixed":
            if player.diseases or player.health < 35:
                act = "rest"
            elif player.money < 200:
                act = "work"
            else:
                act = ("work", "work", "fun", "work", "fun", "rest", "rest")[days % 7]
        else:  # random 策略：乱选行动
            act = ("rest", "work", "fun")[seed % 3]
        sim.apply_daily_action(act)
        days += 1
        if player.diseases and player.health < 55:
            sim.try_cure()
    return player


ages, reasons, plain_days, sick_events = [], {}, 0, 0
for i in range(N):
    seed = 3000 + i
    p = play(seed)
    ages.append(p.age)
    reasons[p.death_reason or "存活"] = reasons.get(p.death_reason or "存活", 0) + 1
    plain_days += sum(1 for e in p.event_history if e.get("name") == "平凡的一天")
    sick_events += p.stats.get("disease_count", 0)
    if i < 8:
        print("seed=%-5d 享年=%-3d 疾病次数=%-3d 事件数=%-5d 死因=%s" % (
            seed, p.age, p.stats.get("disease_count", 0), len(p.event_history),
            p.death_reason or "存活"))

print("\n[策略=%s，样本=%d] 平均寿命 = %.1f 岁，中位数 = %.1f 岁，范围 %d ~ %d" % (
    POLICY, N, statistics.mean(ages), statistics.median(ages), min(ages), max(ages)))
buckets = {"<1岁": 0, "1-14岁": 0, "15-39岁": 0, "40-59岁": 0,
           "60-69岁": 0, "70-79岁": 0, "80-89岁": 0, "90-99岁": 0, "100岁以上": 0}
for a in ages:
    if a < 1:
        buckets["<1岁"] += 1
    elif a < 15:
        buckets["1-14岁"] += 1
    elif a < 40:
        buckets["15-39岁"] += 1
    elif a < 60:
        buckets["40-59岁"] += 1
    elif a < 70:
        buckets["60-69岁"] += 1
    elif a < 80:
        buckets["70-79岁"] += 1
    elif a < 90:
        buckets["80-89岁"] += 1
    elif a < 100:
        buckets["90-99岁"] += 1
    else:
        buckets["100岁以上"] += 1
print("寿命分布：%s" % "  ".join("%s:%d" % (k, v) for k, v in buckets.items() if v))
print("平均患病次数 = %.1f（每 10 年约 %.1f 次）" % (
    sick_events / float(N), sick_events / float(N) / (statistics.mean(ages) / 10.0)))
print("平凡的一天出现次数（前 8 例合计）：%d" % plain_days)
print("死因样例：")
for reason, count in sorted(reasons.items(), key=lambda x: -x[1])[:6]:
    print("    %2d 次  %s" % (count, reason[:60]))
