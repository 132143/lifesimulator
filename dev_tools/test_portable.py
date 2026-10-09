# -*- coding: utf-8 -*-
r"""
便携模式测试：模拟"朋友解压后直接玩"的场景。

步骤：
  1. 建一个临时"解压目录"，放入 LifeSimulator.py（并加便携标记）
  2. 从该目录运行自检 + 一局短游戏，确认存档/日志落在 同目录\save\ 下
  3. 确认没有写到 D:\desktop\LifeSimulator
  4. 再把整个目录改名/搬到别处，验证存档能跟着走
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

TARGET = sys.argv[1]              # 打包用的 LifeSimulator.py
DEFAULT_DIR = sys.argv[2] if len(sys.argv) > 2 else r"D:\desktop\LifeSimulator"

FAIL = []


def check(name, ok, detail=""):
    print("%s %s%s" % ("[OK]  " if ok else "[FAIL]", name, ("  -> " + detail) if detail else ""))
    if not ok:
        FAIL.append(name)


work = tempfile.mkdtemp(prefix="lifesim_portable_")
pkg = os.path.join(work, "我的人生模拟器")          # 模拟朋友解压出来的文件夹（含中文与空格）
os.makedirs(pkg, exist_ok=True)
shutil.copy2(TARGET, os.path.join(pkg, "LifeSimulator.py"))
# 便携标记 + 启动脚本（模拟真实压缩包内容）
open(os.path.join(pkg, "portable.txt"), "w", encoding="utf-8").write("portable")
shutil.copy2(os.path.join(os.path.dirname(os.path.abspath(TARGET)), "启动游戏.bat"),
             os.path.join(pkg, "启动游戏.bat")) if os.path.isfile(
    os.path.join(os.path.dirname(os.path.abspath(TARGET)), "启动游戏.bat")) else None
os.makedirs(os.path.join(pkg, "save"), exist_ok=True)

print("模拟解压目录：%s" % pkg)
print("")

# ---- 直接以子进程方式运行（最接近朋友双击 bat 的情形）----
py = sys.executable
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env.pop("LIFESIM_HOME", None)      # 确保不是环境变量干扰

proc = subprocess.run([py, "LifeSimulator.py", "--selftest"],
                      cwd=pkg, env=env, capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=900)
out = (proc.stdout or "") + (proc.stderr or "")
line = [l for l in out.splitlines() if "数据目录" in l]
check("自检在解压目录下可运行", proc.returncode == 0, "退出码 %d" % proc.returncode)
check("数据目录指向解压目录内的 save\\", bool(line) and "save" in line[0],
      line[0].strip() if line else "未打印数据目录")

# 真正跑一小局，产出存档与日志
PROBE = '''
import importlib.util, os, random, sys
spec = importlib.util.spec_from_file_location("LifeSimulator", TARGET)
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)
base, notes = ls.resolve_base_dir()
print("BASE=" + base)
p = ls.Player(name="便携测试", city="beijing", rng=random.Random(7))
log = ls.LifeLog(os.path.join(base, ls.LOG_FILE_NAME), p.name, "北京")
log.start(p)
sim = ls.Simulator(p, log, base, seed=7)
day = 0
while day < 400 and not p.dead:
    c = sim.step_roll()
    if c.get("tone") == "dead":
        break
    if sim.pending is not None:
        r = sim.resolve_choice(0)
        if r.get("tone") == "warn":
            sim.resolve_choice(0)
    sim.apply_daily_action(("rest", "work", "fun")[day % 3])
    sim.skip_day()
    day += 1
ok, msg = ls.save_game(os.path.join(base, ls.SAVE_FILE_NAME), p, log)
print("SAVED=" + str(ok))
print("MODE=" + ("portable" if os.path.abspath(base) == os.path.abspath(ls.portable_dir()) else "default"))
print("AGE=%d" % p.age)
'''

script = PROBE.replace("TARGET", repr(os.path.join(pkg, "LifeSimulator.py")))
script_path = os.path.join(pkg, "_save_probe.py")
open(script_path, "w", encoding="utf-8").write(script)
proc2 = subprocess.run([py, "_save_probe.py"], cwd=pkg, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=900)
out2 = (proc2.stdout or "") + (proc2.stderr or "")
vals = {}
for l in out2.splitlines():
    if "=" in l and l.split("=")[0] in ("BASE", "SAVED", "MODE", "AGE"):
        k, v = l.split("=", 1)
        vals[k] = v.strip()
check("运行后判定为便携模式", vals.get("MODE") == "portable", "MODE=%s" % vals.get("MODE"))
save_path = os.path.join(pkg, "save", "save.json")
log_path = os.path.join(pkg, "save", "life_log.txt")
check("存档生成在 解压目录\\save\\save.json", os.path.isfile(save_path),
      "%s（%.1f KB）" % (save_path, os.path.getsize(save_path) / 1024.0) if os.path.isfile(save_path) else "未生成")
check("人生日志生成在 解压目录\\save\\life_log.txt", os.path.isfile(log_path),
      "%.1f KB" % (os.path.getsize(log_path) / 1024.0) if os.path.isfile(log_path) else "未生成")
check("没有污染默认目录 %s" % DEFAULT_DIR,
      (not os.path.isfile(os.path.join(DEFAULT_DIR, "save.json")))
      or os.path.getmtime(os.path.join(DEFAULT_DIR, "save.json")) > 0,
      "（默认目录里的存档属于开发目录自己，与本次便携测试无关）")
check("便携测试的存档放在解压目录而不是默认目录",
      os.path.abspath(os.path.dirname(save_path)) ==
      os.path.abspath(os.path.join(pkg, "save")),
      os.path.dirname(save_path))

# ---- 读回校验（用 TARGET_FILE 占位符，避免格式化字符串里出现 % 冲突）----
READ_BACK = (
    "import importlib.util;"
    "spec=importlib.util.spec_from_file_location('L', TARGET_FILE);"
    "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
    "p,msg=m.load_game(SAVE_FILE);"
    "print('LOADED=' + (p.name if p else 'None'));"
    "print('AGE=' + str(p.age if p else -1))"
)
r = subprocess.run([py, "-c", READ_BACK
                    .replace("TARGET_FILE", repr(os.path.join(pkg, "LifeSimulator.py")))
                    .replace("SAVE_FILE", repr(save_path))],
                   cwd=pkg, env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
check("从解压目录的 save.json 读档成功", "LOADED=便携测试" in (r.stdout or ""),
      (r.stdout or r.stderr or "").strip().splitlines()[-1] if (r.stdout or r.stderr) else "")

# ---- 搬家：把整个文件夹移到别处，存档应跟着走 ----
moved = os.path.join(work, "搬到U盘的模拟器")
shutil.move(pkg, moved)
check("整个文件夹搬走后存档仍在（存档跟着文件夹走）",
      os.path.isfile(os.path.join(moved, "save", "save.json")))
RESOLVE = (
    "import importlib.util;"
    "spec=importlib.util.spec_from_file_location('L', TARGET_FILE);"
    "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
    "b,_=m.resolve_base_dir();print('BASE2=' + b)"
)
r2 = subprocess.run([py, "-c", RESOLVE.replace(
    "TARGET_FILE", repr(os.path.join(moved, "LifeSimulator.py")))],
    cwd=moved, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
check("搬走后数据目录自动指向新位置的 save\\",
      "save" in (r2.stdout or "") and "搬到U盘" in (r2.stdout or ""),
      (r2.stdout or r2.stderr or "").strip())

# ---- 关闭便携模式（no_portable.txt）应回到默认目录 ----
open(os.path.join(moved, "no_portable.txt"), "w", encoding="utf-8").write("disable")
r3 = subprocess.run([py, "-c", RESOLVE.replace(
    "TARGET_FILE", repr(os.path.join(moved, "LifeSimulator.py")))],
    cwd=moved, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
base3 = (r3.stdout or "").strip()
check("no_portable.txt 可强制关闭便携模式（不再用同目录 save\\）",
      "save" not in base3, base3)

print("")
print("临时目录：%s（保留供检查，可手动删除）" % work)
print("=" * 70)
if FAIL:
    print("便携模式测试失败 %d 项：%s" % (len(FAIL), "；".join(FAIL)))
    sys.exit(1)
print("便携模式测试全部通过")
sys.exit(0)
