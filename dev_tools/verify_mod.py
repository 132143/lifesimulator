# -*- coding: utf-8 -*-
"""
模组接入验证：确认 harry_potter 模组能被自动加载、环境/阶段/事件都进库、
并且 daily_event_hook 真的接管了每日事件。
用法：python verify_mod.py <项目目录>
"""
import importlib.util
import os
import random
import sys

ROOT = os.path.abspath(sys.argv[1])
MAIN = os.path.join(ROOT, "LifeSimulator.py")

spec = importlib.util.spec_from_file_location("LifeSimulator", MAIN)
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)
ls.__LIFESIM_BASE_DIR__ = ROOT

FAIL = []


def check(name, ok, detail=""):
    print("%s %s%s" % ("[OK]  " if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))
    if not ok:
        FAIL.append(name)


# ---- 1) 自动加载 ----
n, notes = ls.discover_mods()
for x in notes:
    print("   加载日志：%s" % x)
check("模组被自动发现并加载", n >= 1, "加载 %d 个" % n)
check("harry_potter 在已加载列表里", "harry_potter" in ls.MOD_REGISTRY["loaded"])

# ---- 2) 环境 / 阶段 / 事件进库 ----
check("模组环境 hp_london 进入可选城市", "hp_london" in ls.CITIES,
      "当前可选城市：%s" % "、".join(ls.CITIES[c]["name"] for c in ls.CITY_ORDER[:8]))
hp_stages = [k for k in ls.STAGE_BY_ID if k.startswith("hp_")]
check("模组阶段进入阶段流程", len(hp_stages) >= 3, "共 %d 个：%s" % (len(hp_stages), hp_stages[:5]))
hp_events = [k for k in ls.EVENT_ORDER if k.startswith("hp_")]
check("模组事件进入可抽取列表", len(hp_events) >= 20, "共 %d 个" % len(hp_events))
check("事件字典里也有这些模组事件",
      all(k in ls.EVENTS for k in hp_events[:10]))

# ---- 3) 在伦敦开局时 daily_event_hook 是否接管 ----
mod = ls.MOD_REGISTRY["loaded"]["harry_potter"]["object"]
dice = ls.DiceSystem(random.Random(7))
p = ls.Player(name="巫师", city="hp_london", rng=random.Random(3))
p.stage = "hp_childhood"
p.age = 8
hook_hits = sum(1 for _ in range(30) if mod.daily_event_hook(p, dice) is not None)
check("伦敦开局时模组会接管每日事件", hook_hits >= 25,
      "30 次调用中接管 %d 次" % hook_hits)

# 非伦敦开局不应接管
p2 = ls.Player(name="麻瓜", city="beijing", rng=random.Random(3))
p2.age = 30
hook_miss = sum(1 for _ in range(20) if mod.daily_event_hook(p2, dice) is None)
check("非伦敦开局不接管（原版事件照常）", hook_miss == 20,
      "20 次调用中未接管 %d 次" % hook_miss)

# ---- 4) 真正跑一局：确认抽到的都是巫师事件 ----
sim = ls.Simulator(p, ls.LifeLog(None), "", seed=11)
dice2 = ls.DiceSystem(random.Random(11))
sim.dice = dice2
hp_count = 0
other_count = 0
picks = []
for _ in range(40):
    res = ls.roll_daily_event(sim.dice, p, engine=sim)
    ev = res.get("event")
    if ev is None:
        continue
    eid = ev.get("id", "")
    picks.append(eid)
    if eid.startswith("hp_"):
        hp_count += 1
    else:
        other_count += 1
check("每日事件抽取被模组接管（抽到的基本都是 hp_* 事件）",
      hp_count >= 20 and hp_count > other_count * 3,
      "共抽 %d 次：巫师事件 %d / 原版事件 %d" % (len(picks), hp_count, other_count))
print("   抽样事件：%s" % "、".join(picks[:12]))

# ---- 5) 完整跑几天，确认不崩、数值不越界 ----
p3 = ls.Player(name="跑测", city="hp_london", rng=random.Random(21))
sim3 = ls.Simulator(p3, ls.LifeLog(None), "", seed=21)
days = 0
errors = []
for _ in range(600):
    try:
        card = sim3.step_roll()
    except Exception as exc:
        errors.append("step_roll: %s" % exc)
        break
    if card.get("tone") == "dead":
        break
    if sim3.pending is not None:
        try:
            r = sim3.resolve_choice(0)
            if r.get("tone") == "warn":
                sim3.resolve_choice(0)
        except Exception as exc:
            errors.append("resolve_choice: %s" % exc)
            break
        if p3.dead:
            break
    try:
        sim3.apply_daily_action(("rest", "work", "fun")[days % 3])
        sim3.skip_day()
    except Exception as exc:
        errors.append("action: %s" % exc)
        break
    days += 1
    if not (0 <= p3.health <= 100 and 0 <= p3.happy <= 100):
        errors.append("数值越界 health=%.1f happy=%.1f" % (p3.health, p3.happy))
        break
check("巫师人生连续跑 600 天无异常", not errors, "；".join(errors[:2]) or
      "跑了 %d 天，%d 岁，阶段=%s，健康 %.1f 幸福 %.1f" % (
          days, p3.age, ls.stage_name(p3.stage), p3.health, p3.happy))
check("阶段推进到了巫师专属阶段", any(s.startswith("hp_") for s in
                                [p3.stage] + [h.get("to", "") for h in p3.stage_history]),
      "当前阶段=%s，历史=%s" % (p3.stage, [h.get("to") for h in p3.stage_history][:6]))

# ---- 6) 存档往返（模组状态下也能存读）----
import tempfile
tmp = tempfile.mkdtemp(prefix="mod_verify_")
sp = os.path.join(tmp, "save.json")
ok, msg = ls.save_game(sp, p3, ls.LifeLog(None))
loaded, lmsg = ls.load_game(sp, rng=random.Random(1))
check("模组开局下存档/读档正常",
      ok and loaded is not None and loaded.stage == p3.stage and loaded.city == "hp_london",
      "阶段 %s / 城市 %s" % (loaded.stage if loaded else "?", loaded.city if loaded else "?"))

print("")
print("=" * 70)
if FAIL:
    print("模组验证失败 %d 项：%s" % (len(FAIL), "；".join(FAIL)))
    sys.exit(1)
print("模组接入验证全部通过")
sys.exit(0)
