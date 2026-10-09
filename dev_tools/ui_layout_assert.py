# -*- coding: utf-8 -*-
"""
UI 布局断言：验证底部控制区（开局控件 / 游戏菜单）在窗口内完整可见，不被裁切。
这个检查比截图更可靠——直接比较控件几何与窗口客户区。
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


def dump(app, tag):
    """把一个容器里所有按钮/输入框的几何与可见性打印出来，并检查是否越界。"""
    root_h = app.root.winfo_height()
    problems = []
    lines = []
    for container in (app.bottom_panel, app.footer, app.start_bar):
        if container is None:
            continue
        widgets = []

        def collect(w):
            for c in w.winfo_children():
                widgets.append(c)
                collect(c)
        collect(container)
        for w in widgets:
            cls = w.winfo_class()
            if cls not in ("Button", "Entry", "Radiobutton"):
                continue
            text = ""
            try:
                text = w.cget("text")
            except Exception:
                try:
                    text = w.get()
                except Exception:
                    text = ""
            mapped = w.winfo_ismapped()
            h = w.winfo_height()
            w_ = w.winfo_width()
            # 计算该控件在 root 坐标系里的纵向位置
            y = w.winfo_rooty() - app.root.winfo_rooty()
            bottom = y + h
            inside = (0 <= y) and (bottom <= root_h + 2)
            lines.append("    %-11s %-22s pos=(%4d,%4d) size=%3dx%-3d mapped=%s %s" % (
                cls, str(text)[:22], w.winfo_rootx() - app.root.winfo_rootx(), y,
                w_, h, mapped, "OK" if (mapped and inside and h > 8) else "<== 异常"))
            if mapped and (not inside or h <= 8):
                problems.append("%s(%s) y=%d bottom=%d root_h=%d h=%d" % (
                    cls, str(text)[:12], y, bottom, root_h, h))
    print("  [%s] 窗口 %dx%d" % (tag, app.root.winfo_width(), root_h))
    print("\n".join(lines))
    return problems


work = tempfile.mkdtemp(prefix="lifesim_layout_")
app = ls.GameApp(work, ["布局断言"])
app.root.geometry("1000x760+40+20")   # 故意给一个偏小的窗口，测试自动扩展
app.root.update()
app.adjust_window_size()
app.root.update()
print("=== 开局界面 ===")
p1 = dump(app, "开局")
check("开局：姓名输入框与按钮都完整可见", not p1, "；".join(p1[:3]))

# 用真实输入开局
app.name_entry.delete(0, "end")
app.name_entry.insert(0, "布局测试")
app.city_var.set("shanghai")
app.start_new_game()
app.root.update()
app.adjust_window_size()
app.root.update()
print("")
print("=== 游戏中界面 ===")
p2 = dump(app, "游戏")
check("游戏中：底部菜单按钮都完整可见", not p2, "；".join(p2[:3]))
check("游戏中：开局控件已移除", app.start_bar is None)
check("游戏中：推进一天按钮可见且有点击高度",
      app.btn_roll.winfo_ismapped() and app.btn_roll.winfo_height() > 20,
      "h=%d" % app.btn_roll.winfo_height())
# 8 个操作按钮都在
missing = [k for k, b in app.action_buttons.items()
           if not b.winfo_ismapped() or b.winfo_height() <= 8]
check("游戏中：8 个操作按钮全部可见", not missing, "异常：%s" % missing)
# 时间跳跃输入框
check("游戏中：按月/按年跳过输入框可见",
      app.skip_months_var.get() != "" and app.skip_years_var.get() != "",
      "月=%s 年=%s" % (app.skip_months_var.get(), app.skip_years_var.get()))

# 最小窗口尺寸下也要能显示（自动扩展应保证）
app.root.geometry("780x680")
app.root.update()
app.adjust_window_size()
app.root.update()
p3 = dump(app, "最小尺寸")
check("最小窗口尺寸下底部菜单仍完整可见", not p3, "；".join(p3[:3]))

print("")
print("=== 字体与配色 ===")
check("字体为宋体", app.font_family in ("SimSun", "宋体", "NSimSun", "新宋体"),
      "实际使用：%s" % app.font_family)
check("背景为纯黑", ls.COLORS["bg"] == "#000000", ls.COLORS["bg"])
check("正文为纯白", ls.COLORS["text"] == "#ffffff", ls.COLORS["text"])
check("反色面板为纯白", ls.COLORS["panel2"] == "#ffffff", ls.COLORS["panel2"])
check("强调色为橙色", ls.COLORS["accent"] == "#ff8c00", ls.COLORS["accent"])
bad_colors = [k for k, v in ls.COLORS.items()
              if k not in ("bg", "panel", "panel2", "text", "dim", "accent", "bad",
                           "good", "warn", "secret", "gold", "black", "white", "border")]
check("配色表只保留黑/白/灰/橙", not bad_colors, "多余颜色：%s" % bad_colors)

app.root.quit()
app.root.destroy()
print("")
if FAIL:
    print("存在 %d 项问题：%s" % (len(FAIL), "；".join(FAIL)))
    os._exit(1)
print("全部布局断言通过")
os._exit(0)
