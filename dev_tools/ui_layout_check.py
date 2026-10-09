# -*- coding: utf-8 -*-
"""
UI 布局检查：真实创建窗口，列出开局界面所有控件的类型、文字与屏幕坐标，
确认姓名输入框、城市单选、开始/读取按钮确实存在于主窗口并可见可点。
用法：python ui_layout_check.py <LifeSimulator.py>
"""
import importlib.util
import sys
import tempfile

spec = importlib.util.spec_from_file_location("ls", sys.argv[1])
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)

work = tempfile.mkdtemp(prefix="lifesim_layout_")
app = ls.GameApp(work, ["布局检查目录"])
app.root.update()
app.root.deiconify()
app.root.lift()
app.root.update_idletasks()
app.root.update()

print("窗口标题：%s" % app.root.title())
print("窗口尺寸：%dx%d  位置 +%d+%d" % (
    app.root.winfo_width(), app.root.winfo_height(),
    app.root.winfo_rootx(), app.root.winfo_rooty()))
print("")
print("=== 顶层子控件（pack 顺序即布局优先级）===")
for child in app.root.pack_slaves():
    print("  %-12s y=%4d h=%3d %s" % (
        child.winfo_class(), child.winfo_y(), child.winfo_height(),
        "（底部区域）" if child.winfo_y() > app.root.winfo_height() * 0.7 else ""))

print("")
print("=== 开局区域（start_bar）内控件 ===")
found_entry = None
found_radios = []
found_buttons = []
if getattr(app, "start_bar", None) is not None:
    def walk(widget, depth=1):
        for child in widget.winfo_children():
            cls = child.winfo_class()
            text = ""
            try:
                text = child.cget("text")
            except Exception:
                pass
            try:
                text = text or child.get()
            except Exception:
                pass
            visible = child.winfo_ismapped()
            geo = "x=%d y=%d w=%d h=%d" % (
                child.winfo_x(), child.winfo_y(),
                child.winfo_width(), child.winfo_height())
            print("  %s%-10s %-28s %s %s" % (
                "  " * depth, cls, str(text)[:28], geo,
                "可见" if visible else "未显示"))
            if cls == "Entry":
                found_entry = child
            elif cls == "Radiobutton":
                found_radios.append(child)
            elif cls == "Button":
                found_buttons.append(child)
            walk(child, depth + 1)
    walk(app.start_bar)
else:
    print("  [错误] start_bar 不存在！")

print("")
print("=== 结论 ===")
# 递归查找（输入框嵌在 row1 里，不能只看直接子控件）
all_widgets = []


def collect_all(widget):
    for child in widget.winfo_children():
        all_widgets.append(child)
        collect_all(child)


collect_all(app.start_bar)
entries = [w for w in all_widgets if w.winfo_class() == "Entry"]
radios = [w for w in all_widgets if w.winfo_class() == "Radiobutton"]
buttons = [w for w in all_widgets if w.winfo_class() == "Button"]
entry = entries[0] if entries else None

print("姓名输入框 Entry 存在：%s" % (entry is not None))
entry_ok = False
if entry is not None:
    print("  尺寸 = %dx%d  可见 = %s  状态 = %s" % (
        entry.winfo_width(), entry.winfo_height(), entry.winfo_ismapped(),
        entry.cget("state")))
    entry.delete(0, "end")
    entry.insert(0, "测试输入")
    app.root.update()
    readback = entry.get()
    print("  写入并读回 = %r" % readback)
    entry_ok = (readback == "测试输入" and entry.winfo_ismapped()
                and entry.winfo_width() > 40 and entry.winfo_height() > 15)
print("城市单选按钮数量：%d -> %s" % (len(radios), [r.cget("text") for r in radios]))
print("按钮：%s" % [b.cget("text") for b in buttons])

# 实测：输入姓名 + 选择城市 -> 开局后人物是否真的用了这些值
app.city_var.set("guangzhou")
app.start_new_game()
app.root.update()
name_ok = (app.player.name == "测试输入" and app.player.city == "guangzhou")
print("")
print("开局结果：姓名 = %r（期望 '测试输入'），城市 = %s（期望 guangzhou）" % (
    app.player.name, app.player.city))

print("")
print("=== 最终判定 ===")
print("[%s] 主窗口底部存在姓名输入框且可输入" % ("OK" if entry_ok else "FAIL"))
print("[%s] 主窗口底部存在 4 个城市单选按钮" % ("OK" if len(radios) == 4 else "FAIL"))
print("[%s] 输入的姓名与所选城市被正确用于开局" % ("OK" if name_ok else "FAIL"))
print("[%s] 开局后游戏菜单（推进一天等按钮）正常显示" % (
    "OK" if app.footer.winfo_ismapped() and app.btn_roll.winfo_ismapped() else "FAIL"))

app.root.quit()
app.root.destroy()
import os
os._exit(0 if (entry_ok and len(radios) == 4 and name_ok) else 1)
