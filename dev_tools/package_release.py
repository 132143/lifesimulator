# -*- coding: utf-8 -*-
"""
打包脚本：生成"解压即玩"的分发压缩包。

用法：
    python dev_tools/package_release.py                  # 打包当前项目
    python dev_tools/package_release.py --out D:\\         # 指定输出目录
    python dev_tools/package_release.py --with-source      # 附带模块化源码(开发者用)
    python dev_tools/package_release.py --zip-name 自定义名

产物：
    LifeSimulator_v<版本>_便携版.zip
      解压后双击「启动游戏.bat」即可玩，存档就在解压目录的 save\\ 里。
"""
import argparse
import datetime
import os
import shutil
import sys
import zipfile

APP_NAME = "LifeSimulator"
APP_VERSION = "3.0"

#: 玩家版必需文件：(源路径相对项目根, 压缩包内相对路径)
PLAYER_FILES = [
    ("LifeSimulator.py", "LifeSimulator.py"),
    ("启动游戏.bat", "启动游戏.bat"),
    ("使用说明.txt", "使用说明.txt"),
    ("README.md", "README.md"),
    ("docs/模组开发指南.md", "docs/模组开发指南.md"),
    ("docs/打包与分发指南.md", "docs/打包与分发指南.md"),
]

#: 开发者附加内容（--with-source 时加入）
DEV_FILES = [
    ("dev_tools/part1_header.py", "dev_tools/part1_header.py"),
    ("dev_tools/part2_city_disease.py", "dev_tools/part2_city_disease.py"),
    ("dev_tools/part3_events.py", "dev_tools/part3_events.py"),
    ("dev_tools/part4_player_engine.py", "dev_tools/part4_player_engine.py"),
    ("dev_tools/part5_ui_main.py", "dev_tools/part5_ui_main.py"),
    ("dev_tools/assemble.ps1", "dev_tools/assemble.ps1"),
    ("dev_tools/test_v2.py", "dev_tools/test_v2.py"),
    ("dev_tools/test_v3.py", "dev_tools/test_v3.py"),
    ("dev_tools/acceptance.py", "dev_tools/acceptance.py"),
    ("dev_tools/ui_smoke.py", "dev_tools/ui_smoke.py"),
    ("dev_tools/ui_layout_assert.py", "dev_tools/ui_layout_assert.py"),
    ("dev_tools/lifespan.py", "dev_tools/lifespan.py"),
    ("dev_tools/ushape.py", "dev_tools/ushape.py"),
    ("dev_tools/balance.py", "dev_tools/balance.py"),
    ("dev_tools/calibrate.py", "dev_tools/calibrate.py"),
    ("dev_tools/package_release.py", "dev_tools/package_release.py"),
]

#: 便携模式标记（放在压缩包根目录，让存档落在同文件夹）
PORTABLE_MARKER_NAME = "portable.txt"
PORTABLE_MARKER_TEXT = """这个文件代表"便携模式"。
有它在，游戏会把存档、日志放在本文件夹的 save\\ 目录里，
整个文件夹可以随意拷贝/备份/带走，存档跟着走。
（删掉它，游戏就会改用系统默认目录保存）"""


def bat_bytes(text):
    """
    把批处理脚本文本转成"中文 Windows cmd 能正确解析"的字节：
        1. 行尾统一为 CRLF（cmd 用 LF 会错乱解析，把中文/引号拆成命令）
        2. 编码用 GBK/cp936（cmd 默认代码页；UTF-8 中文会变乱码并报
           "'ho' 不是内部或外部命令" 这类错误）
        3. 不带 BOM
    返回 bytes。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    for enc in ("gbk", "cp936", "utf-8"):
        try:
            return text.encode(enc)
        except UnicodeEncodeError:
            continue
    return text.encode("utf-8", "replace")


def read_text_auto(path):
    """自动尝试 utf-8 / utf-8-sig / gbk 读取文本。"""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def find_project_root():
    """
    定位"待打包项目"的根目录（含 LifeSimulator.py 的目录）。
    查找顺序：
        1. 当前工作目录及其向上两层（从项目根运行时最准）
        2. 脚本所在目录及其向上两层（脚本放在 dev_tools/ 或 build/ 里时）
    """
    cands = []
    cwd = os.getcwd()
    cands.append(cwd)
    cands.append(os.path.dirname(cwd))
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(here)
    cands.append(os.path.dirname(here))
    cands.append(os.path.dirname(os.path.dirname(here)))
    seen = set()
    for cand in cands:
        if not cand:
            continue
        key = os.path.normcase(os.path.abspath(cand))
        if key in seen:
            continue
        seen.add(key)
        # 必须同时有主程序与启动脚本，才算"可打包的项目根"
        if (os.path.isfile(os.path.join(cand, "LifeSimulator.py"))
                and os.path.isfile(os.path.join(cand, "启动游戏.bat"))):
            return cand
    for cand in cands:
        if cand and os.path.isfile(os.path.join(cand, "LifeSimulator.py")):
            return cand
    return cwd


def build_release(root, out_dir, zip_name, with_source=False, keep_stage=False):
    """构建压缩包，返回 (zip 路径, 打包文件数, 总字节数)。"""
    files = list(PLAYER_FILES)
    if with_source:
        files += DEV_FILES

    missing = [src for src, _dst in files if not os.path.isfile(os.path.join(root, src))]
    if missing:
        raise SystemExit("缺少文件，无法打包：\n  " + "\n  ".join(missing))

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, zip_name)

    total_bytes = 0
    packed = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for src, dst in files:
            full = os.path.join(root, src)
            if dst.lower().endswith(".bat"):
                # 批处理脚本必须转成 CRLF + GBK，否则中文 Windows 的 cmd 会报
                # "'ho' 不是内部或外部命令" 这类乱码错误
                data = bat_bytes(read_text_auto(full))
                zf.writestr(dst, data)
                total_bytes += len(data)
            else:
                zf.write(full, dst)
                total_bytes += os.path.getsize(full)
            packed += 1
        # 便携标记
        zf.writestr(PORTABLE_MARKER_NAME, PORTABLE_MARKER_TEXT)
        packed += 1
        # 空目录：确保解压后就有 save/ 与 mods/（存档、模组位置一目了然）
        for d in ("save/", "save/mods/"):
            info = zipfile.ZipInfo(d)
            info.external_attr = 0o40755 << 16       # 目录属性
            info.date_time = datetime.datetime.now().timetuple()[:6]
            zf.writestr(info, "")
            packed += 1
        # 版本说明
        zf.writestr("版本信息.txt", (
            "弹窗式文字人生模拟器\n"
            "版本：v%s（便携版）\n"
            "打包时间：%s\n"
            "运行环境：Python 3.8+（自带 tkinter 即可，无需第三方库）\n"
            "启动方式：双击「启动游戏.bat」\n"
            "存档位置：本文件夹下的 save\\（save.json + life_log.txt）\n"
        ) % (APP_VERSION, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        packed += 1
    return zip_path, packed, total_bytes


def main():
    parser = argparse.ArgumentParser(description="打包便携版发行压缩包")
    parser.add_argument("--out", default=None, help="输出目录（默认：项目根目录下的 release/）")
    parser.add_argument("--zip-name", default=None, help="压缩包文件名")
    parser.add_argument("--with-source", action="store_true", help="附带模块化源码与测试脚本")
    args = parser.parse_args()

    root = find_project_root()
    out_dir = args.out or os.path.join(root, "release")
    suffix = "_含源码" if args.with_source else "_便携版"
    zip_name = args.zip_name or "%s_v%s%s.zip" % (APP_NAME, APP_VERSION, suffix)

    print("项目根目录：%s" % root)
    zip_path, packed, total = build_release(root, out_dir, zip_name, args.with_source)

    size = os.path.getsize(zip_path)
    print("")
    print("打包完成：[OK]")
    print("  压缩包：%s" % zip_path)
    print("  条目数：%d（含 %s 与 save/ 空目录）" % (packed, PORTABLE_MARKER_NAME))
    print("  原始大小：%.1f KB    压缩后：%.1f KB（压缩率 %.0f%%）" % (
        total / 1024.0, size / 1024.0, (1 - size / float(max(1, total))) * 100))
    print("")
    print("  拿到压缩包的朋友只需要：")
    print("    1) 解压到任意文件夹（路径别带奇怪符号即可）")
    print("    2) 双击「启动游戏.bat」")
    print("    3) 存档会自动写进解压目录的 save\\ 里，整个文件夹可随意拷贝")
    if not args.with_source:
        print("")
        print("  想额外附带模块化源码与测试：加 --with-source 再打一次")
    return 0


if __name__ == "__main__":
    sys.exit(main())
