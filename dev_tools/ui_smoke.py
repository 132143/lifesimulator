# -*- coding: utf-8 -*-
"""
界面冒烟测试：真实创建 Tk 窗口，自动驱动游戏若干天，验证界面层不崩溃。
用法：python ui_smoke.py <LifeSimulator.py 路径> [天数]
"""
import importlib.util
import os
import random
import sys
import tempfile

TARGET = sys.argv[1]
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 25

spec = importlib.util.spec_from_file_location("ls", TARGET)
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

work_dir = tempfile.mkdtemp(prefix="lifesim_ui_")
app = ls.GameApp(work_dir, ["界面冒烟测试目录"])
app.root.update()
print("主窗口创建成功：%s" % app.root.title())

# ---------------------------------------------------------------------------
# 布局回归检查：开局控件（姓名输入框 / 城市单选）必须真实可见且有尺寸，
# 不能被中部可伸缩文本区挤压成 1px（历史上出现过这个 bug）。
# ---------------------------------------------------------------------------
all_widgets = []


def _collect(widget):
    for child in widget.winfo_children():
        all_widgets.append(child)
        _collect(child)


_collect(app.start_bar)
entries = [w for w in all_widgets if w.winfo_class() == "Entry"]
radios = [w for w in all_widgets if w.winfo_class() == "Radiobutton"]
assert entries, "开局界面缺少姓名输入框 Entry"
assert len(radios) == 4, "开局界面城市单选按钮数量异常：%d" % len(radios)
entry = entries[0]
assert entry.winfo_ismapped(), "姓名输入框未显示（被布局挤压）"
assert entry.winfo_width() > 40 and entry.winfo_height() > 15, \
    "姓名输入框尺寸异常：%dx%d" % (entry.winfo_width(), entry.winfo_height())
entry.delete(0, "end")
entry.insert(0, "布局检查")
app.root.update()
assert entry.get() == "布局检查", "姓名输入框无法输入"
print("布局回归检查通过：姓名输入框 %dx%d 可见可输入，城市单选 %d 个" % (
    entry.winfo_width(), entry.winfo_height(), len(radios)))

# 最小窗口尺寸下也要可见
app.root.geometry("780x680")
app.root.update()
assert entry.winfo_ismapped() and entry.winfo_width() > 40, "缩小窗口后输入框不可见"
app.root.geometry("900x800")
app.root.update()
print("最小窗口尺寸（780x680）下输入框仍然可见")

# 开局（走主窗口内的开局控件，不弹额外对话框）
app.name_entry.delete(0, "end")
app.name_entry.insert(0, "冒烟测试")
app.city_var.set("harbin")
app.start_new_game()
app.root.update()
print("开局成功：%s @ %s" % (app.player.name, ls.get_city(app.player.city)["name"]))

dialogs_handled = 0


def drive_dialog(button_keys, app_=None):
    """
    扫描当前顶层窗口里的按钮，按给定优先级点击其中一个。
    返回实际点击的按钮文字，找不到返回 None。
    """
    global dialogs_handled
    app_ = app_ or app
    try:
        if not app_.root.winfo_exists():
            return None
        children = app_.root.winfo_children()
    except Exception:
        return None
    for win in children:
        if not isinstance(win, ls.tk.Toplevel):
            continue
        try:
            if not win.winfo_exists():
                continue
        except Exception:
            continue
        buttons = []

        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, ls.tk.Button):
                    buttons.append(child)
                collect(child)
        collect(win)
        if not buttons:
            continue
        chosen = None
        for key in button_keys:
            for btn in buttons:
                if key in btn.cget("text"):
                    chosen = btn
                    break
            if chosen:
                break
        if chosen is None:
            chosen = buttons[0]
        text = chosen.cget("text")
        # 事件弹窗里避免总选"稍后再说"
        if "稍后再说" in text and len(buttons) > 1:
            chosen = buttons[0]
            text = chosen.cget("text")
        try:
            chosen.invoke()
            app_.root.update()
        except Exception:
            pass
        dialogs_handled += 1
        return text
    return None


steps = 0
events_seen = 0
while steps < DAYS and not app.player.dead:
    # 1) 推进一天
    app.on_roll_day()
    app.root.update()
    # 2) 处理事件弹窗（优先选择治疗类选项）
    for _ in range(6):
        clicked = drive_dialog(["治疗", "就医", "医院", "买药", "吃药", "确定",
                                "添置", "口罩", "空调", "报警", "接受", "主动",
                                "告诉老师", "备考", "争取"])
        if clicked is None:
            break
        if "稍后" not in clicked:
            events_seen += 1
    # 3) 每日行动：交替执行
    action = ("rest", "work", "fun")[steps % 3]
    app.on_action(action)
    app.root.update()
    for _ in range(4):
        clicked = drive_dialog(["确定"])
        if clicked is None:
            break
    # 4) 菜单功能抽查
    if steps % 7 == 3:
        app.on_status()
        app.root.update()
        drive_dialog(["确定"])
        app.on_cure()
        app.root.update()
        drive_dialog(["取消", "治疗"])
    if steps % 11 == 5:
        app.on_save()
        app.root.update()
        drive_dialog(["确定"])
        app.on_log()
        app.root.update()
        drive_dialog(["确定"])
    steps += 1

print("已推进 %d 天，处理弹窗 %d 次" % (steps, dialogs_handled))
print("人物状态：%s" % app.player.date_full)
print("健康 %.1f / 幸福 %.1f / 金钱 %.2f / 体温 %.2f℃ / 疾病：%s" % (
    app.player.health, app.player.happy, app.player.money, app.player.temp,
    app.player.disease_names()))

# 存档 / 读档走一遍界面流程
app.on_save()
app.root.update()
drive_dialog(["确定"])
app.on_load()
app.root.update()
drive_dialog(["确定读取", "确定"])
app.root.update()
for _ in range(3):
    if drive_dialog(["确定"]) is None:
        break
print("存档 / 读档流程通过：%s" % app.player.date_full)

# 帮助面板
app.on_help()
app.root.update()
drive_dialog(["确定"])
app.root.update()

# 死亡面板流程（强制死亡）
app.player.health = 0.0
app.sim.kill("冒烟测试结束", None)
app.handle_death(None)
app.root.update()
clicked = drive_dialog(["重新开始"])
print("死亡总结面板流程通过（点击：%s）" % clicked)
app.root.update()
try:
    app.root.quit()
    app.root.destroy()
except Exception:
    pass
print("阶段一完成：[OK] 单人流程无异常")

# ---------------------------------------------------------------------------
# 阶段二：验证「保存并退出」随时可用
# ---------------------------------------------------------------------------
app2 = ls.GameApp(work_dir, ["退出测试目录"])
app2.root.update()
app2.name_entry.delete(0, "end")
app2.name_entry.insert(0, "退出测试")
app2.city_var.set("guangzhou")
app2.start_new_game()
app2.root.update()
for i in range(3):
    app2.on_roll_day()
    app2.root.update()
    for _ in range(4):
        if drive_dialog(["治疗", "买药", "确定"], app2) is None:
            break
    app2.on_action(("rest", "work", "fun")[i % 3])
    app2.root.update()
    for _ in range(3):
        if drive_dialog(["确定"], app2) is None:
            break
before = app2.player.date_full
save_before = os.path.getmtime(app2.save_path) if os.path.exists(app2.save_path) else 0
# 调用保存并退出（面板里点「保存并退出」）
app2.root.after(300, lambda: drive_dialog(["保存并退出"]))
app2.on_quit()
try:
    app2.root.update()
except Exception:
    pass
exists = os.path.exists(app2.save_path)
saved_player, saved_msg = ls.load_game(app2.save_path, rng=random.Random(5))
print("保存并退出：存档文件存在=%s，日期=%s，时间戳变化=%s" % (
    exists, before, (os.path.getmtime(app2.save_path) > save_before) if exists else False))
assert exists, "保存并退出后没有生成存档文件"
assert saved_player is not None, "保存并退出后存档无法读取：%s" % saved_msg
assert saved_player.date_full == before, "存档日期与退出前不一致：%s / %s" % (
    saved_player.date_full, before)
print("阶段二完成：[OK] 保存并退出流程正常，读回日期 = %s" % saved_player.date_full)

# ---------------------------------------------------------------------------
# 阶段三：读取存档后继续游戏
# ---------------------------------------------------------------------------
app3 = ls.GameApp(work_dir, ["读档测试目录"])
app3.root.update()
app3.on_load()
app3.root.update()
drive_dialog(["确定读取", "确定"])
app3.root.update()
for _ in range(3):
    if drive_dialog(["确定"]) is None:
        break
assert app3.player is not None, "读档后没有人物"
app3.on_roll_day()
app3.root.update()
for _ in range(4):
    if drive_dialog(["治疗", "买药", "确定"]) is None:
        break
app3.on_action("work")
app3.root.update()
for _ in range(3):
    if drive_dialog(["确定"]) is None:
        break
print("阶段三完成：[OK] 读档并继续游戏，当前 %s" % app3.player.date_full)

# ---------------------------------------------------------------------------
# 收尾：关闭所有窗口并退出 Tk，避免残留事件循环导致进程挂住
# ---------------------------------------------------------------------------
for app_obj in (app, app2, app3):
    try:
        app_obj.hide_start_controls()
    except Exception:
        pass
    try:
        for win in list(app_obj.root.winfo_children()):
            if isinstance(win, ls.tk.Toplevel):
                try:
                    win.grab_release()
                    win.destroy()
                except Exception:
                    pass
        app_obj.root.quit()
        app_obj.root.destroy()
    except Exception:
        pass
print("界面冒烟测试全部通过：[OK]")
sys.stdout.flush()
os._exit(0)
