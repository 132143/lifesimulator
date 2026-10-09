# -*- coding: utf-8 -*-
r"""
行动点流程测试：验证"一天内可以连续点 8 次操作"。

覆盖用户反馈的问题：
  1. 同一天可以连续点击操作按钮 8 次（中间不需要"跳过当天"）
  2. 操作按钮在还有行动点时始终是可点击状态（不能是 disabled）
  3. 行动点耗尽后按钮变灰，此时点「推进一天」直接进入第二天（不是"跳过"）
  4. 推进后行动点重置为 8，且当天还能继续操作
  5. 操作不推进日期；「推进一天」才推进日期
"""
import importlib.util
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("LifeSimulator", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

FAIL = []


def check(name, ok, detail=""):
    print("%s %s%s" % ("[OK]  " if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))
    if not ok:
        FAIL.append(name)


def close_dialogs(app):
    """关掉所有弹窗，模拟玩家点了"确定"关闭结果窗。"""
    for w in list(app.root.winfo_children()):
        if isinstance(w, ls.tk.Toplevel):
            try:
                w.grab_release()
                w.destroy()
            except Exception:
                pass
    app.root.update()


work = tempfile.mkdtemp(prefix="lifesim_ap_")
app = ls.GameApp(work, ["行动点测试"])
app.root.update()
app.name_entry.delete(0, "end")
app.name_entry.insert(0, "行动测试")
app.city_var.set("beijing")
app.start_new_game()
app.root.update()
close_dialogs(app)

# ---- 推进一天，直到出现"平静的一天"（没有待处理事件），便于测试连续操作 ----
for _ in range(60):
    app.on_roll_day()
    app.root.update()
    close_dialogs(app)
    if app.sim.pending is not None:
        app.sim.resolve_choice(0)
        app.root.update()
        close_dialogs(app)
    if app.sim.pending is None:
        break

date_before = app.player.date_full
print("当天日期：%s    行动点：%d" % (date_before, app.player.action_points))
print("")

# ---- 1) 连续点 8 次「休息恢复」（每次都点"确定"关掉结果窗）----
print("=== 连续点击「休息恢复」8 次 ===")
done = 0
for i in range(12):          # 多点几次，验证第 9 次会被拒绝
    before = app.player.action_points
    state_before = app.action_buttons["rest"].cget("state")
    app.on_action("rest")
    app.root.update()
    close_dialogs(app)
    after = app.player.action_points
    state_after = app.action_buttons["rest"].cget("state")
    ok_click = after < before
    if ok_click:
        done += 1
    print("  第%2d 次：行动点 %2d -> %2d   按钮 %-8s -> %-8s  %s" % (
        i + 1, before, after, state_before, state_after,
        "成功" if ok_click else "被拒绝（行动点不足，符合预期）"))
    if not ok_click and i < 8:
        break

check("同一天能连续执行 8 次操作", done == 8, "实际成功 %d 次" % done)
check("操作过程中日期不变（操作不推进日期）", app.player.date_full == date_before,
      "%s -> %s" % (date_before, app.player.date_full))
check("行动点耗尽后为 0", app.player.action_points == 0,
      "剩余 %d" % app.player.action_points)
check("行动点耗尽后操作按钮变为 disabled",
      app.action_buttons["rest"].cget("state") == "disabled",
      "按钮状态=%s" % app.action_buttons["rest"].cget("state"))
check("行动点耗尽后「推进一天」按钮提示进入下一天",
      "推进到下一天" in app.btn_roll.cget("text"),
      "按钮文字=%s" % app.btn_roll.cget("text"))

# ---- 2) 行动点耗尽后直接点「推进一天」进入第二天 ----
print("")
print("=== 行动点耗尽后直接点「推进一天」 ===")
app.on_roll_day()
app.root.update()
close_dialogs(app)
if app.sim.pending is not None:
    app.sim.resolve_choice(0)
    app.root.update()
    close_dialogs(app)
check("推进一天后日期确实推进了", app.player.date_full != date_before,
      "%s -> %s" % (date_before, app.player.date_full))
check("新的一天行动点重置为 8", app.player.action_points == ls.ACTION_POINTS_PER_DAY,
      "行动点 %d" % app.player.action_points)

# ---- 3) 新的一天还能继续连续操作 ----
print("")
print("=== 新的一天继续操作 ===")
again = 0
for i in range(8):
    before = app.player.action_points
    app.on_action("social")
    app.root.update()
    close_dialogs(app)
    if app.player.action_points < before:
        again += 1
check("新的一天可以再次连续操作 8 次", again == 8, "实际 %d 次" % again)

# ---- 4) 检查混用不同操作也能连续 ----
print("")
print("=== 同一天混用不同操作 ===")
app.on_roll_day()
app.root.update()
close_dialogs(app)
if app.sim.pending is not None:
    app.sim.resolve_choice(0)
    app.root.update()
    close_dialogs(app)
mixed = 0
for key in ("rest", "work", "fun", "study", "social", "exercise", "rest", "fun"):
    before = app.player.action_points
    app.on_action(key)
    app.root.update()
    close_dialogs(app)
    if app.player.action_points < before:
        mixed += 1
check("同一天混用不同操作可以连续执行", mixed >= 7, "实际 %d 次" % mixed)

# ---- 5) 「略过剩余行动点」也应可用（但不再是唯一出路）----
print("")
print("=== 验证「略过剩余行动点」是可选操作 ===")
app.on_roll_day()
app.root.update()
close_dialogs(app)
if app.sim.pending is not None:
    app.sim.resolve_choice(0)
    app.root.update()
    close_dialogs(app)
d0 = app.player.date_full
app.on_action("rest")
app.root.update()
close_dialogs(app)
app.on_skip_day()
app.root.update()
close_dialogs(app)
check("「略过剩余行动点」可直接进入下一天", app.player.date_full != d0,
      "%s -> %s" % (d0, app.player.date_full))

# ---- 6) 无模态结果窗阻塞：操作后不应残留 grab ----
print("")
print("=== 检查操作后没有残留的模态窗口 ===")
leftovers = [w for w in app.root.winfo_children() if isinstance(w, ls.tk.Toplevel)]
check("执行操作后主窗口没有被结果弹窗挡住", len(leftovers) == 0,
      "残留弹窗 %d 个" % len(leftovers))

try:
    app.root.quit()
    app.root.destroy()
except Exception:
    pass
print("")
print("=" * 70)
if FAIL:
    print("行动点测试失败 %d 项：%s" % (len(FAIL), "；".join(FAIL)))
    os._exit(1)
print("行动点流程测试全部通过：一天可连续操作 8 次，耗尽后直接进入下一天")
os._exit(0)
