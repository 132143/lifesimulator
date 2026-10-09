# -*- coding: utf-8 -*-
"""
把游戏打包成**免安装 exe**（朋友不需要装 Python）。

用法（在项目根目录执行）：
    python dev_tools/build_exe.py                  # 打包 + 生成 release\\LifeSimulator_v3.0_免安装版.zip
    python dev_tools/build_exe.py --no-zip         # 只生成 exe，不压缩
    python dev_tools/build_exe.py --console        # 保留控制台窗口（排查问题用）

前置：本机需要 PyInstaller（会用到第三方库，仅打包时需要，游戏运行不需要）：
    python -m pip install pyinstaller

产物：
    build_exe\\dist\\LifeSimulator.exe
    release\\LifeSimulator_v3.0_免安装版.zip
      解压后双击「启动游戏.exe.bat」或直接双击 LifeSimulator.exe 即可玩，
      存档在解压目录的 save\\ 里（便携模式）。

为什么需要 run_frozen.py：
    主程序是单文件、靠 importlib 动态加载的；PyInstaller 的静态分析看不到它，
    所以用一个显式 import 的引导脚本把它纳入依赖收集。
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
import zipfile

APP_NAME = "LifeSimulator"
APP_VERSION = "3.0"
ZIP_NAME = "%s_v%s_免安装版.zip" % (APP_NAME, APP_VERSION)
BOOTSTRAP = "run_frozen.py"
LAUNCHER_SRC = "launcher_exe_ascii.bat"     # 纯 ASCII 源，打包时转成 GBK
LAUNCHER_NAME = "启动游戏.bat"

#: 压缩包内附带文件：(源相对项目根, 包内路径)
EXTRA_FILES = [
    ("启动游戏.bat", LAUNCHER_NAME),        # 开发者可直接用的 bat（源码版启动）
    ("使用说明.txt", "使用说明.txt"),
    ("README.md", "README.md"),
    ("docs/模组开发指南.md", "docs/模组开发指南.md"),
    ("docs/打包与分发指南.md", "docs/打包与分发指南.md"),
]

PORTABLE_MARKER_NAME = "portable.txt"
PORTABLE_MARKER_TEXT = """这个文件代表"便携模式"。
有它在，游戏会把存档、日志放在本文件夹的 save\\ 目录里，
整个文件夹可以随意拷贝/备份/带走，存档跟着走。
"""

#: 免安装版专用说明（替换掉"需要装 Python"的内容）
EXE_README = """========================================================
     弹窗式文字人生模拟器  免安装版（不用装 Python）
========================================================

【怎么开始玩】
  1. 双击「LifeSimulator.exe」即可
     （如果双击没反应，就双击「启动游戏.bat」）
  2. 弹出的窗口就是游戏，输入名字、选城市，点「开始新的人生」
  3. 退出时点「保存并退出」，或直接关窗口（会提示是否保存）

【存档在哪？能带走吗？】
  存档就在本文件夹的 save 文件夹里：
      save\\save.json        你的进度
      save\\life_log.txt     人生日志
      save\\mods\\           模组放这里
  整个文件夹可以随便拷贝 / 放 U 盘 / 发给别人，存档跟着走。

【常见问题】
  Q: 双击 exe 没反应 / 被杀毒软件拦截？
  A: 这是 PyInstaller 打包程序的常见误报，添加信任即可；
     或者改用「启动游戏.bat」。

  Q: 提示缺 VCRUNTIME140.dll 之类的？
  A: 装一次「Microsoft Visual C++ 运行库」即可（微软官网免费下载）。

  Q: 启动有点慢（几秒）？
  A: 免安装版是自解压的单文件程序，首次启动会慢几秒，属正常现象。

  Q: 想开两个存档一起玩？
  A: 把整个文件夹复制一份，两份各有独立的 save，互不干扰。

【玩法要点】
  * 每个游戏内的一天可以操作 8 次：休息/工作/娱乐/学习/社交/锻炼/夫妻亲密/陪伴孩子
  * 点「推进一天」掷骰抽事件；不想做事就点「跳过这一天」
  * 四项属性：健康（归零就死）/ 幸福（长期低于 20 掉健康）/ 金钱（可负债）/ 体温
  * 开局随机给「体质」和「家境」：体质好很少生病，家境决定父母能给你多少生活费
  * 人生流程：婴幼儿→学龄前→幼儿园→小学→初中→中考→高中→高考→大学→读研→工作→退休
  * 结婚后可以「夫妻亲密」提升幸福度，也可能怀上孩子（可选避孕方式）
  * 共 36 种常见疾病，寿命一般在 80 岁上下

祝你在里面活出精彩的一生。
"""


def collect_mod_files(root):
    """收集 mods/ 目录下的模组文件（发行包要带上，否则模组不会加载）。"""
    out = []
    mods_dir = os.path.join(root, "mods")
    if not os.path.isdir(mods_dir):
        return out
    for dirpath, _dirnames, filenames in os.walk(mods_dir):
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            out.append((rel, rel))
    return out


def bat_bytes(text):
    """批处理脚本转成 CRLF + GBK（中文 Windows cmd 专用），不带 BOM。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    for enc in ("gbk", "cp936", "utf-8"):
        try:
            return text.encode(enc)
        except UnicodeEncodeError:
            continue
    return text.encode("utf-8", "replace")


def read_text_auto(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def find_project_root():
    """找到含 LifeSimulator.py 与 run_frozen.py 的项目根目录。"""
    cands = [os.getcwd(), os.path.dirname(os.getcwd())]
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))]
    seen = set()
    for cand in cands:
        if not cand:
            continue
        c = os.path.normcase(os.path.abspath(cand))
        if c in seen:
            continue
        seen.add(c)
        if (os.path.isfile(os.path.join(cand, "LifeSimulator.py"))
                and os.path.isfile(os.path.join(cand, BOOTSTRAP))):
            return cand
    for cand in cands:
        if cand and os.path.isfile(os.path.join(cand, "LifeSimulator.py")):
            return cand
    return os.getcwd()


def run(cmd, cwd=None, label=""):
    print("  $ %s" % " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    ok = proc.returncode == 0
    if not ok:
        print("    [失败] 退出码 %d" % proc.returncode)
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-12:]
        for line in tail:
            print("      " + line)
    elif label:
        print("    [OK] %s" % label)
    return ok, (proc.stdout or "") + (proc.stderr or "")


def main():
    parser = argparse.ArgumentParser(description="打包免安装 exe 版本")
    parser.add_argument("--no-zip", action="store_true", help="只生成 exe，不压 zip")
    parser.add_argument("--console", action="store_true", help="保留控制台窗口（排查用）")
    parser.add_argument("--onefile", action="store_true",
                        help="打成单文件 exe（默认是目录式；单文件在受限环境可能启动失败）")
    parser.add_argument("--out", default=None, help="zip 输出目录（默认项目下 release/）")
    args = parser.parse_args()

    root = find_project_root()
    out_dir = args.out or os.path.join(root, "release")
    work = os.path.join(root, "build_exe")
    print("项目根目录：%s" % root)
    print("构建目录  ：%s" % work)
    print("")

    if not os.path.isfile(os.path.join(root, BOOTSTRAP)):
        raise SystemExit("缺少引导脚本 %s（应与 LifeSimulator.py 在同一目录）" % BOOTSTRAP)

    # ---- 0) 检查 PyInstaller ----
    print("[1/5] 检查 PyInstaller")
    ok, out = run([sys.executable, "-m", "PyInstaller", "--version"])
    if not ok:
        print("")
        print("未安装 PyInstaller，正在自动安装（仅打包需要，游戏运行不需要）……")
        ok2, _ = run([sys.executable, "-m", "pip", "install", "--no-input",
                      "--disable-pip-version-check", "pyinstaller"])
        if not ok2:
            raise SystemExit("PyInstaller 安装失败，请手动执行：\n"
                             "    python -m pip install pyinstaller")
    print("")

    # ---- 1) 调用 PyInstaller ----
    # 默认用 --onedir（启动快、兼容性好，不需要往临时目录解压）；
    # 加 --onefile 可打成单文件，但某些受限环境（临时目录被策略限制）会启动失败。
    mode_label = "单文件 (--onefile)" if args.onefile else "目录式 (--onedir，推荐)"
    print("[2/5] 用 PyInstaller 打包 exe：%s（首次约 1~3 分钟）" % mode_label)
    cmd = [sys.executable, "-m", "PyInstaller",
           "--noconfirm", "--clean",
           "--name", APP_NAME,
           "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "build"),
           "--specpath", work,
           "--paths", root,                     # 让分析器能找到 LifeSimulator 模块
           "--hidden-import", "LifeSimulator",  # 显式声明，防漏
           ]
    cmd.append("--onefile" if args.onefile else "--onedir")
    cmd += ["--console"] if args.console else ["--windowed"]
    cmd.append(os.path.join(root, BOOTSTRAP))
    ok, out = run(cmd, cwd=root)
    if not ok:
        raise SystemExit("PyInstaller 打包失败，请查看上面的输出。")
    if args.onefile:
        exe_path = os.path.join(work, "dist", APP_NAME + ".exe")
        exe_src_dir = None
    else:
        exe_src_dir = os.path.join(work, "dist", APP_NAME)
        exe_path = os.path.join(exe_src_dir, APP_NAME + ".exe")
    if not os.path.isfile(exe_path):
        raise SystemExit("没有找到生成的 exe：%s" % exe_path)
    exe_mb = os.path.getsize(exe_path) / (1024.0 * 1024.0)
    print("    生成：%s（exe %.1f MB）" % (exe_path, exe_mb))
    if exe_src_dir:
        total = sum(os.path.getsize(os.path.join(dp, f))
                    for dp, _dn, fns in os.walk(exe_src_dir) for f in fns)
        print("    运行文件夹总大小：%.1f MB" % (total / (1024.0 * 1024.0)))
    print("")

    if args.no_zip:
        print("已按要求跳过压缩（--no-zip）。")
        return 0

    # ---- 2) 组装发行目录 ----
    print("[3/5] 组装发行内容")
    stage = os.path.join(work, "stage")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)
    if exe_src_dir:
        # 目录式：把 exe 与 _internal 一起平铺到发行根目录
        for item in os.listdir(exe_src_dir):
            src = os.path.join(exe_src_dir, item)
            dst = os.path.join(stage, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        print("    已复制 exe 运行文件夹（%d 个文件）"
              % sum(len(fns) for _dp, _dn, fns in os.walk(stage)))
    else:
        shutil.copy2(exe_path, os.path.join(stage, APP_NAME + ".exe"))

    # 启动 bat（给"双击 exe 没反应"或被杀软拦截的情况兜底）
    launcher_src = os.path.join(root, "build", LAUNCHER_SRC)
    if not os.path.isfile(launcher_src):
        launcher_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), LAUNCHER_SRC)
    if os.path.isfile(launcher_src):
        with open(os.path.join(stage, LAUNCHER_NAME), "wb") as fh:
            fh.write(bat_bytes(read_text_auto(launcher_src)))
        print("    已生成 %s" % LAUNCHER_NAME)
    else:
        print("    [提示] 未找到 %s，跳过启动脚本" % LAUNCHER_SRC)

    # 便携标记
    with open(os.path.join(stage, PORTABLE_MARKER_NAME), "w", encoding="utf-8") as fh:
        fh.write(PORTABLE_MARKER_TEXT)
    # 免安装版说明
    with open(os.path.join(stage, "使用说明.txt"), "w", encoding="utf-8") as fh:
        fh.write(EXE_README)
    # 其他文档
    for src, dst in EXTRA_FILES:
        if os.path.basename(src) in ("使用说明.txt", LAUNCHER_NAME):
            continue          # 上面已用免安装版内容覆盖
        full = os.path.join(root, src)
        if os.path.isfile(full):
            target = os.path.join(stage, dst)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(full, target)
    # 模组文件（若项目里有 mods/ 就一起带上）
    mod_files = collect_mod_files(root)
    for src_rel, dst_rel in mod_files:
        full = os.path.join(root, src_rel)
        target = os.path.join(stage, dst_rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(open(full, "rb").read())
    if mod_files:
        print("    已带上 %d 个模组文件（mods/）" % len(mod_files))

    # 存档与模组空目录
    os.makedirs(os.path.join(stage, "save", "mods"), exist_ok=True)
    with open(os.path.join(stage, "版本信息.txt"), "w", encoding="utf-8") as fh:
        fh.write("弹窗式文字人生模拟器\n版本：v%s（免安装版）\n"
                 "打包时间：%s\n运行环境：Windows，无需安装 Python\n"
                 "启动方式：双击 %s.exe（或 启动游戏.bat）\n"
                 "存档位置：本文件夹下的 save\\（save.json + life_log.txt）\n"
                 % (APP_VERSION, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    APP_NAME))
    print("")

    # ---- 3) 压缩 ----
    print("[4/5] 生成压缩包")
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, ZIP_NAME)
    total = 0
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for dirpath, _dirnames, filenames in os.walk(stage):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, stage).replace("\\", "/")
                zf.write(full, rel)
                total += os.path.getsize(full)
                count += 1
        for d in ("save/", "save/mods/"):
            info = zipfile.ZipInfo(d)
            info.external_attr = 0o40755 << 16
            info.date_time = datetime.datetime.now().timetuple()[:6]
            zf.writestr(info, "")
            count += 1
    size = os.path.getsize(zip_path)
    print("    压缩包：%s" % zip_path)
    print("")

    # ---- 4) 汇总 ----
    print("[5/5] 完成")
    print("  条目数  ：%d" % count)
    print("  原始大小：%.1f KB    压缩后：%.1f KB" % (total / 1024.0, size / 1024.0))
    print("  exe 大小：%.1f MB（单文件，免安装 Python）" % exe_mb)
    print("")
    print("  朋友拿到压缩包后：")
    print("    1) 解压到任意文件夹")
    print("    2) 双击“%s.exe”（双击没反应就用“%s”）" % (APP_NAME, LAUNCHER_NAME))
    print("    3) 存档自动写进解压目录的 save\\，整个文件夹可随意拷贝")
    return 0


if __name__ == "__main__":
    sys.exit(main())
