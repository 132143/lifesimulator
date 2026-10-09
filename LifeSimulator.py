# -*- coding: utf-8 -*-
"""
================================================================================
                弹窗式文字人生模拟器  Life Simulator  (Tkinter)
================================================================================

玩法简介
--------
* 你将从 0 岁开始人生，以「天」为最小推进单位（30 天 = 1 月，12 月 = 1 年）。
* 每个"操作日"推进后，会先用跑团骰子判定触发一个事件，然后弹出每日操作菜单。
* 四项核心属性：
    - 健康 100（上限 100 / 下限 0，归零即死亡）
    - 幸福  50（0 ~ 100，长期低于 20 会持续扣健康）
    - 金钱 1000（可负债、无上限）
    - 体温 36.5（正常 36.0 ~ 37.0，过高/过低每日扣健康）
* 开局选择城市：哈尔滨（寒冷） / 北京（温带） / 上海（亚热带） / 广州（炎热），
  城市决定环境气候事件的概率与体温波动幅度，选择后永久生效。
* 所有随机结果都通过骰子（d100 / d20 / d10 / d6 / d4）产生；
  当骰子掷出极端值（100、1 等）时会触发隐藏的特殊剧情。
* 存档 save.json、人生日志 life_log.txt 与源码一起放在本文件所在目录。

操作方式
--------
1. 运行程序 -> 弹出开局面板 -> 输入姓名 -> 选择城市 -> 点「开始人生」。
2. 主面板显示当前日期与四项属性，点「推进一天 ▸」开始这一天的生活。
3. 事件弹窗：显示事件描述 + 骰子点数 + 属性变化，点「确定」继续。
4. 选择弹窗：关键事件给出 2~3 个选项（例如「花钱治病 / 硬扛休息」），
   点击按钮即结算对应效果；金钱不足无法支付时才可用的选项会被禁用并给出提示。
5. 每日操作菜单：查看当前状态 / 休息恢复 / 工作赚钱 / 娱乐消费 /
   保存进度 / 读取进度 / 查看人生日志 / 退出游戏。
6. 死亡后会弹出人生总结面板，可选择「重新开始」或「退出游戏」。

运行要求
--------
* 仅使用 Python 标准库（tkinter / random / json / os / sys / datetime / math）。
* 无需安装任何第三方库。
* 建议 Python 3.8 以上；在 VS Code 中直接按 F5 或点右上角 ▶ 运行。

作者说明：本文件为单文件版本，便于在 VS Code 里直接运行；内部按模块划分：
    常量 / 骰子 / 数值工具 / 城市气候 / 疾病 / 事件库 / 人物 / 存档 / 日志 /
    结算引擎 / 模拟器 / Tkinter 界面 / 自检 / 入口。
================================================================================
"""

import json
import math
import os
import random
import re
import sys
import traceback
from datetime import datetime

# ------------------------------------------------------------------------------
# 0. 依赖检查（tkinter 为标准库，但在极少数精简版 Python 中会被裁剪）
# ------------------------------------------------------------------------------
try:
    import tkinter as tk
    from tkinter import font as tkfont
except Exception as _tk_err:  # pragma: no cover - 仅在缺库环境下触发
    tk = None
    tkfont = None
    _TK_IMPORT_ERROR = _tk_err
else:
    _TK_IMPORT_ERROR = None


# ==============================================================================
# 1. 全局常量配置
# ==============================================================================

APP_NAME = "弹窗式文字人生模拟器"
APP_VERSION = "1.0.0"

#: 游戏数据目录：源码、存档、日志统一存放在这里；程序启动时自动检测并创建
DEFAULT_BASE_DIR = r"D:\desktop\LifeSimulator"
#: 允许通过环境变量覆盖数据目录（便于测试或多存档管理）
ENV_BASE_DIR_KEY = "LIFESIM_HOME"
#: 兜底目录名（当目标盘符不可写时使用的次级目录）
FALLBACK_DIR_NAME = "LifeSimulator"

SAVE_FILE_NAME = "save.json"
LOG_FILE_NAME = "life_log.txt"
SOURCE_FILE_NAME = "LifeSimulator.py"

# 天数 / 时间换算
DAYS_PER_MONTH = 30          # 30 天 = 1 个月
MONTHS_PER_YEAR = 12         # 12 个月 = 1 年
DAYS_PER_YEAR = DAYS_PER_MONTH * MONTHS_PER_YEAR   # 360 天 = 1 年

# 属性边界
HEALTH_MAX = 100
HEALTH_MIN = 0
HAPPY_MAX = 100
HAPPY_MIN = 0
TEMP_NORMAL_LOW = 36.0
TEMP_NORMAL_HIGH = 37.0
TEMP_HARD_LOW = 30.0         # 体温硬下限（再低也不会低于此值，但会持续掉血）
TEMP_HARD_HIGH = 44.0        # 体温硬上限

# 初始值
INIT_HEALTH = 100
INIT_HAPPY = 50
INIT_MONEY = 1000.0
INIT_TEMP = 36.5
INIT_AGE = 0

# 每月固定经济
BASE_WAGE = 1500.0           # 工资基数（随职级 / 年龄变化）
BASE_EXPENSE = 1100.0        # 固定生活支出基数（随城市消费水平变化）

# 死亡 / 结局阈值
LOW_HAPPY_THRESHOLD = 20     # 幸福低于该值时产生 debuff
AGE_MAX_LIMIT = 130          # 年龄硬上限，超过后自然衰老必定致命

# 自然寿命模型（通过多种子实验调试：让角色的平均水平寿命稳定在 80 岁左右）
NATURAL_DEATH_START = 55     # 从这个年龄开始每年掷"生死骰"
NATURAL_DEATH_FLOOR_AGE = 45.0   # 死亡率曲线的起始年龄
NATURAL_DEATH_BASE_RATE = 0.0032  # 起始年龄（45 岁）的年度自然死亡概率
NATURAL_DEATH_GROWTH = 1.0580     # 死亡率年增长系数（多种子标定：平均寿命≈80 岁）
NATURAL_DEATH_ULTRA_AGE = 85.0  # 超过该年龄后死亡率加速上升
NATURAL_DEATH_ULTRA_GROWTH = 1.17  # 高龄加速系数
#: 健康状态对自然死亡率的修正（健康越差，死亡率越高）
NATURAL_DEATH_HEALTH_MIN = 0.7      # 满健康时的倍率下限
NATURAL_DEATH_HEALTH_MAX = 4.5      # 濒危健康时的倍率上限

# 数值保留位数
MONEY_ROUND = 2
TEMP_ROUND = 2

# 骰子面数表
DICE_FACES = (4, 6, 10, 20, 100)

# ------------------------------------------------------------------------------
# 体质系统（开局随机生成的固定参数，决定患病判定的容易程度）
#   0~100 分，50 为平均水平；采用正态分布（均值 50、标准差 13），
#   因此"极强/极弱体质"的出现概率都很低（±2σ 之外各约 2.3%）。
# ------------------------------------------------------------------------------
CONSTITUTION_MEAN = 50.0
CONSTITUTION_SD = 13.0
CONSTITUTION_MIN = 1.0
CONSTITUTION_MAX = 99.0
#: 体质 -> 患病易感倍率：按年龄的患病率再乘这个系数（50 分 = 1.0 倍）
CONSTITUTION_SUSCEPTIBILITY_MIN = 0.32   # 体质极强
CONSTITUTION_SUSCEPTIBILITY_MAX = 2.70   # 体质极弱

#: 体质档位描述（用于界面展示与日志）
CONSTITUTION_TIERS = [
    (90, "铁打之躯", "几乎不生病，恢复力惊人"),
    (75, "强健", "很少生病，恢复较快"),
    (60, "不错", "比一般人结实一些"),
    (40, "普通", "和大多数人一样"),
    (25, "偏弱", "容易感冒，恢复偏慢"),
    (10, "孱弱", "小病不断，需要格外小心"),
    (0, "病秧子", "常年药不离身，风险极高"),
]

# ------------------------------------------------------------------------------
# 家庭系统（随机生成"家境"参数；成年前/大学毕业前由父母承担开销）
# ------------------------------------------------------------------------------
FAMILY_WEALTH_MEAN = 45.0
FAMILY_WEALTH_SD = 16.0
FAMILY_WEALTH_MIN = 1.0
FAMILY_WEALTH_MAX = 99.0
#: 家境档位： (下限分, 名称, 每月可提供的抚养/支持金额)
FAMILY_TIERS = [
    (88, "富裕", "家里生意做得不错，从小衣食无忧", 4200.0),
    (75, "小康偏上", "父母都有稳定工作，生活宽裕", 2800.0),
    (58, "小康", "普通双职工家庭，够用但不算阔绰", 1900.0),
    (42, "普通", "工薪家庭，精打细算过日子", 1300.0),
    (26, "拮据", "父母收入不高，日子过得紧", 800.0),
    (12, "困难", "家里负担重，常常要为钱发愁", 450.0),
    (0, "贫困", "连学费都要东拼西凑", 200.0),
]
#: 家庭破产：概率极低（万分位），破产后父母不再承担开销
FAMILY_BANKRUPTCY_PERMILLE = 3         # 每"年"约 3‰ 的破产机会
FAMILY_BANKRUPTCY_MIN_AGE = 1          # 最早可能发生的年龄
#: 家庭支持覆盖到什么时候（毕业前 / 成年后仍需自付的比例）
FAMILY_SUPPORT_STAGES = ("infant", "preschool", "kindergarten", "primary", "middle",
                         "high", "university", "postgrad")

# ------------------------------------------------------------------------------
# 行动点：在**游戏内的同一天**里，最多可以进行 8 次操作
#   * 每次操作（休息/工作/娱乐/学习/社交/锻炼）消耗行动点，但**不推进日期**
#   * 点「推进一天」或「跳过这一天」才进入第二天，且一天最多掷骰触发一次事件
# ------------------------------------------------------------------------------
ACTION_POINTS_PER_DAY = 8
#: 每次操作的行动点消耗（都设为 1 点，保证一天正好可以做 8 次操作）
ACTION_COST = {"rest": 1, "work": 1, "fun": 1, "study": 1, "social": 1,
               "exercise": 1, "intimacy": 1, "parenting": 1}
ACTION_LABELS = {
    "rest": "休息恢复", "work": "工作赚钱", "fun": "娱乐消费",
    "study": "学习充电", "social": "社交联络", "exercise": "锻炼身体",
    "intimacy": "夫妻亲密", "parenting": "陪伴孩子",
}
#: 同一天内重复做同一件事的收益衰减（第 2 次 85%，第 3 次 70%……最低 40%）
ACTION_REPEAT_DECAY = 0.85
ACTION_REPEAT_FLOOR = 0.40
#: 每天最多可以进行几次"夫妻亲密"（现实向限制）
INTIMACY_MAX_PER_DAY = 1

# ------------------------------------------------------------------------------
# 疾病对健康的影响倍率（全局总开关）
#   调低它 = 每种病对健康的伤害更小、人生更长（可自行微调）
#   初始健康值见上方「初始值」区块的 INIT_HEALTH（上限 100）
# ------------------------------------------------------------------------------
DISEASE_HEALTH_IMPACT = 0.72

# ------------------------------------------------------------------------------
# 家庭 / 生育系统
#   * 结婚后可以进行「夫妻亲密」：提升幸福，并有概率受孕（可采取避孕）
#   * 孕期 270 天（游戏内 9 个月），期间有孕期反应与分娩风险
#   * 孩子出生后有遗传体质、养育开销、成长事件
# ------------------------------------------------------------------------------
PREGNANCY_DAYS = 270                 # 孕期天数（30 天 × 9 个月）
CONCEPTION_MIN_AGE = 18              # 最低生育年龄
CONCEPTION_MAX_AGE_FEMALE = 45       # 女性生育上限年龄
CONCEPTION_MAX_AGE_MALE = 60         # 男性生育上限年龄
INTIMACY_MIN_AGE = 18                # 「夫妻亲密」的最低年龄
INTIMACY_HAPPY_BASE = 6              # 亲密带来的基础幸福提升
INTIMACY_HAPPY_MARRIED_BONUS = 3     # 已婚额外加成
#: 每晚一次的受孕概率（未避孕）：按女性年龄分段
CONCEPTION_RATE_BY_AGE = [
    (20, 0.20), (25, 0.22), (30, 0.19), (35, 0.14),
    (40, 0.08), (45, 0.04), (60, 0.01),
]
#: 避孕方式 -> 成功率
CONTRACEPTION_OPTIONS = [
    ("不避孕", 0.0, "顺其自然，受孕概率最高"),
    ("安全期", 0.55, "低成本但不可靠"),
    ("避孕套", 0.92, "常见且方便"),
    ("短效避孕药", 0.98, "成功率高，需长期服用"),
]
#: 分娩风险：按母亲年龄
BIRTH_RISK_BY_AGE = [
    (20, 0.010), (25, 0.014), (30, 0.022), (35, 0.038),
    (40, 0.075), (45, 0.150), (60, 0.300),
]
#: 孩子数量上限（现实向软上限，超过后受孕概率大幅下降）
MAX_CHILDREN = 5
#: 每个孩子每月的养育开销（游戏内货币）
CHILD_MONTHLY_COST = 260.0
#: 子女姓名池（出生时随机取名）
CHILD_NAME_POOL = [
    "小雨", "星辰", "安安", "乐乐", "子轩", "思远", "若溪", "嘉宁", "一诺", "清和",
    "念安", "知微", "沐辰", "初棠", "亦然", "文轩", "语彤", "景行", "月明", "南风",
]


def conception_rate(age):
    """按女性年龄返回"每次亲密未避孕时的受孕概率"。"""
    for limit, rate in CONCEPTION_RATE_BY_AGE:
        if age <= limit:
            return rate
    return CONCEPTION_RATE_BY_AGE[-1][1]


def birth_risk(age):
    """按母亲年龄返回分娩并发症概率。"""
    for limit, rate in BIRTH_RISK_BY_AGE:
        if age <= limit:
            return rate
    return BIRTH_RISK_BY_AGE[-1][1]

# ------------------------------------------------------------------------------
# 时间跳过（按月 / 按年跳过，只做合理的数值汇总，不生成逐日事件）
# ------------------------------------------------------------------------------
SKIP_MAX_YEARS = 30              # 一次最多跳过多少年
SKIP_MAX_MONTHS = 360            # 一次最多跳过多少月

# 各人生阶段的"平凡日常"基准事件概率（万分位，1/10000）
# 用 d10000 判定，大大压缩事件发生频率：不再是天天有事发生
EVENT_CHANCE_D10000 = {
    "infant": 300,        # 婴幼儿：家里照看，事件很少
    "preschool": 500,
    "kindergarten": 700,
    "primary": 800,
    "middle": 900,
    "high": 1100,
    "university": 1300,
    "postgrad": 1200,
    "work": 1600,         # 工作期事件最多
    "retired": 900,
    "unknown": 1000,
}
#: 各类事件在"事件日"里被抽中的概率上限（万分位），避免某类事件刷屏
EVENT_CATEGORY_COOLDOWN_DAYS = 6   # 同一大类事件的最短间隔（天）
#: 生病事件的最短间隔（天）：避免"一个月生好几次病"
MIN_ILLNESS_GAP_DAYS = 25


# ==============================================================================
# 2. 路径工具：自动检测并创建数据目录（支持"便携模式"）
# ==============================================================================

#: 便携模式标记文件：存在它 = 存档放在"程序所在目录"（解压即玩、存档同目录）
PORTABLE_MARKER = "portable.txt"
#: 便携模式下的存档子目录名
PORTABLE_SAVE_DIR = "save"


def _try_makedirs(path):
    """尝试创建目录，成功返回 True，失败返回 False（不抛异常）。"""
    try:
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
        return os.path.isdir(path)
    except Exception:
        return False


def _dir_writable(path):
    """检测目录是否可写（真实写入一个探针文件）。"""
    probe = os.path.join(path, ".write_probe.tmp")
    try:
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except Exception:
        try:
            if os.path.exists(probe):
                os.remove(probe)
        except Exception:
            pass
        return False


def program_dir():
    """程序（脚本或打包后的 exe）所在目录。"""
    try:
        if getattr(sys, "frozen", False):          # PyInstaller 等打包后的 exe
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def portable_dir():
    """便携模式的数据目录（程序目录下的 save/）。"""
    return os.path.join(program_dir(), PORTABLE_SAVE_DIR)


def _looks_like_extracted_package():
    """
    判断当前是否"从压缩包里解压出来直接运行"（便携包）。
    依据：程序目录里除了源码，还带着分发用的 README / 启动脚本等文件。
    """
    base = program_dir()
    for name in ("run_game.bat", "启动游戏.bat", "readme.txt", "使用说明.txt",
                 "便携说明.txt", PORTABLE_MARKER):
        if os.path.isfile(os.path.join(base, name)):
            return True
    return False


def is_portable_mode():
    """
    是否使用便携模式（存档放在程序同目录的 save/ 下）：
        1. 显式禁用：程序目录存在 "no_portable.txt"  -> 强制用默认数据目录
        2. 显式启用：程序目录存在 "portable.txt"     -> 便携
        3. 自动判断：程序目录里有"解压包标志文件"（README/启动脚本等），
           或者已经存在 save/ 目录                        -> 便携
    """
    base = program_dir()
    if os.path.isfile(os.path.join(base, "no_portable.txt")):
        return False
    if os.path.isfile(os.path.join(base, PORTABLE_MARKER)):
        return True
    if os.path.isdir(os.path.join(base, PORTABLE_SAVE_DIR)):
        return True
    return _looks_like_extracted_package()


def resolve_base_dir(force_portable=None):
    """
    解析游戏数据目录（存档、日志、模组的存放位置）。

    优先级：
        1. 环境变量 LIFESIM_HOME（调试 / 多开用）
        2. 便携模式（解压即玩）：程序目录下的 save/ —— 存档与游戏同文件夹
        3. 默认目录 D:\\desktop\\LifeSimulator（源码开发时的默认位置）
        4. 兜底：<用户主目录>\\LifeSimulator  ->  程序目录\\data

    force_portable: True/False 可强制开关便携模式（None = 自动判断）
    返回 (目录, 说明信息列表)。
    """
    notes = []
    env_dir = os.environ.get(ENV_BASE_DIR_KEY, "").strip()
    candidates = []
    if env_dir:
        candidates.append(env_dir)
        notes.append("检测到环境变量 %s，使用目录：%s" % (ENV_BASE_DIR_KEY, env_dir))

    portable = is_portable_mode() if force_portable is None else bool(force_portable)
    if portable:
        pdir = portable_dir()
        candidates.append(pdir)
        notes.append("便携模式：存档与日志保存在程序同目录（%s）" % PORTABLE_SAVE_DIR)

    candidates.append(DEFAULT_BASE_DIR)
    home = os.path.expanduser("~") or "."
    candidates.append(os.path.join(home, FALLBACK_DIR_NAME))
    candidates.append(os.path.join(program_dir(), "data"))

    for path in candidates:
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.isdir(parent) and not _try_makedirs(parent):
            notes.append("无法创建上级目录：%s（跳过）" % parent)
            continue
        if not _try_makedirs(path):
            notes.append("无法创建数据目录：%s（跳过）" % path)
            continue
        if not _dir_writable(path):
            notes.append("数据目录不可写：%s（跳过）" % path)
            continue
        if portable and os.path.abspath(path) == os.path.abspath(portable_dir()):
            notes.append("提示：解压即玩，存档就在游戏文件夹里，整个文件夹可以随意拷贝。")
        elif path != DEFAULT_BASE_DIR:
            notes.append("提示：目标目录不可用，已自动切换为 %s" % path)
        return path, notes

    # 全部失败：退回到当前工作目录（保证程序不崩溃）
    cwd = os.getcwd()
    notes.append("警告：所有候选目录均不可写，临时使用当前工作目录：%s" % cwd)
    return cwd, notes


def safe_join(base_dir, filename):
    """安全拼接路径。"""
    try:
        return os.path.join(base_dir, filename)
    except Exception:
        return filename


# ==============================================================================
# 3. 骰子系统（跑团随机机制）
# ==============================================================================

class DiceResult:
    """一次骰子投掷的结果，便于界面展示与日志记录。"""

    __slots__ = ("faces", "value", "count", "flat", "tag", "hidden")

    def __init__(self, faces, value, count=1, flat=0, tag=""):
        self.faces = faces      # 骰子面数：4 / 6 / 10 / 20 / 100
        self.value = value      # 总点数（含修正）
        self.count = count      # 骰子个数
        self.flat = flat        # 固定修正值
        self.tag = tag          # 用途标签，如「事件大类判定」
        self.hidden = None      # 极端点数触发的隐藏剧情说明（如有）

    # ---- 展示 ----
    def __str__(self):
        base = "%dd%d" % (self.count, self.faces)
        if self.flat > 0:
            base += "+%d" % self.flat
        elif self.flat < 0:
            base += "%d" % self.flat
        return "[%s = %d]" % (base, self.value)

    def to_dict(self):
        return {
            "faces": self.faces,
            "value": self.value,
            "count": self.count,
            "flat": self.flat,
            "tag": self.tag,
            "hidden": self.hidden,
        }


class DiceSystem:
    """骰子引擎：统一处理随机数、极端点数与隐藏剧情。"""

    #: 极端点数 -> 隐藏剧情（d100）
    HIDDEN_D100 = {
        100: "【隐藏·天命所归】骰子掷出满值 100，命运之神向你微笑。",
        99: "【隐藏·一线生机】骰子掷出 99，绝境中总有转机。",
        2: "【隐藏·劫数初现】骰子掷出 2，冥冥中有阴影靠近。",
        1: "【隐藏·天崩开局】骰子掷出大失败 1，最坏的情况发生了。",
    }
    #: 极端点数 -> 隐藏剧情（d20）
    HIDDEN_D20 = {
        20: "【隐藏·大成功】d20 掷出 20，事情好得出乎意料。",
        1: "【隐藏·大失败】d20 掷出 1，事情糟得不能再糟。",
    }
    #: 极端点数 -> 隐藏剧情（d10）
    HIDDEN_D10 = {
        10: "【隐藏·圆满】d10 掷出 10，这一件事做到了极致。",
        1: "【隐藏·脱力】d10 掷出 1，效果几乎为零。",
    }
    #: 极端点数 -> 隐藏剧情（d6）
    HIDDEN_D6 = {
        6: "【隐藏·顺遂】d6 掷出 6，一切顺利。",
        1: "【隐藏·波折】d6 掷出 1，出了岔子。",
    }
    #: 极端点数 -> 隐藏剧情（d4）
    HIDDEN_D4 = {
        4: "【隐藏·极致】d4 掷出 4，效果拉满。",
        1: "【隐藏·微弱】d4 掷出 1，聊胜于无。",
    }

    HIDDEN_TABLE = {100: HIDDEN_D100, 20: HIDDEN_D20, 10: HIDDEN_D10,
                    6: HIDDEN_D6, 4: HIDDEN_D4}

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.rolls_today = []      # 今日骰子记录（用于界面展示）

    # ------------------------------------------------------------------
    # 基础投掷
    # ------------------------------------------------------------------
    def roll(self, faces, count=1, flat=0, tag=""):
        """投掷 count 个 faces 面骰，返回 DiceResult。"""
        faces = int(faces)
        count = max(1, int(count))
        try:
            total = sum(self.rng.randint(1, faces) for _ in range(count)) + int(flat)
        except Exception:
            total = count + int(flat)
        if count == 1:
            total = min(max(total, 1), faces) if faces >= 1 else total
        res = DiceResult(faces, total, count, int(flat), tag)
        table = self.HIDDEN_TABLE.get(faces)
        if count == 1 and table and total in table:
            res.hidden = table[total]
        return res

    def d4(self, tag="", count=1, flat=0):
        return self.roll(4, count, flat, tag)

    def d6(self, tag="", count=1, flat=0):
        return self.roll(6, count, flat, tag)

    def d10(self, tag="", count=1, flat=0):
        return self.roll(10, count, flat, tag)

    def d20(self, tag="", count=1, flat=0):
        return self.roll(20, count, flat, tag)

    def d100(self, tag="", count=1, flat=0):
        return self.roll(100, count, flat, tag)

    # ------------------------------------------------------------------
    # 组合判定
    # ------------------------------------------------------------------
    def check(self, target, faces=100, tag="", modifier=0):
        """
        对抗判定：掷 faces 面骰 + modifier >= target 视为成功。
        返回 (是否成功, DiceResult)
        """
        res = self.roll(faces, 1, modifier, tag)
        # 极端点数强制结果：100 = 必然成功，1 = 必然失败
        if res.faces == 100 and res.count == 1 and res.flat == 0:
            if res.value == 100:
                return True, res
            if res.value == 1:
                return False, res
        if res.faces == 20 and res.value == 20:
            return True, res
        if res.faces == 20 and res.value == 1:
            return False, res
        return res.value >= target, res

    def pick(self, seq, tag="", faces=None):
        """从序列里用骰子随机取一个元素，返回 (元素, DiceResult)。"""
        seq = list(seq)
        if not seq:
            return None, self.d100(tag or "空池判定")
        faces = faces or 100
        res = self.roll(faces, 1, 0, tag)
        idx = (res.value - 1) % len(seq) if faces >= 2 else 0
        return seq[idx], res

    def roll_notation(self, notation, tag=""):
        """
        解析形如 '2d6+3' / 'd4' 的骰子表达式并投掷，返回 DiceResult。
        解析失败时退化为 d4 投掷，保证不崩溃。
        """
        try:
            text = str(notation).strip().lower().replace(" ", "")
            flat = 0
            if "+" in text:
                text, flat_s = text.split("+", 1)
                flat = int(flat_s)
            elif "-" in text:
                text, flat_s = text.split("-", 1)
                flat = -int(flat_s)
            if "d" in text:
                cnt_s, faces_s = text.split("d", 1)
                count = int(cnt_s) if cnt_s else 1
                faces = int(faces_s)
            else:
                count, faces = 1, int(text)
            if faces not in DICE_FACES and faces < 2:
                faces = 4
            return self.roll(faces, count, flat, tag)
        except Exception:
            return self.d4(tag or "表达式兜底")

    # ------------------------------------------------------------------
    # 事件数值：多骰组合，避免极端暴死
    # ------------------------------------------------------------------
    def graded_value(self, base, faces=6, count=1, min_value=0, tag=""):
        """
        生成一个较为"均衡"的数值：base + 多骰平均（四舍五入），
        避免单骰带来过大的方差，返回 (数值, DiceResult)。
        """
        res = self.roll(faces, count, 0, tag)
        avg = res.value / float(count)
        value = base + int(round(avg))
        return max(min_value, value), res

    # ------------------------------------------------------------------
    # 今日骰子记录
    # ------------------------------------------------------------------
    def reset_today(self):
        self.rolls_today = []

    def remember(self, res, label=""):
        if res is None:
            return
        self.rolls_today.append((label or res.tag or "骰子", res))

    def today_lines(self):
        lines = []
        for label, res in self.rolls_today:
            lines.append("    · %s %s" % (label, res))
        return lines


# 模块级默认骰子实例（供不关心种子的场景使用）
_dice = DiceSystem()


def roll_dice(faces, tag=""):
    """便捷函数：使用模块级骰子投掷一次。"""
    return _dice.roll(faces, 1, 0, tag)


# ==============================================================================
# 4. 数值工具：边界约束、飘字格式化
# ==============================================================================

def clamp(value, low, high):
    """把数值限制在 [low, high] 区间内。"""
    try:
        value = float(value)
    except Exception:
        return low
    if value < low:
        return low
    if value > high:
        return high
    return value


def clamp_health(v):
    return clamp(round(v, 2), HEALTH_MIN, HEALTH_MAX)


def clamp_happy(v):
    return clamp(round(v, 2), HAPPY_MIN, HAPPY_MAX)


def clamp_temp(v):
    return clamp(round(v, TEMP_ROUND), TEMP_HARD_LOW, TEMP_HARD_HIGH)


def round_money(v):
    return round(float(v), MONEY_ROUND)


def fmt_money(v):
    """金额格式化：1234.5 -> '1234.50'（负值带负号）。"""
    try:
        return "%.2f" % float(v)
    except Exception:
        return "0.00"


def fmt_signed(v, digits=2):
    """带符号格式化：+3 / -1.5。"""
    try:
        num = round(float(v), digits)
    except Exception:
        return "±0"
    if digits <= 0:
        num = int(round(num))
        text = "%+d" % num
    else:
        text = "%+.2f" % num
    return text.replace("+0.00", "±0.00").replace("+0", "±0")


def fmt_diff(value, digits=2):
    """生成 (文本, 颜色) 形式的差值描述。"""
    threshold = (10 ** (-digits)) / 2.0 if digits > 0 else 0.5
    if abs(value) < threshold:
        return "±0", "#8a8f98"
    if value > 0:
        return fmt_signed(value, digits), "#4ad07a"
    return fmt_signed(value, digits), "#ff6b6b"


def clean_number(v, digits=MONEY_ROUND):
    """把浮点数整理为"干净"的值，用于存盘与比较。"""
    try:
        num = round(float(v), digits)
    except Exception:
        return 0.0
    if abs(num) < 1e-9:
        return 0.0
    return num


def pct_text(value):
    """0.85 -> '85%'"""
    try:
        return "%d%%" % int(round(float(value) * 100))
    except Exception:
        return "0%"


# ==============================================================================
# 4.1 体质系统工具
# ==============================================================================

def roll_constitution(rng):
    """
    开局随机生成体质：正态分布（均值 50、标准差 13），截断到 1~99。
    正态分布保证了"极强体质（90+）"与"极弱体质（10-）"的出现概率都很低：
        >= 90 分：约 0.1%      >= 80 分：约 1.0%
        <= 10 分：约 0.1%      <= 20 分：约 1.0%
    返回 (体质分数, 骰子说明文本)
    """
    try:
        value = rng.gauss(CONSTITUTION_MEAN, CONSTITUTION_SD)
    except Exception:
        value = CONSTITUTION_MEAN
    if value < CONSTITUTION_MIN:
        value = CONSTITUTION_MIN
    if value > CONSTITUTION_MAX:
        value = CONSTITUTION_MAX
    value = round(value, 1)
    note = "d100 体质判定 = %d（均值 50，正态分布）" % int(round(value))
    return value, note


def constitution_tier(value):
    """返回 (档位名称, 说明)。"""
    for low, name, desc in CONSTITUTION_TIERS:
        if value >= low:
            return name, desc
    return CONSTITUTION_TIERS[-1][1], CONSTITUTION_TIERS[-1][2]


def constitution_susceptibility(value):
    """
    体质 -> 患病易感倍率（分段指数曲线，实现在下方 _susceptibility 中）：
        50 分（普通）  = 1.00 倍
        90 分（强健）  ≈ 0.35 倍
        99 分（铁打）  ≈ 0.20 倍
        10 分（孱弱）  ≈ 1.85 倍
        1 分（病秧子） ≈ 2.70 倍
    采用指数关系，使两端差异明显但不会出现 0 倍或无穷大。
    """
    try:
        v = float(value)
    except Exception:
        v = CONSTITUTION_MEAN
    v = max(CONSTITUTION_MIN, min(CONSTITUTION_MAX, v))
    # 以 50 分为 1.0 的基准指数曲线：exp(-(v-50)*0.011) 在 50 分处为 1
    # 低分区（<50）再做一次轻微放大，让"病秧子"更明显
    factor = math.exp(-(v - CONSTITUTION_MEAN) * 0.0265) if v >= CONSTITUTION_MEAN \
        else math.exp(-(v - CONSTITUTION_MEAN) * 0.0110)
    if factor < CONSTITUTION_SUSCEPTIBILITY_MIN:
        factor = CONSTITUTION_SUSCEPTIBILITY_MIN
    if factor > CONSTITUTION_SUSCEPTIBILITY_MAX:
        factor = CONSTITUTION_SUSCEPTIBILITY_MAX
    return round(factor, 3)


def duration_factor(value):
    """体质 -> 病程长短系数（体质越差，病得越久）。"""
    sus = constitution_susceptibility(value)
    return round(0.6 + 0.4 * sus, 2)


# ==============================================================================
# 4.2 家庭系统工具
# ==============================================================================

def roll_family_wealth(rng):
    """开局随机生成家境（正态分布，均值 45、标准差 16），返回 (分数, 说明)。"""
    try:
        value = rng.gauss(FAMILY_WEALTH_MEAN, FAMILY_WEALTH_SD)
    except Exception:
        value = FAMILY_WEALTH_MEAN
    value = round(max(FAMILY_WEALTH_MIN, min(FAMILY_WEALTH_MAX, value)), 1)
    note = "d100 家境判定 = %d（均值 45，正态分布）" % int(round(value))
    return value, note


def family_tier(value):
    """返回 (档位名称, 说明, 每月支持金额)。"""
    for low, name, desc, support in FAMILY_TIERS:
        if value >= low:
            return name, desc, support
    last = FAMILY_TIERS[-1]
    return last[1], last[2], last[3]


def family_support_amount(player):
    """
    计算家庭每月能给的生活支持金额。
    * 家庭破产 / 已被赶出家门 -> 0
    * 成年前（各学业阶段）-> 按家境档位发放，随年龄略增
    * 工作之后 -> 只在你"仍在读书"时给（读研）
    """
    if getattr(player, "family_bankrupt", False):
        return 0.0
    if getattr(player, "left_home", False):
        return 0.0
    stage = getattr(player, "stage", "")
    if stage not in FAMILY_SUPPORT_STAGES:
        return 0.0
    _name, _desc, base = family_tier(player.family_wealth)
    age = max(0, int(getattr(player, "age", 0)))
    if age <= 3:
        factor = 0.55
    elif age <= 6:
        factor = 0.70
    elif age <= 12:
        factor = 0.85
    elif age <= 18:
        factor = 1.0
    else:
        factor = 1.15          # 大学/读研阶段开销更大
    # 家境随"家庭收入波动"轻微浮动（±15%）
    wave = 1.0 + ((age * 7 + int(player.family_wealth)) % 31 - 15) / 100.0
    return round(base * factor * wave, 2)


# ==============================================================================
# 4.3 人生阶段流程（学龄前 -> 幼儿园 -> 义务教育 -> 中考 -> 高中 -> 高考
#                    -> 大学 -> 读研 -> 工作 -> 退休）
# ==============================================================================
#: 每个阶段：名称、起始年龄、结束年龄（到达时判定下一阶段）、事件概率键
LIFE_STAGES = [
    {"id": "infant", "name": "婴幼儿", "start": 0, "end": 2,
     "next": "preschool", "chance_key": "infant",
     "desc": "还不会走路说话，全凭父母照顾。"},
    {"id": "preschool", "name": "学龄前", "start": 3, "end": 4,
     "next": "kindergarten", "chance_key": "preschool",
     "desc": "会跑会闹，开始对世界充满好奇。"},
    {"id": "kindergarten", "name": "幼儿园", "start": 5, "end": 6,
     "next": "primary", "chance_key": "kindergarten",
     "desc": "上幼儿园，第一次离开家人独自待一整天。"},
    {"id": "primary", "name": "小学", "start": 7, "end": 12,
     "next": "middle", "chance_key": "primary",
     "desc": "九年义务教育第一阶段：小学。"},
    {"id": "middle", "name": "初中", "start": 13, "end": 15,
     "next": "zhongkao", "chance_key": "middle",
     "desc": "九年义务教育第二阶段：初中。"},
    {"id": "zhongkao", "name": "中考", "start": 16, "end": 16,
     "next": "high", "chance_key": "middle",
     "desc": "人生第一次分流：中考。", "exam": "zhongkao"},
    {"id": "high", "name": "高中", "start": 17, "end": 19,
     "next": "gaokao", "chance_key": "high",
     "desc": "三年苦读，目标只有一个：高考。"},
    {"id": "gaokao", "name": "高考", "start": 20, "end": 20,
     "next": "university", "chance_key": "high",
     "desc": "决定未来走向的一场考试。", "exam": "gaokao"},
    {"id": "university", "name": "大学", "start": 21, "end": 24,
     "next": "work", "chance_key": "university",
     "desc": "离开家乡，开始独立生活的四年。"},
    {"id": "postgrad", "name": "读研", "start": 25, "end": 27,
     "next": "work", "chance_key": "postgrad",
     "desc": "继续深造，为将来争取更高的起点。"},
    {"id": "work", "name": "工作", "start": 22, "end": 59,
     "next": "retired", "chance_key": "work",
     "desc": "步入社会，靠自己的双手吃饭。"},
    {"id": "retired", "name": "退休", "start": 60, "end": 200,
     "next": None, "chance_key": "retired",
     "desc": "退出职场，开始晚年生活。"},
    # 特殊分支（由考试 / 家庭破产等事件进入）
    {"id": "dropout", "name": "辍学打工", "start": 15, "end": 21,
     "next": "work", "chance_key": "work", "branch": True,
     "desc": "提前离开校园，进入社会谋生。"},
    {"id": "jobless", "name": "待业", "start": 18, "end": 59,
     "next": "work", "chance_key": "work", "branch": True,
     "desc": "暂时没有工作，靠零工和积蓄生活。"},
]

STAGE_BY_ID = {s["id"]: s for s in LIFE_STAGES}


def stage_name(stage_id):
    stage = STAGE_BY_ID.get(stage_id)
    return stage["name"] if stage else "未知阶段"


def stage_of_age(age):
    """按年龄返回"标准流程"下的阶段 id（用于时间跳跃与校验）。"""
    a = int(age)
    if a <= 2:
        return "infant"
    if a <= 4:
        return "preschool"
    if a <= 6:
        return "kindergarten"
    if a <= 12:
        return "primary"
    if a <= 15:
        return "middle"
    if a == 16:
        return "zhongkao"
    if a <= 19:
        return "high"
    if a == 20:
        return "gaokao"
    if a <= 24:
        return "university"
    if a <= 59:
        return "work"
    return "retired"


def event_chance_of(player):
    """返回该角色当天发生"值得记录的事件"的概率（0~1，基于万分位配置）。"""
    stage = getattr(player, "stage", None) or stage_of_age(getattr(player, "age", 0))
    meta = STAGE_BY_ID.get(stage) or {}
    key = meta.get("chance_key", "unknown")
    per_10000 = EVENT_CHANCE_D10000.get(key, EVENT_CHANCE_D10000["unknown"])
    # 健康差、情绪差的人更容易遇到波折
    try:
        health = float(player.health)
        happy = float(player.happy)
    except Exception:
        health, happy = 100.0, 50.0
    mod = 1.0
    if health < 35:
        mod *= 1.4
    elif health < 60:
        mod *= 1.15
    if happy < LOW_HAPPY_THRESHOLD:
        mod *= 1.2
    if getattr(player, "diseases", None):
        mod *= 1.25
    return max(0.0, min(0.5, per_10000 / 10000.0 * mod))


# ==============================================================================
# 4.4 插件 / 模组系统（名著模组等）
# ==============================================================================
#: 全局模组注册表。模组可以覆盖：城市气候、事件库、人生阶段、初始属性等。
MOD_REGISTRY = {
    "loaded": {},          # 模组id -> 模组信息
    "event_hooks": [],     # 额外的每日事件生成器
    "stage_hooks": {},     # 阶段覆盖
    "env_hooks": {},       # 环境（城市/场景）覆盖
    "flavor": {},          # 模组自带的文案/世界设定
}


class LifeMod:
    """
    人生模组基类（插件接口）。
    继承它并实现需要的钩子，然后用 register_mod() 注册即可。
    典型用途：把某本名著的世界观做成模组——新增环境（场景）、事件、
    以及该世界观特有的人生流程。

    可用钩子：
        mod_id / mod_name / mod_desc / author
        init(game_api)                     -> 注入宿主 API（生成人物、骰子、日志等）
        register_events()                  -> 返回 [事件字典]（会被加入事件库）
        register_stages()                  -> 返回 [阶段字典]（会被加入阶段流程）
        register_environments()            -> 返回 {环境id: 环境数据}
        daily_event_hook(player, dice)     -> 返回事件卡或 None（优先于普通抽签）
        on_day_end(player, report)         -> 每天结束时的额外处理
        opening_text(player)               -> 开局介绍文本
    """

    mod_id = "base"
    mod_name = "基础模组"
    mod_desc = "模组基类，仅用于示例。"
    author = ""

    def init(self, game_api):
        """注入宿主 API（不实现也没关系）。"""
        self.api = game_api

    def register_events(self):
        return []

    def register_stages(self):
        return []

    def register_environments(self):
        return {}

    def daily_event_hook(self, player, dice):
        return None

    def on_day_end(self, player, report):
        return None

    def opening_text(self, player):
        return ""


def register_mod(mod, events_map=None, event_order=None):
    """
    注册一个模组。
    返回 (是否成功, 说明文本)。
    events_map  : 事件字典（通常是 EVENTS），模组事件会被加进去
    event_order : 可抽取事件 id 列表（通常是 EVENT_ORDER）；
                  传入它，模组新增的事件才会真正参与每日抽签
    """
    if mod is None or not getattr(mod, "mod_id", None):
        return False, "模组对象无效（缺少 mod_id）。"
    mod_id = mod.mod_id
    if mod_id in MOD_REGISTRY["loaded"]:
        return False, "模组 %s 已经加载过了。" % mod_id
    info = {
        "id": mod_id,
        "name": getattr(mod, "mod_name", mod_id),
        "desc": getattr(mod, "mod_desc", ""),
        "author": getattr(mod, "author", ""),
        "object": mod,
        "events": [],
        "stages": [],
        "environments": {},
    }
    try:
        # 1) 事件
        for ev in (mod.register_events() or []):
            if not isinstance(ev, dict) or "id" not in ev:
                continue
            info["events"].append(ev)
            if events_map is not None:
                is_host_events = event_order is not None
                if ev["id"] not in events_map:
                    events_map[ev["id"]] = ev
                    if is_host_events and ev["id"] not in event_order:
                        event_order.append(ev["id"])
        # 2) 阶段
        for st in (mod.register_stages() or []):
            if not isinstance(st, dict) or "id" not in st:
                continue
            info["stages"].append(st)
            if st["id"] not in STAGE_BY_ID:
                LIFE_STAGES.append(st)
                STAGE_BY_ID[st["id"]] = st
        # 3) 环境/场景
        envs = mod.register_environments() or {}
        info["environments"] = envs
        for env_id, env_data in envs.items():
            MOD_REGISTRY["env_hooks"][env_id] = env_data
            # 环境同时加入可选开局地点
            try:
                g = register_mod.__globals__
                cities = g.get("CITIES")
                order = g.get("CITY_ORDER")
                if isinstance(cities, dict) and isinstance(order, list) and env_id not in cities:
                    data = dict(env_data)
                    data.setdefault("name", env_id)
                    data.setdefault("tag", "模组")
                    data.setdefault("desc", "")
                    data.setdefault("seasons", {1: 15.0, 2: 25.0, 3: 18.0, 4: 5.0})
                    data.setdefault("variance", 4.0)
                    data.setdefault("temp_swing", 1.0)
                    data.setdefault("cost_factor", 1.0)
                    data.setdefault("env_weights", {1: {}, 2: {}, 3: {}, 4: {}})
                    data.setdefault("disease_weights", {"cold": 10, "gastro": 10,
                                                        "pneumonia": 8, "chronic": 8,
                                                        "frostbite": 5, "heatstroke": 5})
                    cities[env_id] = data
                    order.append(env_id)
            except Exception:
                pass
    except Exception as exc:
        return False, "模组 %s 加载失败：%s" % (mod_id, exc)
    MOD_REGISTRY["loaded"][mod_id] = info
    return True, "模组「%s」加载成功（新增事件 %d 个，阶段 %d 个，环境 %d 个）" % (
        info["name"], len(info["events"]), len(info["stages"]), len(info["environments"]))


def loaded_mods_text():
    """返回已加载模组的说明文本。"""
    if not MOD_REGISTRY["loaded"]:
        return "（当前没有加载任何模组，使用基础人生流程）"
    lines = []
    for mod_id, info in MOD_REGISTRY["loaded"].items():
        lines.append("  · %s（%s）%s" % (info["name"], mod_id, info["desc"]))
        if info["author"]:
            lines.append("      作者：%s" % info["author"])
    return "\n".join(lines)


def discover_mods():
    """
    自动发现并加载模组：
      * 从环境变量 LIFESIM_MODS 指定的目录（多个用 os.pathsep 分隔）
      * 以及数据目录下的 mods 子目录
      * 每个 .py 文件里可以定义任意多个 LifeMod 子类，会被自动注册
    为了让模组文件可以直接写 `class X(LifeMod)`，加载前会把当前程序注册到
    sys.modules（名字为 "LifeSimulator" 与 "__main__"），模组里也可以显式
    `from LifeSimulator import LifeMod`。
    返回 (成功加载数量, 说明文本列表)
    """
    import importlib.util as _ilu
    # ---- 把宿主程序注册成可导入模块，方便模组引用 ----
    host_module = sys.modules.get(__name__) or sys.modules.get("__main__")
    if host_module is not None:
        for alias in ("LifeSimulator", "lifesimulator"):
            sys.modules.setdefault(alias, host_module)
        # 让 __main__ 也有 LifeMod 等符号（直接运行时）
        sys.modules.setdefault("__main__", host_module)

    # ---- 解析宿主里的关键符号 ----
    # 注意：本函数在文件里出现的位置早于 LifeMod 类的定义，
    #       因此必须"延迟解析"：用函数自身的 __globals__（就是本模块的命名空间）
    #       在调用时查找，而不是在函数体里直接引用全局名。
    def _resolve(name):
        g = _resolve.__globals__
        if name in g:
            return g[name]
        for candidate in (sys.modules.get("LifeSimulator"),
                          sys.modules.get("__main__"),
                          sys.modules.get(__name__)):
            if candidate is not None and hasattr(candidate, name):
                return getattr(candidate, name)
        return None

    mod_base = _resolve("LifeMod")
    reg_func = _resolve("register_mod")
    if mod_base is None or reg_func is None:
        return 0, ["模组系统尚未初始化完成（找不到 LifeMod / register_mod）"]
    host_events = _resolve("EVENTS")
    host_order = _resolve("EVENT_ORDER")

    host_module = _resolve.__globals__.get("__name__")
    host_module = sys.modules.get("LifeSimulator") or sys.modules.get("__main__")
    if host_module is None or not hasattr(host_module, "LifeMod"):
        # 直接拿本模块的命名空间作为宿主
        host_module = type(sys)("LifeSimulator_host")
        host_module.__dict__.update(_resolve.__globals__)
    for alias in ("LifeSimulator", "lifesimulator"):
        sys.modules.setdefault(alias, host_module)

    inject_names = ("LifeMod", "register_mod", "register_event", "EVENTS",
                    "EVENT_ORDER", "CITIES", "CITY_ORDER", "DISEASES",
                    "LIFE_STAGES", "STAGE_BY_ID", "MOD_REGISTRY",
                    "CATEGORY_BANDS", "TRUE_TONE_COLORS",
                    "ACTION_POINTS_PER_DAY", "ACTION_COST", "ACTION_LABELS")
    host_vars = dict(_resolve.__globals__)

    roots = []
    env = os.environ.get("LIFESIM_MODS", "").strip()
    if env:
        for part in env.split(os.pathsep):
            if part.strip():
                roots.append(part.strip())
    base = globals().get("__LIFESIM_BASE_DIR__") or ""
    if base:
        roots.append(os.path.join(base, "mods"))
    notes = []
    loaded = 0
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for fname in sorted(os.listdir(root)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(root, fname)
            try:
                spec = _ilu.spec_from_file_location("lifesim_mod_%s" % fname[:-3], path)
                module = _ilu.module_from_spec(spec)
                # ---- 注入宿主命名空间，让模组文件可以直接写 class X(LifeMod) ----
                module.__dict__["LifeMod"] = mod_base
                module.__dict__["register_mod"] = reg_func
                for key in inject_names:
                    if key in host_vars:
                        module.__dict__[key] = host_vars[key]
                module.__dict__.setdefault("__host__", host_module)
                spec.loader.exec_module(module)
            except Exception as exc:
                notes.append("模组文件 %s 加载失败：%s" % (fname, exc))
                continue
            # 找出模块里所有的 LifeMod 子类
            found = 0
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (isinstance(obj, type) and issubclass(obj, mod_base)
                        and obj is not mod_base and getattr(obj, "mod_id", "base") != "base"):
                    try:
                        ok, msg = reg_func(obj(), host_events, host_order)
                    except Exception as exc:
                        notes.append("模组类 %s 实例化失败：%s" % (attr_name, exc))
                        continue
                    notes.append(msg)
                    if ok:
                        loaded += 1
                        found += 1
            if found == 0:
                notes.append("模组文件 %s 中未找到 LifeMod 子类" % fname)
    return loaded, notes


class LifeModCodec:
    """
    模组辅助工具：把模组数据（事件 / 阶段 / 环境）导出为可读的 Python 源码骨架，
    方便作者照着填内容。
    """

    TEMPLATE = '''# -*- coding: utf-8 -*-
r"""
{mod_name} —— 人生模拟器模组（插件）
把本文件放到 <数据目录>\\mods\\ 下即可被自动加载，
或用环境变量 LIFESIM_MODS 指定模组目录。

它可以让游戏运行在完全不同的世界里（例如某本名著的人生）：
    * register_environments(): 新增"环境/场景"（在 CITIES 里追加可选开局地点）
    * register_events():       新增事件（进入事件库参与每日抽签）
    * register_stages():       新增人生阶段（进入阶段流程）
    * daily_event_hook():      接管每日事件生成（返回自定义事件卡）

提示：本文件运行时，主程序已经把 LifeMod / register_mod / EVENTS 等符号
注入到模组的命名空间里，因此可以直接使用下面的名字；
也可以写 `from LifeSimulator import LifeMod`（主程序已注册该模块名）。
"""


class {class_name}(LifeMod):
    mod_id = "{mod_id}"
    mod_name = "{mod_name}"
    mod_desc = "{mod_desc}"
    author = "{author}"

    # ------------------------------------------------------------------
    def register_environments(self):
        """新增环境（场景）。返回 {{环境id: 环境数据}}，会被加入可选城市列表。"""
        return {{
            "{mod_id}_world": {{
                "name": "示例场景",
                "tag": "虚构",
                "desc": "这里描述这个场景的气候与氛围。",
                "seasons": {{1: 15.0, 2: 25.0, 3: 18.0, 4: 5.0}},
                "variance": 4.0,
                "temp_swing": 1.0,
                "cost_factor": 1.0,
                "env_weights": {{1: {{}}, 2: {{}}, 3: {{}}, 4: {{}}}},
                "disease_weights": {{"cold": 10, "gastro": 10, "pneumonia": 8,
                                    "chronic": 8, "frostbite": 5, "heatstroke": 5}},
            }}
        }}

    # ------------------------------------------------------------------
    def register_events(self):
        """新增事件。weight 采用万分之一精度（10000 = 100%）。"""
        return [{{
            "id": "{mod_id}_event_1",
            "name": "模组事件示例",
            "category": "意外",          # 日常/疾病/工作/情感/环境/意外
            "weight": 800,
            "descs": ["这里写事件描述，可以有多条备选。"],
            "cond": lambda p: True,      # 触发条件，可限制年龄/阶段/属性
            "tone": "neutral",           # good/bad/neutral/secret
            "special": False,
            "tags": [],
            "choices": [{{
                "label": "做个选择",
                "hint": "提示文字",
                "roll": "d6",
                "outcomes": [{{
                    "range": (1, 6),
                    "desc": "结果描述。",
                    "effects": {{"happy": 3}},
                    "tone": "good",
                }}],
                "need_money": 0,
                "need_disease": False,
            }}],
        }}]

    # ------------------------------------------------------------------
    def register_stages(self):
        """新增人生阶段（会追加到阶段流程里）。"""
        return [{{
            "id": "{mod_id}_stage",
            "name": "模组阶段",
            "start": 0, "end": 0,
            "next": "infant",
            "chance_key": "infant",
            "desc": "这个阶段的描述。",
            "branch": True,
        }}]

    # ------------------------------------------------------------------
    def daily_event_hook(self, player, dice):
        """可选：接管每日事件（返回事件字典则优先使用；返回 None 走普通抽签）"""
        return None

    def on_day_end(self, player, report):
        """可选：每天结束时的额外处理（例如模组专属的持续效果）"""
        return None

    def opening_text(self, player):
        """可选：开局介绍文本"""
        return "欢迎来到这个模组世界。"


# 保存本文件后重新启动游戏即可自动加载
'''

    @staticmethod
    def make_template(mod_id="my_novel", mod_name="我的名著模组",
                      mod_desc="自定义世界观与事件", author=""):
        class_name = "".join(part.capitalize() for part in re.split(r"[^0-9a-zA-Z]+", mod_id) if part) or "MyNovel"
        return LifeModCodec.TEMPLATE.format(
            mod_id=mod_id, mod_name=mod_name, mod_desc=mod_desc,
            author=author, class_name=class_name + "Mod")


def write_mod_template(path, mod_id="my_novel", mod_name="我的名著模组",
                       mod_desc="自定义世界观与事件", author=""):
    """把模组模板写入指定文件，返回 (是否成功, 说明)。"""
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(LifeModCodec.make_template(mod_id, mod_name, mod_desc, author))
        return True, "模组模板已写入：\n%s" % path
    except Exception as exc:
        return False, "写入模组模板失败：%s" % exc


def natural_death_rate(age, health=100.0, diseases=None):
    """
    计算当年自然死亡概率（0~1），采用分段 Gompertz 曲线：
        45 ~ 85 岁： 概率 = 起始概率 × GROWTH ^ (age - 45)
        85 岁以上  ： 在此基础上再乘以 ULTRA_GROWTH ^ (age - 85)（老年死亡率加速）
    默认参数（45 岁 0.4%、×1.0625/年）下的典型取值（满健康）：
        55 岁 0.8% ｜ 65 岁 1.5% ｜ 75 岁 2.8% ｜ 80 岁 3.6%
        85 岁 4.7% ｜ 90 岁 9.7% ｜ 95 岁 19.9% ｜ 100 岁 41%（几乎必然）
    再叠加健康修正（健康差的人死亡率最高放大 4.5 倍）与长期患病修正。
    该曲线经多种子实验标定：理性玩家的平均寿命稳定在 80 岁左右，
    多数人落在 70~95 岁，极少数能活到 100 岁以上。
    """
    try:
        age = float(age)
    except Exception:
        return 0.0
    if age <= NATURAL_DEATH_FLOOR_AGE:
        rate = 0.0
    else:
        rate = NATURAL_DEATH_BASE_RATE * (NATURAL_DEATH_GROWTH ** (age - NATURAL_DEATH_FLOOR_AGE))
        if age > NATURAL_DEATH_ULTRA_AGE:
            rate *= NATURAL_DEATH_ULTRA_GROWTH ** (age - NATURAL_DEATH_ULTRA_AGE)
    # 健康修正：健康越低，死亡率越高
    try:
        h = max(0.0, min(100.0, float(health)))
    except Exception:
        h = 100.0
    health_factor = NATURAL_DEATH_HEALTH_MIN + (NATURAL_DEATH_HEALTH_MAX - NATURAL_DEATH_HEALTH_MIN) * \
        ((100.0 - h) / 100.0) ** 2
    rate *= health_factor
    # 长期患病进一步削弱体质
    sick = len(diseases or [])
    if sick:
        rate *= (1.0 + 0.12 * sick)
    return max(0.0, min(1.0, rate))



# ==============================================================================
# 5. 效果字典：统一的属性变更描述与应用
# ==============================================================================
# 效果字典键名约定：
#   health / happy / money / temp / temp_now / temp_drift : 立即数值变更
#   disease  : 施加疾病，值为 (疾病id, 持续天数修正)
#   cure     : 立即治愈疾病，值为疾病id或 True
#   health_boost / happy_boost : 有上限的回复（不会超过 100）
#   func     : 特殊回调，签名 func(player) -> 追加描述(list[str])
#   title    : 变更条目的显示名（覆盖默认的提示文字）
# ==============================================================================


def merge_effect(target, extra):
    """把 extra 合并进 target 效果字典（数值累加，其余覆盖）。"""
    if not extra:
        return target
    for key, value in extra.items():
        if key == "func":
            target[key] = value
        elif isinstance(value, (int, float)) and isinstance(target.get(key), (int, float)):
            target[key] = target[key] + value
        else:
            target[key] = value
    return target


def describe_effects(effects, player=None):
    """
    把效果字典翻译成中文描述列表（用于选择弹窗的提示文字）。
    """
    if not effects:
        return []
    parts = []
    names = {
        "health": "健康", "happy": "幸福", "money": "金钱", "temp": "体温",
        "temp_now": "体温", "temp_drift": "体温趋势", "health_boost": "健康",
        "happy_boost": "幸福",
    }
    order = ["health", "happy", "money", "temp", "temp_now", "temp_drift",
             "health_boost", "happy_boost"]
    for key in order:
        if key not in effects:
            continue
        value = effects[key]
        if key in ("health", "happy", "money"):
            parts.append("%s %s" % (names[key], fmt_signed(value, 0 if key != "money" else 0)))
        elif key in ("temp", "temp_now"):
            parts.append("%s %s" % (names[key], fmt_signed(value, 1)))
        elif key == "health_boost":
            parts.append("健康 回复最多 %+d" % value)
        elif key == "happy_boost":
            parts.append("幸福 回复最多 %+d" % value)
        elif key == "temp_drift":
            parts.append("体温趋势 %s" % fmt_signed(value, 1))
    if "disease" in effects:
        did = effects["disease"]
        if isinstance(did, (tuple, list)):
            did = did[0]
        dis = DISEASES.get(did)
        parts.append("可能患病：%s" % (dis["name"] if dis else did))
    if effects.get("cure"):
        parts.append("立刻治愈当前疾病")
    return parts


# ==============================================================================
# 6. 城市气候系统
# ==============================================================================
# 每个城市包含：
#   tag            : 气候类型
#   desc           : 简介
#   seasons        : 四季基准气温（℃）
#   variance       : 每日气温波动幅度
#   temp_swing     : 环境事件造成的体温波动倍率（越高越"极端"）
#   cost_factor    : 消费水平系数（影响每月固定支出）
#   env_weights    : 四季环境气候事件权重表
#   disease_weights: 疾病易感权重（按季节合并计算的额外倾向）
# ==============================================================================

SEASON_NAMES = {1: "春季", 2: "夏季", 3: "秋季", 4: "冬季"}

CITIES = {
    "harbin": {
        "name": "哈尔滨",
        "tag": "寒冷",
        "desc": "北国冰城：冬季漫长严寒，寒潮与冻伤高发；室内供暖好，夏季凉爽宜人。",
        "seasons": {1: 4.0, 2: 22.0, 3: 5.0, 4: -18.0},
        "variance": 6.0,
        "temp_swing": 1.6,
        "cost_factor": 0.86,
        "env_weights": {
            1: {"cold_wave": 16, "blizzard": 12, "rain": 8, "haze": 5, "heat_wave": 0, "heatstroke": 0},
            2: {"heat_wave": 5, "heatstroke": 3, "rain": 12, "haze": 4, "cold_wave": 0, "blizzard": 0},
            3: {"cold_wave": 10, "rain": 10, "haze": 10, "blizzard": 2, "heat_wave": 0, "heatstroke": 0},
            4: {"cold_wave": 26, "blizzard": 18, "haze": 12, "rain": 2, "heat_wave": 0, "heatstroke": 0},
        },
        "disease_weights": {"cold": 20, "flu": 16, "tonsillitis": 12, "bronchitis": 10, "pneumonia": 10, "asthma": 6, "rhinitis": 4, "gastro": 8, "food_poisoning": 6, "gastritis": 6, "hypertension": 8, "heart_disease": 6, "diabetes": 6, "gout": 5, "migraine": 6, "insomnia": 5, "frostbite": 12, "burns": 4, "fracture": 5, "sprain": 6, "dental": 5, "dermatitis": 4, "depression": 4, "anxiety": 4, "heatstroke": 1},
    },
    "beijing": {
        "name": "北京",
        "tag": "温带",
        "desc": "温带季风：四季分明，春季沙尘、夏季闷热、冬季干冷，气候事件较为均衡。",
        "seasons": {1: 12.0, 2: 27.0, 3: 13.0, 4: -3.0},
        "variance": 5.0,
        "temp_swing": 1.15,
        "cost_factor": 1.10,
        "env_weights": {
            1: {"sandstorm": 14, "haze": 12, "rain": 8, "cold_wave": 5, "heat_wave": 0, "heatstroke": 0},
            2: {"heat_wave": 14, "heatstroke": 8, "rain": 14, "haze": 6, "cold_wave": 0, "blizzard": 0},
            3: {"haze": 14, "rain": 10, "cold_wave": 6, "sandstorm": 4, "heat_wave": 0, "heatstroke": 0},
            4: {"cold_wave": 16, "haze": 16, "blizzard": 8, "sandstorm": 4, "rain": 2, "heat_wave": 0},
        },
        "disease_weights": {"cold": 18, "flu": 16, "tonsillitis": 10, "bronchitis": 12, "pneumonia": 10, "asthma": 8, "rhinitis": 8, "gastro": 12, "food_poisoning": 8, "gastritis": 8, "hypertension": 10, "heart_disease": 8, "diabetes": 8, "gout": 6, "migraine": 8, "insomnia": 7, "frostbite": 6, "burns": 4, "fracture": 5, "sprain": 6, "dental": 6, "dermatitis": 5, "depression": 5, "anxiety": 5, "heatstroke": 3},
    },
    "shanghai": {
        "name": "上海",
        "tag": "亚热带",
        "desc": "亚热带季风：梅雨连绵、夏季湿热难耐，体质偏弱者易患肠胃疾病。",
        "seasons": {1: 15.0, 2: 30.0, 3: 20.0, 4: 6.0},
        "variance": 4.0,
        "temp_swing": 1.0,
        "cost_factor": 1.22,
        "env_weights": {
            1: {"rain": 16, "cold_wave": 4, "haze": 8, "heat_wave": 0, "heatstroke": 0},
            2: {"rain": 18, "heat_wave": 12, "heatstroke": 6, "haze": 4, "cold_wave": 0},
            3: {"rain": 10, "haze": 8, "cold_wave": 4, "heat_wave": 0, "heatstroke": 0},
            4: {"cold_wave": 10, "rain": 12, "haze": 10, "heat_wave": 0, "heatstroke": 0},
        },
        "disease_weights": {"cold": 16, "flu": 14, "tonsillitis": 10, "bronchitis": 10, "pneumonia": 8, "asthma": 8, "rhinitis": 10, "gastro": 18, "food_poisoning": 12, "gastritis": 10, "hypertension": 9, "heart_disease": 6, "diabetes": 7, "gout": 6, "migraine": 8, "insomnia": 8, "frostbite": 2, "burns": 4, "fracture": 5, "sprain": 7, "dental": 6, "dermatitis": 7, "depression": 5, "anxiety": 5, "heatstroke": 8},
    },
    "guangzhou": {
        "name": "广州",
        "tag": "炎热",
        "desc": "南国花城：长夏无冬，高温高湿，中暑与湿热型肠胃病高发。",
        "seasons": {1: 22.0, 2: 33.0, 3: 27.0, 4: 16.0},
        "variance": 3.0,
        "temp_swing": 1.25,
        "cost_factor": 1.05,
        "env_weights": {
            1: {"rain": 14, "heat_wave": 6, "heatstroke": 6, "haze": 4},
            2: {"heat_wave": 20, "heatstroke": 16, "rain": 16, "haze": 4},
            3: {"heat_wave": 8, "heatstroke": 8, "rain": 10, "haze": 8},
            4: {"heat_wave": 6, "heatstroke": 6, "cold_wave": 3, "rain": 6, "haze": 6},
        },
        "disease_weights": {"cold": 12, "flu": 12, "tonsillitis": 10, "bronchitis": 8, "pneumonia": 6, "asthma": 7, "rhinitis": 10, "gastro": 16, "food_poisoning": 12, "gastritis": 9, "hypertension": 8, "heart_disease": 5, "diabetes": 7, "gout": 7, "migraine": 7, "insomnia": 7, "frostbite": 1, "burns": 5, "fracture": 4, "sprain": 7, "dental": 6, "dermatitis": 8, "depression": 4, "anxiety": 4, "heatstroke": 16},
    },
}

CITY_ORDER = ["harbin", "beijing", "shanghai", "guangzhou"]

#: 春秋季环境事件的补充权重（让季节间差异更自然）
ENV_BASE_WEIGHTS = {
    1: {"rain": 6, "haze": 4, "cold_wave": 2, "sandstorm": 4},
    2: {"heat_wave": 4, "rain": 6, "heatstroke": 2},
    3: {"rain": 5, "haze": 5, "cold_wave": 4},
    4: {"cold_wave": 8, "blizzard": 4, "haze": 4},
}


def get_city(city_id):
    """取城市数据，未知城市退回北京（保证不崩溃）。"""
    return CITIES.get(city_id) or CITIES["beijing"]


def season_of_month(month):
    """月份 -> 季节编号（1春 2夏 3秋 4冬）。"""
    if month in (3, 4, 5):
        return 1
    if month in (6, 7, 8):
        return 2
    if month in (9, 10, 11):
        return 3
    return 4


def season_name(month):
    return SEASON_NAMES[season_of_month(month)]


def seasonal_avg_temp(city_id, month):
    """该城市该月的基准气温。"""
    city = get_city(city_id)
    season = season_of_month(month)
    base = city["seasons"].get(season, 20.0)
    # 同一季节内做小幅偏移，让同季不同月也有区别
    offset_map = {
        1: {3: -2.0, 4: 0.0, 5: 2.0},
        2: {6: -1.0, 7: 1.5, 8: 0.5},
        3: {9: 2.0, 10: 0.0, 11: -2.0},
        4: {12: -2.0, 1: 0.0, 2: 1.5},
    }
    return base + offset_map.get(season, {}).get(month, 0.0)


def roll_ambient_temp(dice, city_id, month):
    """
    投掷当日气温：基准气温 ± d6 波动（寒冷城市波动更大）。
    返回 (气温, DiceResult)
    """
    city = get_city(city_id)
    base = seasonal_avg_temp(city_id, month)
    res = dice.roll(6, 2, 0, "气温波动")
    swing = (res.value - 7) / 1.0            # 2d6 期望 7，范围 -5 ~ +5
    swing *= (city["variance"] / 5.0)
    return round(base + swing, 1), res


def env_weights_for(city_id, month):
    """合并城市权重与季节基础权重，返回 (事件id -> 权重) 字典。"""
    city = get_city(city_id)
    season = season_of_month(month)
    weights = {}
    for key, value in (city["env_weights"].get(season) or {}).items():
        if value > 0:
            weights[key] = weights.get(key, 0) + value
    for key, value in ENV_BASE_WEIGHTS.get(season, {}).items():
        weights[key] = weights.get(key, 0) + value
    return weights


def temperature_adjust(dice, player):
    """
    每日环境对体温的自发影响：
      * 气温过高/过低会把体温推离正常区间（有上限，不会一天之内暴走）
      * 同时身体会向 36.5℃ 回归，越偏离回归越强
      * 因此体温异常是"缓慢恶化 + 可自救"的过程，而不是必死陷阱
    返回 (体温变化量, 描述文本, DiceResult)
    """
    city = get_city(player.city)
    ambient = player.ambient_temp
    swing_factor = min(1.5, float(city["temp_swing"]))
    desc = []
    push = 0.0
    neutral = 36.5

    if ambient <= 0:
        push -= min(0.30, (0 - ambient) * 0.012) * swing_factor
        desc.append("严寒环境推低体温")
    elif ambient >= 33:
        push += min(0.30, (ambient - 33) * 0.012) * swing_factor
        desc.append("酷热环境推高体温")

    res = dice.d10("环境体温影响")
    push += (res.value - 5.5) / 10.0 * 0.25        # 轻微随机波动

    # 身体恒温调节：越偏离正常值，回归力越强（最低 0.12，避免"越冻越冷"）
    deviation = neutral - player.temp
    regulate = max(-0.30, min(0.30, deviation * 0.22))
    if abs(deviation) > 0.6:
        regulate += 0.12 if deviation > 0 else -0.12

    delta = push + regulate
    if regulate > 0 and player.temp < 36.2:
        desc.append("身体努力回暖")
    elif regulate < 0 and player.temp > 36.8:
        desc.append("身体努力降温")

    return round(delta, 2), "，".join(desc), res


# ==============================================================================
# 7. 疾病系统
# ==============================================================================
# 字段说明：
#   name / kind / desc : 名称、类型、描述
#   days               : (最短, 最长) 严重程度（1~5，用于判定"是否更严重"）
#   hp_per_day         : 每日健康扣除（已按"现实病程 + 游戏可玩性"标定）
#   happy_per_day      : 每日幸福扣除
#   cure_cost          : 彻底治愈费用
#   self_heal          : 每日自愈概率（0 表示不会自愈，只能花钱）
#   temp_mod           : 每日体温累积影响（发烧为正、冻伤为负）
#   needs_cure         : True 表示必须花钱治疗，否则一直持续（慢性病）
#   fatal              : True 表示危重疾病，健康过低时可能直接致死
#   severity           : 1~5 严重度（替代旧的 DISEASE_SEVERITY 表）
#   scope              : 适用人群（all/child/adult/elder）——影响抽病权重
#   contagion          : 传染性（1~3），影响季节/人群聚集时的权重
#   tags               : 附加标签（fever 发热 / chill 失温 / chronic 慢性 / injury 外伤）
# ==============================================================================

DISEASES = {
    # ---------------- 呼吸道 ----------------
    "cold": {
        "id": "cold", "name": "普通感冒", "kind": "轻症",
        "desc": "鼻塞、流涕、打喷嚏，通常一周左右自愈。",
        "days": (2, 6), "hp_per_day": 1.6, "happy_per_day": 2,
        "cure_cost": 80.0, "self_heal": 0.55, "temp_mod": 0.10,
        "severity": 1, "scope": "all", "contagion": 2, "tags": ["fever"],
    },
    "flu": {
        "id": "flu", "name": "流行性感冒", "kind": "中症",
        "desc": "高热、全身酸痛，比普通感冒重得多，容易并发肺炎。",
        "days": (4, 10), "hp_per_day": 2.6, "happy_per_day": 3,
        "cure_cost": 260.0, "self_heal": 0.35, "temp_mod": 0.22,
        "severity": 2, "scope": "all", "contagion": 3, "tags": ["fever"],
    },
    "tonsillitis": {
        "id": "tonsillitis", "name": "扁桃体炎", "kind": "中症",
        "desc": "咽喉肿痛、吞咽困难，儿童和青少年尤其常见。",
        "days": (3, 8), "hp_per_day": 2.2, "happy_per_day": 2,
        "cure_cost": 220.0, "self_heal": 0.35, "temp_mod": 0.18,
        "severity": 2, "scope": "child", "contagion": 1, "tags": ["fever"],
    },
    "bronchitis": {
        "id": "bronchitis", "name": "支气管炎", "kind": "中症",
        "desc": "咳嗽不止、痰多胸闷，抽烟或空气差的人更容易得。",
        "days": (5, 12), "hp_per_day": 2.8, "happy_per_day": 3,
        "cure_cost": 420.0, "self_heal": 0.25, "temp_mod": 0.15,
        "severity": 3, "scope": "all", "contagion": 1, "tags": ["fever"],
    },
    "pneumonia": {
        "id": "pneumonia", "name": "肺炎", "kind": "重症",
        "desc": "高烧不退、呼吸带杂音，必须住院治疗，否则非常危险。",
        "days": (7, 18), "hp_per_day": 4.2, "happy_per_day": 5,
        "cure_cost": 2600.0, "self_heal": 0.05, "temp_mod": 0.30,
        "severity": 5, "scope": "all", "contagion": 1, "tags": ["fever"], "fatal": True,
    },
    "asthma": {
        "id": "asthma", "name": "哮喘发作", "kind": "顽疾",
        "desc": "气道痉挛、喘不上气，换季或雾霾天特别容易发作。",
        "days": (2, 6), "hp_per_day": 3.0, "happy_per_day": 4,
        "cure_cost": 480.0, "self_heal": 0.45, "temp_mod": 0.05,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    "rhinitis": {
        "id": "rhinitis", "name": "过敏性鼻炎", "kind": "轻症",
        "desc": "喷嚏不断、鼻子发痒，春天和雾霾天最难受。",
        "days": (4, 12), "hp_per_day": 0.8, "happy_per_day": 2,
        "cure_cost": 180.0, "self_heal": 0.45, "temp_mod": 0.0,
        "severity": 1, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    # ---------------- 消化道 ----------------
    "gastro": {
        "id": "gastro", "name": "急性肠胃炎", "kind": "中症",
        "desc": "上吐下泻、浑身发软，多因吃坏东西引起。",
        "days": (3, 8), "hp_per_day": 2.4, "happy_per_day": 3,
        "cure_cost": 320.0, "self_heal": 0.30, "temp_mod": 0.08,
        "severity": 2, "scope": "all", "contagion": 2, "tags": [],
    },
    "food_poisoning": {
        "id": "food_poisoning", "name": "食物中毒", "kind": "中症",
        "desc": "剧烈腹痛、反复呕吐，需要尽快补液。",
        "days": (2, 5), "hp_per_day": 3.2, "happy_per_day": 4,
        "cure_cost": 400.0, "self_heal": 0.35, "temp_mod": 0.12,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["fever"],
    },
    "gastritis": {
        "id": "gastritis", "name": "慢性胃炎", "kind": "顽疾",
        "desc": "胃部隐痛、反酸胀气，饮食不规律的人容易拖成老毛病。",
        "days": (15, 40), "hp_per_day": 0.9, "happy_per_day": 2,
        "cure_cost": 900.0, "self_heal": 0.10, "temp_mod": 0.0,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "appendicitis": {
        "id": "appendicitis", "name": "阑尾炎", "kind": "急症",
        "desc": "右下腹剧痛、按下去更疼，必须马上手术。",
        "days": (5, 12), "hp_per_day": 4.5, "happy_per_day": 5,
        "cure_cost": 3800.0, "self_heal": 0.02, "temp_mod": 0.25,
        "severity": 5, "scope": "all", "contagion": 0, "tags": ["fever"], "fatal": True,
    },
    "hemorrhoids": {
        "id": "hemorrhoids", "name": "痔疮", "kind": "轻症",
        "desc": "久坐、便秘之后的老毛病，坐立不安。",
        "days": (5, 15), "hp_per_day": 0.7, "happy_per_day": 2,
        "cure_cost": 600.0, "self_heal": 0.35, "temp_mod": 0.0,
        "severity": 2, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    # ---------------- 心血管 / 代谢 ----------------
    "hypertension": {
        "id": "hypertension", "name": "高血压", "kind": "慢性病",
        "desc": "头晕、后颈发紧，需要长期吃药控制，否则伤及心脑。",
        "days": (25, 60), "hp_per_day": 1.1, "happy_per_day": 2,
        "cure_cost": 1600.0, "self_heal": 0.0, "temp_mod": 0.02,
        "severity": 4, "scope": "elder", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True,
    },
    "heart_disease": {
        "id": "heart_disease", "name": "冠心病", "kind": "重症",
        "desc": "胸闷、心悸，情绪激动或劳累时可能急性发作。",
        "days": (20, 50), "hp_per_day": 1.8, "happy_per_day": 3,
        "cure_cost": 12000.0, "self_heal": 0.0, "temp_mod": 0.0,
        "severity": 5, "scope": "elder", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True, "fatal": True,
    },
    "diabetes": {
        "id": "diabetes", "name": "糖尿病", "kind": "慢性病",
        "desc": "口渴、多尿、体重下降，需要长期控糖与忌口。",
        "days": (30, 70), "hp_per_day": 1.0, "happy_per_day": 3,
        "cure_cost": 2400.0, "self_heal": 0.0, "temp_mod": 0.0,
        "severity": 4, "scope": "adult", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True,
    },
    "hyperlipidemia": {
        "id": "hyperlipidemia", "name": "高血脂", "kind": "慢性病",
        "desc": "体检报告上的常客，控制饮食就能缓解。",
        "days": (20, 50), "hp_per_day": 0.6, "happy_per_day": 1,
        "cure_cost": 1200.0, "self_heal": 0.05, "temp_mod": 0.0,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "gout": {
        "id": "gout", "name": "痛风", "kind": "顽疾",
        "desc": "关节红肿剧痛，半夜能把人疼醒，海鲜啤酒是元凶。",
        "days": (4, 14), "hp_per_day": 2.4, "happy_per_day": 4,
        "cure_cost": 800.0, "self_heal": 0.20, "temp_mod": 0.05,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "anemia": {
        "id": "anemia", "name": "贫血", "kind": "慢性病",
        "desc": "脸色苍白、容易头晕乏力，女性与偏食者更常见。",
        "days": (10, 30), "hp_per_day": 0.9, "happy_per_day": 2,
        "cure_cost": 700.0, "self_heal": 0.25, "temp_mod": 0.0,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    # ---------------- 感染 / 其他内科 ----------------
    "urinary_infection": {
        "id": "urinary_infection", "name": "尿路感染", "kind": "中症",
        "desc": "尿急尿痛、小腹坠胀，需要多喝水并尽快用药。",
        "days": (3, 9), "hp_per_day": 2.0, "happy_per_day": 4,
        "cure_cost": 300.0, "self_heal": 0.25, "temp_mod": 0.15,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["fever"],
    },
    "kidney_stone": {
        "id": "kidney_stone", "name": "肾结石", "kind": "急症",
        "desc": "腰部绞痛，疼起来直不起身，严重时需要碎石。",
        "days": (5, 15), "hp_per_day": 3.6, "happy_per_day": 5,
        "cure_cost": 4200.0, "self_heal": 0.10, "temp_mod": 0.05,
        "severity": 4, "scope": "adult", "contagion": 0, "tags": [],
    },
    "thyroid": {
        "id": "thyroid", "name": "甲状腺疾病", "kind": "慢性病",
        "desc": "心慌、怕冷或怕热、体重异常，需要长期服药。",
        "days": (25, 60), "hp_per_day": 0.8, "happy_per_day": 2,
        "cure_cost": 1800.0, "self_heal": 0.0, "temp_mod": 0.03,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
        "needs_cure": True,
    },
    "liver_disease": {
        "id": "liver_disease", "name": "脂肪肝 / 肝功能异常", "kind": "慢性病",
        "desc": "体检提示肝酶升高，多半是熬夜和饮食造成的。",
        "days": (20, 50), "hp_per_day": 0.9, "happy_per_day": 2,
        "cure_cost": 2000.0, "self_heal": 0.10, "temp_mod": 0.0,
        "severity": 3, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "migraine": {
        "id": "migraine", "name": "偏头痛", "kind": "顽疾",
        "desc": "一侧头痛、怕光怕吵，压力大时发作频繁。",
        "days": (2, 7), "hp_per_day": 1.4, "happy_per_day": 4,
        "cure_cost": 260.0, "self_heal": 0.45, "temp_mod": 0.0,
        "severity": 2, "scope": "adult", "contagion": 0, "tags": ["chronic"],
    },
    "insomnia": {
        "id": "insomnia", "name": "失眠症", "kind": "轻症",
        "desc": "躺下两小时还睡不着，白天精神恍惚。",
        "days": (5, 20), "hp_per_day": 0.8, "happy_per_day": 3,
        "cure_cost": 400.0, "self_heal": 0.40, "temp_mod": 0.0,
        "severity": 2, "scope": "adult", "contagion": 0, "tags": [],
    },
    # ---------------- 外科 / 外伤 ----------------
    "fracture": {
        "id": "fracture", "name": "骨折", "kind": "外伤",
        "desc": "骨头断了，需要打石膏静养很长一段时间。",
        "days": (20, 45), "hp_per_day": 2.0, "happy_per_day": 3,
        "cure_cost": 3000.0, "self_heal": 0.05, "temp_mod": 0.05,
        "severity": 4, "scope": "all", "contagion": 0, "tags": ["injury"],
    },
    "sprain": {
        "id": "sprain", "name": "扭伤", "kind": "外伤",
        "desc": "脚踝或手腕扭伤，肿得像个馒头。",
        "days": (5, 14), "hp_per_day": 1.2, "happy_per_day": 2,
        "cure_cost": 300.0, "self_heal": 0.40, "temp_mod": 0.0,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["injury"],
    },
    "burns": {
        "id": "burns", "name": "烫伤 / 烧伤", "kind": "外伤",
        "desc": "皮肤红肿起泡，处理不当会留疤甚至感染。",
        "days": (4, 12), "hp_per_day": 2.6, "happy_per_day": 3,
        "cure_cost": 1200.0, "self_heal": 0.20, "temp_mod": 0.10,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["injury"],
    },
    "frostbite": {
        "id": "frostbite", "name": "冻伤", "kind": "外伤",
        "desc": "手脚冻得失去知觉，严重时皮肤发黑，必须尽快处理。",
        "days": (3, 9), "hp_per_day": 2.2, "happy_per_day": 3,
        "cure_cost": 260.0, "self_heal": 0.25, "temp_mod": -0.30,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["chill", "injury"],
    },
    "heatstroke": {
        "id": "heatstroke", "name": "中暑", "kind": "急症",
        "desc": "头晕恶心、体温飙升，需要马上降温补水。",
        "days": (2, 6), "hp_per_day": 3.0, "happy_per_day": 4,
        "cure_cost": 300.0, "self_heal": 0.35, "temp_mod": 0.35,
        "severity": 2, "scope": "all", "contagion": 0, "tags": ["fever"],
    },
    # ---------------- 皮肤 / 口腔 / 眼耳 ----------------
    "dermatitis": {
        "id": "dermatitis", "name": "皮炎 / 湿疹", "kind": "轻症",
        "desc": "皮肤发红发痒，越挠越难受。",
        "days": (5, 20), "hp_per_day": 0.6, "happy_per_day": 3,
        "cure_cost": 350.0, "self_heal": 0.30, "temp_mod": 0.0,
        "severity": 1, "scope": "all", "contagion": 0, "tags": ["chronic"],
    },
    "dental": {
        "id": "dental", "name": "牙痛 / 龋齿", "kind": "轻症",
        "desc": "牙疼不是病，疼起来真要命，补牙还要花不少钱。",
        "days": (3, 10), "hp_per_day": 1.2, "happy_per_day": 4,
        "cure_cost": 900.0, "self_heal": 0.25, "temp_mod": 0.0,
        "severity": 2, "scope": "all", "contagion": 0, "tags": [],
    },
    "conjunctivitis": {
        "id": "conjunctivitis", "name": "结膜炎", "kind": "轻症",
        "desc": "眼睛红痒、分泌物增多，传染性很强。",
        "days": (3, 8), "hp_per_day": 0.9, "happy_per_day": 3,
        "cure_cost": 200.0, "self_heal": 0.45, "temp_mod": 0.05,
        "severity": 1, "scope": "all", "contagion": 2, "tags": [],
    },
    "otitis": {
        "id": "otitis", "name": "中耳炎", "kind": "中症",
        "desc": "耳朵闷痛、听力下降，小孩子尤其容易得。",
        "days": (4, 10), "hp_per_day": 1.8, "happy_per_day": 3,
        "cure_cost": 400.0, "self_heal": 0.35, "temp_mod": 0.15,
        "severity": 2, "scope": "child", "contagion": 1, "tags": ["fever"],
    },
    "hemorrhagic_fever": {
        "id": "hemorrhagic_fever", "name": "重症感染", "kind": "危重症",
        "desc": "高热、寒战、意识模糊，必须立刻住院抢救。",
        "days": (8, 20), "hp_per_day": 5.0, "happy_per_day": 6,
        "cure_cost": 20000.0, "self_heal": 0.02, "temp_mod": 0.45,
        "severity": 5, "scope": "all", "contagion": 2, "tags": ["fever"],
        "fatal": True,
    },
    # ---------------- 心理健康（现实中最常见的"病"之一）----------------
    "depression": {
        "id": "depression", "name": "抑郁症", "kind": "心理疾病",
        "desc": "提不起劲、对什么都失去兴趣，需要长期疏导与治疗。",
        "days": (30, 90), "hp_per_day": 1.0, "happy_per_day": 5,
        "cure_cost": 3000.0, "self_heal": 0.02, "temp_mod": 0.0,
        "severity": 4, "scope": "all", "contagion": 0, "tags": ["mental"],
        "needs_cure": True,
    },
    "anxiety": {
        "id": "anxiety", "name": "焦虑症", "kind": "心理疾病",
        "desc": "心慌、手抖、总是担心最坏的结果。",
        "days": (15, 45), "hp_per_day": 0.8, "happy_per_day": 4,
        "cure_cost": 1500.0, "self_heal": 0.10, "temp_mod": 0.0,
        "severity": 3, "scope": "all", "contagion": 0, "tags": ["mental"],
    },
}

#: 疾病严重度（由 severity 字段生成，保留旧接口名）
DISEASE_SEVERITY = {k: v.get("severity", 2) for k, v in DISEASES.items()}

#: 常见疾病总览（供帮助面板展示）
COMMON_DISEASE_KEYS = [
    "cold", "flu", "tonsillitis", "bronchitis", "pneumonia", "asthma", "rhinitis",
    "gastro", "food_poisoning", "gastritis", "appendicitis", "hemorrhoids",
    "hypertension", "heart_disease", "diabetes", "hyperlipidemia", "gout", "anemia",
    "urinary_infection", "kidney_stone", "thyroid", "liver_disease",
    "migraine", "insomnia", "fracture", "sprain", "burns", "frostbite", "heatstroke",
    "dermatitis", "dental", "conjunctivitis", "otitis", "hemorrhagic_fever",
    "depression", "anxiety",
]

#: 疾病分类（用于界面分组展示）
DISEASE_GROUPS = [
    ("呼吸道", ["cold", "flu", "tonsillitis", "bronchitis", "pneumonia", "asthma", "rhinitis"]),
    ("消化道", ["gastro", "food_poisoning", "gastritis", "appendicitis", "hemorrhoids"]),
    ("心血管/代谢", ["hypertension", "heart_disease", "diabetes", "hyperlipidemia",
                     "gout", "anemia", "thyroid", "liver_disease"]),
    ("感染与其他内科", ["urinary_infection", "kidney_stone", "migraine", "insomnia",
                        "hemorrhagic_fever"]),
    ("外伤/环境", ["fracture", "sprain", "burns", "frostbite", "heatstroke"]),
    ("皮肤/口腔/眼耳", ["dermatitis", "dental", "conjunctivitis", "otitis"]),
    ("心理", ["depression", "anxiety"]),
]

#: 患病概率的年龄系数（U 型曲线：婴幼儿偏高 -> 青少年最低 -> 老年快速升高）
#: 已按"各年龄段事件暴露量不同"做过实验修正，使实际患病频率呈标准 U 型
SICKNESS_AGE_POINTS = [
    (0, 1.20), (1, 1.15), (2, 1.05), (4, 0.95), (6, 0.88),
    (10, 0.80), (14, 0.72), (18, 0.62), (25, 0.66), (35, 0.85),
    (45, 1.15), (55, 1.70), (65, 2.45), (75, 3.40), (85, 4.60), (100, 5.80),
]

#: 患病基础概率（"患病机会"出现后真正病倒的概率）
SICKNESS_BASE_RATE = 0.055

#: 目标"每年生病次数"曲线（普通人、体质 50 分）：用于反推每日患病概率
#: 与真实人生接近：婴幼儿 3~4 次/年，青少年 1 次/年，老年人 4~6 次/年
ILLNESS_PER_YEAR_POINTS = [
    (0, 3.40), (1, 3.60), (2, 3.20), (4, 2.80), (6, 2.50),
    (10, 1.80), (14, 1.20), (18, 1.00), (25, 0.90), (35, 1.00),
    (45, 1.40), (55, 2.00), (65, 2.80), (75, 4.00), (85, 5.40), (100, 6.50),
]

#: 单次"患病机会"对应的掷骰精度（万分之一），使间隔分布更细腻
ILLNESS_ROLL_D10000 = 10000


def _interp(points, value):
    """在 (x, y) 点列上做线性插值。"""
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= value <= x1:
            ratio = (value - x0) / float(x1 - x0) if x1 != x0 else 0.0
            return y0 + (y1 - y0) * ratio
    return points[-1][1]


def illness_per_year(age, constitution=CONSTITUTION_MEAN):
    """
    该年龄 + 该体质下，平均每年生病次数（真实感的核心参数）。
    体质通过易感倍率调节：体质 80 分约 0.45 倍，体质 20 分约 1.8 倍。
    """
    base = _interp(ILLNESS_PER_YEAR_POINTS, age)
    return base * constitution_susceptibility(constitution)


def sickness_age_factor(age):
    """按年龄对患病概率做插值，形成 U 型曲线（保留给旧接口使用）。"""
    return _interp(SICKNESS_AGE_POINTS, age)


def sickness_probability(player):
    """
    计算"今天是否会生病"的**每日概率**（0~0.05），综合：
        * 基础发病率（随年龄呈 U 型：幼年高 -> 青少年低 -> 老年高）
        * 体质（开局固定参数，正态分布；越弱越容易病）
        * 当前健康 / 幸福 / 体温状态
        * 城市易感倾向（不同城市疾病权重均值不同）
    例：3 岁幼儿、体质 50 -> 约 3.2 次/年 -> 每日约 0.88%
        25 岁成人、体质 50 -> 约 0.90 次/年 -> 每日约 0.25%
        75 岁老人、体质 50 -> 约 4.0 次/年 -> 每日约 1.10%
    """
    age = getattr(player, "age", 0)
    constitution = getattr(player, "constitution", CONSTITUTION_MEAN)
    per_year = illness_per_year(age, constitution)
    daily = per_year / float(DAYS_PER_YEAR)

    # 状态修正
    kind = player_status_factor(player)
    daily *= kind
    # 城市整体易感倾向
    city = get_city(getattr(player, "city", "beijing"))
    weights = [w for w in city["disease_weights"].values()]
    avg = (sum(weights) / float(len(weights))) if weights else 10.0
    daily *= max(0.7, min(1.35, avg / 10.0))
    return max(0.0, min(0.05, daily))


def player_status_factor(player):
    """健康 / 幸福 / 体温对患病概率的修正系数。"""
    factor = 1.0
    try:
        health = float(player.health)
        happy = float(player.happy)
        temp = float(player.temp)
    except Exception:
        return 1.0
    if health < 35:
        factor *= 1.45
    elif health < 60:
        factor *= 1.18
    if happy < LOW_HAPPY_THRESHOLD:
        factor *= 1.22
    if temp >= 38.0 or temp <= 35.2:
        factor *= 1.35
    elif temp > TEMP_NORMAL_HIGH or temp < TEMP_NORMAL_LOW:
        factor *= 1.12
    sick = len(getattr(player, "diseases", []) or [])
    if sick >= 2:
        factor *= 1.25
    return factor


def illness_gap_ok(player, min_gap=None):
    """
    生病间隔检查：距上次生病至少 MIN_ILLNESS_GAP_DAYS 天，
    避免出现"一个月生好几次病"这种不现实的情况。
    """
    min_gap = MIN_ILLNESS_GAP_DAYS if min_gap is None else min_gap
    last = getattr(player, "last_illness_day", None)
    if last is None:
        return True
    return (getattr(player, "total_days", 0) - last) >= min_gap


def disease_table_text(full=False):
    """
    疾病速查表文本（用于帮助面板）。
    full=False 时只列出常见病摘要；full=True 时按分类列出全部疾病。
    """
    if not full:
        lines = ["  共收录 %d 种常见疾病，按分类如下：" % len(COMMON_DISEASE_KEYS)]
        for group_name, keys in DISEASE_GROUPS:
            names = "、".join(DISEASES[k]["name"] for k in keys if k in DISEASES)
            lines.append("  · %s（%d 种）：%s" % (group_name, len(keys), names))
        lines.append("")
        lines.append("  示例（每日健康/幸福扣除、治愈费、自愈率）：")
        for key in ("cold", "flu", "gastro", "pneumonia", "appendicitis",
                    "hypertension", "depression", "fracture"):
            d = DISEASES[key]
            lines.append("    - %s（%s）：健康 -%.1f / 幸福 -%d，治愈 %.0f，自愈 %s%s" % (
                d["name"], d["kind"], d["hp_per_day"], d["happy_per_day"], d["cure_cost"],
                pct_text(d["self_heal"]) if d["self_heal"] > 0 else "无（需治疗）",
                "，危重" if d.get("fatal") else ""))
        return "\n".join(lines)
    lines = []
    for group_name, keys in DISEASE_GROUPS:
        lines.append("【%s】" % group_name)
        for key in keys:
            d = DISEASES.get(key)
            if not d:
                continue
            days_txt = "%d~%d 天" % d["days"]
            lines.append("  · %-14s %-6s 病程 %-10s 健康 -%.1f/天  幸福 -%d/天  治愈 %-8.0f 自愈 %-6s%s" % (
                d["name"], d["kind"], days_txt, d["hp_per_day"], d["happy_per_day"],
                d["cure_cost"],
                pct_text(d["self_heal"]) if d["self_heal"] > 0 else "无",
                "  危重" if d.get("fatal") else ("  需长期治疗" if d.get("needs_cure") else "")))
        lines.append("")
    return "\n".join(lines)


def make_disease(dice, disease_id, hp_scale=1.0, days_bonus=0, temp_scale=1.0):
    """
    生成一个活动疾病实例（字典）。
    hp_scale  : 每日掉血倍率（受年龄、体质影响）
    days_bonus: 持续天数修正（负值表示恢复更快）
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]
    lo, hi = base["days"]
    # 用骰子决定持续天数，兼顾随机与均衡
    span = max(1, hi - lo + 1)
    res = dice.roll(span if span in DICE_FACES else 6, 1, 0, "病程天数")
    days = lo + (res.value - 1) % span + days_bonus
    days = max(1, int(days))
    return {
        "id": base["id"],
        "name": base["name"],
        "kind": base["kind"],
        "days": days,                                   # 剩余持续天数
        "total_days": days,
        "hp_per_day": round(base["hp_per_day"] * hp_scale, 2),
        "happy_per_day": base["happy_per_day"],
        "cure_cost": float(base["cure_cost"]),
        "self_heal": base["self_heal"],
        "temp_mod": round(base["temp_mod"] * temp_scale, 3),
        "needs_cure": base.get("needs_cure", False),
        "fatal": base.get("fatal", False),
        "severity": base.get("severity", 2),
        "desc": base.get("desc", ""),
        "tags": list(base.get("tags", [])),
        "days_roll": res.to_dict(),
    }


#: 疾病抽签的"人群适用性"倍率（scope 字段 + 年龄）
def _scope_modifier(player, disease):
    """
    某些病只在特定人群高发（例如幼儿中耳炎、老人冠心病），
    用倍率模拟真实人群分布；不适用时给一个很低但非零的权重。
    """
    scope = disease.get("scope", "all")
    age = getattr(player, "age", 30)
    if scope == "all":
        return 1.0
    if scope == "child":
        if age <= 3:
            return 2.0
        if age <= 12:
            return 1.8
        if age <= 18:
            return 1.0
        if age <= 40:
            return 0.25
        return 0.08
    if scope == "adult":
        if age < 16:
            return 0.06
        if age <= 60:
            return 1.0
        return 1.2
    if scope == "elder":
        if age < 45:
            return 0.05
        if age < 60:
            return 0.4
        if age < 75:
            return 1.3
        return 2.0
    return 1.0


def disease_weight_for(player, disease_id):
    """
    计算某种疾病相对易感程度：
        城市气候 + 季节 + 年龄人群 + 体质 + 当前体温 + 健康状态。
    疾病种类扩展到 30+ 种后，这里统一用"标签 + scope"驱动，避免逐病硬编码。
    """
    disease = DISEASES.get(disease_id) or DISEASES["cold"]
    city = get_city(player.city)
    base = float(city["disease_weights"].get(disease_id, 5))
    tags = set(disease.get("tags") or [])
    season = season_of_month(player.month)
    contagion = float(disease.get("contagion", 0) or 0)

    # ---- 季节修正 ----
    season_mod = 1.0
    if "fever" in tags or contagion >= 2:
        # 呼吸道/传染病：冬春高发
        season_mod *= {1: 1.25, 2: 0.7, 3: 1.3, 4: 1.8}.get(season, 1.0)
    if "chill" in tags:
        season_mod *= {1: 0.6, 2: 0.0, 3: 0.8, 4: 2.4}.get(season, 1.0)
    if disease_id == "heatstroke" or "heat" in tags:
        season_mod *= {1: 0.4, 2: 2.4, 3: 0.7, 4: 0.0}.get(season, 1.0)
    if disease_id in ("gastro", "food_poisoning"):
        # 夏季食物易变质
        season_mod *= {1: 1.0, 2: 1.7, 3: 1.1, 4: 0.8}.get(season, 1.0)
    if "injury" in tags:
        season_mod *= {1: 1.1, 2: 1.15, 3: 1.05, 4: 1.15}.get(season, 1.0)
    if "mental" in tags:
        # 换季与冬季情绪问题更多
        season_mod *= {1: 1.1, 2: 1.0, 3: 1.05, 4: 1.2}.get(season, 1.0)
    base *= season_mod

    # ---- 人群适用性（年龄）----
    base *= _scope_modifier(player, disease)

    # ---- 年龄修正：老人更易重症/慢性病，幼儿更易感染 ----
    age = player.age
    severity = disease.get("severity", 2)
    if age <= 6:
        if "fever" in tags or contagion >= 1:
            base *= 1.35
        if "chronic" in tags or severity >= 4:
            base *= 0.2
    elif age >= 60:
        if "chronic" in tags or severity >= 4:
            base *= 1.7
        if "fever" in tags:
            base *= 1.4
    elif age >= 45:
        if "chronic" in tags or severity >= 4:
            base *= 1.3

    # ---- 体温异常 ----
    if player.temp >= 38.0 and ("fever" in tags or severity >= 4):
        base *= 1.35
    if player.temp <= 35.2 and ("chill" in tags or "fever" in tags):
        base *= 1.45

    # ---- 体质影响易感程度（体质越好，重病概率越低）----
    sus = constitution_susceptibility(getattr(player, "constitution", CONSTITUTION_MEAN))
    base *= (0.6 + 0.5 * sus)

    # ---- 健康低时更容易病倒 ----
    if player.health <= 40:
        base *= 1.3
    return max(0.4, base)


def roll_disease(dice, player, hp_scale=1.0, forced_id=None):
    """
    用加权骰子抽取一种疾病并生成实例。
    返回 (疾病实例 或 None, DiceResult, 说明)
    说明：真正是否发病由 sickness_probability（U 型年龄曲线）决定，
          掷骰失败表示"这次没有真的病倒"，返回 None。
    """
    if forced_id:
        return make_disease(dice, forced_id, hp_scale), dice.d4("重症判定"), ""
    # ---- 是否真的生病：d100 与年龄相关的发病概率对抗 ----
    gate_roll = dice.d100("患病判定")
    prob = sickness_probability(player)
    if gate_roll.value > prob * 100.0:
        return None, gate_roll, "这次身体扛住了，没有发展成疾病"
    weight_items = []
    for key in DISEASES:
        w = disease_weight_for(player, key)
        # 用 d10 做一个轻微随机扰动，避免完全固定
        jitter = dice.d10("易感扰动").value / 10.0
        weight_items.append((key, w * (0.6 + jitter * 0.8)))
    total = sum(w for _, w in weight_items) or 1.0
    res = dice.d100("疾病判定")
    acc = 0.0
    target = (res.value - 0.5) / 100.0 * total
    chosen = weight_items[-1][0]
    for key, w in weight_items:
        acc += w
        if target <= acc:
            chosen = key
            break
    return make_disease(dice, chosen, hp_scale), res, ""



# ==============================================================================
# 8. 事件库
# ==============================================================================
# 每个事件包含：
#   id / name / category : 标识、名称、大类
#   weight               : 基础权重（越高越容易抽到）
#   cond(player)         : 触发条件
#   descs                : 事件描述模板（支持 {name} {age} 等占位符）
#   choices              : [{"label":..., "hint":..., "roll":"d6", "outcomes":[...]}]
#        每个 outcome: {"range":(low,high), "desc":..., "effects":{...}, "tone":...}
#   tone                 : 事件基调（good/bad/neutral/secret）
#   special              : 是否为隐藏特殊事件
# ==============================================================================

TRUE_TONE_COLORS = {
    "good": "#4ad07a",
    "bad": "#ff6b6b",
    "neutral": "#f0c040",
    "secret": "#b98cff",
}

EVENTS = {}
EVENT_ORDER = []


def register_event(event, internal=False):
    """
    注册事件到全局事件表。
    internal=True 表示该事件不作为候选（例如"感冒加重"只能由感冒硬扛失败触发）。
    """
    EVENTS[event["id"]] = event
    if not internal:
        EVENT_ORDER.append(event["id"])
    return event


def _ev(eid, name, category, weight, descs, choices, cond=None, tone="neutral",
        special=False, tags=None, internal=False):
    """事件注册辅助函数。"""
    return register_event({
        "id": eid,
        "name": name,
        "category": category,
        "weight": weight,
        "descs": descs,
        "choices": choices,
        "cond": cond or (lambda p: True),
        "tone": tone,
        "special": special,
        "tags": tags or [],
    }, internal=internal)


def _out(lo, hi, desc, effects=None, tone="neutral", next_event=None):
    """
    构造一个结果区间。
    next_event 用于"连锁事件"：结算完本结果后立刻追加一个后续事件。
    """
    return {"range": (lo, hi), "desc": desc, "effects": effects or {},
            "tone": tone, "next_event": next_event}


def _out_parent(lo, hi, desc, effects=None, tone="neutral", next_event=None):
    """带"父母同在"标记的结果区间（对 6 岁以下开放）。"""
    out = _out(lo, hi, desc, effects, tone, next_event)
    out["with_parents"] = True
    return out


def _choice_parent(label, hint="", roll="d6", outcomes=None,
                   need_money=0, need_disease=False):
    """带"父母同在"标记的选项（对 6 岁以下开放）。"""
    return _choice(label, hint, roll, outcomes, need_money, need_disease,
                   with_parents=True)


def _choice(label, hint="", roll="d6", outcomes=None, need_money=0, need_disease=False,
            with_parents=False):
    return {
        "label": label,
        "hint": hint,
        "roll": roll,
        "outcomes": outcomes or [],
        "need_money": need_money,
        "need_disease": need_disease,
        "with_parents": with_parents,
    }


# ------------------------------------------------------------------------------
# 8.1 疾病类事件
# ------------------------------------------------------------------------------

def _apply_disease_factory(disease_id, hp_scale=1.0, temp_scale=1.0, days_bonus=0):
    """
    生成一个强制施加指定疾病的 func（用于"病情必然加重"的连锁事件）。
    注意：普通患病事件请使用 _apply_disease_gate，让患病概率遵守 U 型年龄曲线。
    """
    def _apply(player):
        if player.has_disease(disease_id):
            return ["你身上的%s还没好，这次是雪上加霜。" % DISEASES[disease_id]["name"]]
        info, _ = player.add_disease(disease_id, hp_scale=hp_scale,
                                     temp_scale=temp_scale, days_bonus=days_bonus,
                                     force=True)
        if not info:
            return []
        return ["患上了%s（预计持续 %d 天，每日健康 -%.1f）"
                % (info["name"], info["days"], info["hp_per_day"])]
    return _apply


def _apply_disease_gate(disease_id, hp_scale=1.0, temp_scale=1.0):
    """
    生成一个"先判定再患病"的 func：
    若玩家当前没有该疾病，则按 U 型年龄曲线 + 体质判定是否真的病倒。
    （用于"是否发病还不确定"的场景，例如硬扛之后病情加重）
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]

    def _apply(player):
        if player.has_disease(disease_id):
            return ["你身上的%s还没好，这次是雪上加霜。" % base["name"]]
        info, _ = player.add_disease(disease_id, hp_scale=hp_scale,
                                     temp_scale=temp_scale)
        if not info:
            return ["幸好这次身体扛住了，没有真的病倒。"]
        return ["患上了%s（预计持续 %d 天，每日健康 -%.1f）"
                % (info["name"], info["days"], info["hp_per_day"])]
    return _apply


def _apply_disease_definite(disease_id, hp_scale=1.0, temp_scale=1.0, days_bonus=0):
    """
    生成一个"确定患病"的 func（不再判定概率）。
    用于生病机会已经判定通过的场景：此时角色确实已经不舒服，
    因此选择"硬扛/不治疗"就必然发展成真正的疾病。
    """
    base = DISEASES.get(disease_id) or DISEASES["cold"]

    def _apply(player):
        if player.has_disease(disease_id):
            return ["你身上的%s还没好，这次是雪上加霜。" % base["name"]]
        info, _ = player.add_disease(disease_id, hp_scale=hp_scale,
                                     temp_scale=temp_scale,
                                     days_bonus=days_bonus, force=True)
        if not info:
            return []
        return ["患上了%s（预计持续 %d 天，每日健康 -%.1f）"
                % (info["name"], info["days"], info["hp_per_day"])]
    return _apply


_ev("illness_cold", "着凉感冒", "疾病", 26,
    ["夜里窗户没关严，第二天起来嗓子发紧、喷嚏不断，一看就是感冒了。",
     "换季时节气温反复，你开始流鼻涕、头晕，典型的感冒症状。"],
    [_choice("花钱买药治好", "小额支出，基本立刻康复", "d10", [
        _out(1, 9, "药到病除，你很快就恢复了精神。", {"money": -80, "temp": 0.1, "cure": True}, "good"),
        _out(10, 10, "药没压住，还是病倒了。",
             {"money": -80, "func": _apply_disease_definite("cold", 0.8)}, "bad"),
    ]),
     _choice("多喝热水硬扛", "大部分能自愈，也可能真的病倒", "d6", [
        _out(1, 2, "硬扛了几天越来越重，炎症往下走了。",
             {"func": _apply_disease_definite("cold", 1.0)}, "bad",
             next_event="illness_cold_worse"),
        _out(3, 6, "睡了几觉，感冒自己好了。", {"happy": +1}, "good"),
    ])],
    tone="bad", tags=["disease"])

# 「感冒加重」为连锁事件：只能由「着凉感冒-硬扛失败」触发，不参与日常抽取
_ev("illness_cold_worse", "感冒加重", "疾病", 0,
    ["感冒没好利索，咳嗽越来越深，夜里开始发烧。"],
    [_choice("花钱去医院", "正规治疗，快速恢复", "d4", [
        _out(1, 4, "输液之后症状明显缓解。", {"money": -260, "happy": +2}, "good"),
    ]),
     _choice("继续硬扛", "可能发展成肺炎", "d6", [
        _out(1, 2, "病情失控，发展成了肺炎！", {"func": _apply_disease_factory("pneumonia", 1.0, 1.0)}, "bad"),
        _out(3, 6, "终于靠着休息扛过去了。", {"health": -4}, "neutral"),
    ])],
    tone="bad", tags=["disease"], internal=True)

_ev("illness_gastro", "吃坏肚子", "疾病", 22,
    ["路边摊的宵夜格外香，半夜你的肚子开始翻江倒海。",
     "一顿火锅配冰啤，第二天早上你抱着马桶站不起来。"],
    [_choice("买药调理", "花小钱稳妥解决", "d10", [
        _out(1, 9, "吃了药，肠胃很快平静下来。", {"money": -120, "cure": True, "health": +2}, "good"),
        _out(10, 10, "药吃晚了，还是拉了两天。",
             {"money": -120, "func": _apply_disease_definite("gastro", 0.8)}, "bad"),
    ]),
     _choice("饿两天挺过去", "省钱但风险高", "d6", [
        _out(1, 2, "越拖越严重，落下了肠胃炎。", {"func": _apply_disease_definite("gastro", 1.0)}, "bad"),
        _out(3, 6, "清汤寡水两天，居然好了。", {"health": -2, "happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["disease"])

_ev("illness_pneumonia", "高烧不退", "疾病", 10,
    ["连续几天高烧不退，咳嗽时胸口像被撕开一样疼。",
     "半夜咳醒，呼吸都带着杂音，家人催你赶紧去医院。"],
    [_choice("住院治疗", "费用高昂但救命", "d4", [
        _out(1, 4, "住院一周后，病情终于控制住了。", {"money": -2000, "happy": +5, "health": -3, "cure": True}, "good"),
    ]),
     _choice("吃退烧药硬撑", "极度危险", "d6", [
        _out(1, 3, "病情急剧恶化，你被送进了急诊室。",
             {"func": _apply_disease_definite("pneumonia", 1.3)}, "bad"),
        _out(4, 6, "烧退了，但身体虚得厉害。", {"health": -10, "happy": -6}, "neutral"),
    ])],
    tone="bad", tags=["disease"], cond=lambda p: p.age >= 5)

_ev("illness_chronic", "查出慢性病", "疾病", 9,
    ["体检报告上出现了一个不太友好的名词，医生建议长期服药控制。",
     "最近总是乏力、失眠，检查后发现是慢性疾病在作祟。"],
    [_choice("遵医嘱长期治疗", "花钱买健康", "d4", [
        _out(1, 4, "按时吃药复查，指标慢慢稳定了。", {"money": -1500, "happy": -2, "health": +2}, "neutral"),
    ]),
     _choice("先不管它", "省下钱，但身体会持续受损", "d6", [
        _out(1, 4, "慢性病就这么拖了下来，身体一天不如一天。",
             {"func": _apply_disease_definite("chronic")}, "bad"),
        _out(5, 6, "你调整作息、锻炼身体，竟没留下病根。", {"happy": +3, "health": -2}, "good"),
    ])],
    tone="bad", tags=["disease"], cond=lambda p: p.age >= 30)

_ev("illness_seasonal", "流感季节", "疾病", 18,
    ["季节交替，办公室一半人都在咳嗽，你也开始觉得发冷。",
     "新闻里说最近流感高发，你恰好在这个节骨眼上不舒服了。"],
    [_choice("打疫苗 + 休息", "小投入大回报", "d6", [
        _out(1, 5, "你成功躲过了这波流感。", {"money": -200, "happy": +2}, "good"),
        _out(6, 6, "疫苗也没挡住，还是中招了。",
             {"func": _apply_disease_definite("cold", 0.8)}, "bad"),
    ]),
     _choice("照常生活", "碰运气", "d6", [
        _out(1, 3, "你病倒了，发烧三天。", {"func": _apply_disease_definite("cold", 1.1)}, "bad"),
        _out(4, 6, "你的免疫力意外地强，毫发无伤。", {"happy": +1}, "good"),
    ])],
    tone="bad", tags=["disease"])

_ev("illness_frostbite", "冻伤", "疾病", 12,
    ["在室外待得太久，手脚先麻后疼，指尖泛起青紫色。",
     "寒风像刀子一样刮在脸上，回屋后你的耳朵和手指失去了知觉。"],
    [_choice("立刻就医处理", "快速止损", "d4", [
        _out(1, 4, "医生处理及时，只是轻微冻伤。", {"money": -260, "temp": +0.2, "cure": True}, "good"),
    ]),
     _choice("用雪搓一搓", "民间偏方，风险很大", "d6", [
        _out(1, 3, "偏方没用，冻伤加重了。", {"func": _apply_disease_definite("frostbite", 1.2)}, "bad"),
        _out(4, 6, "不知是运气还是偏方有效，居然缓过来了。", {"health": -4}, "neutral"),
    ])],
    tone="bad", tags=["disease"],
    cond=lambda p: get_city(p.city)["tag"] == "寒冷" or p.ambient_temp <= 0)

_ev("illness_heatstroke", "中暑", "疾病", 12,
    ["太阳晒得柏油路都在冒热气，你突然一阵天旋地转。",
     "高温下你出了太多汗，喝水的速度完全跟不上流失。"],
    [_choice("马上降温补水", "及时处理", "d4", [
        _out(1, 4, "在阴凉处缓了一会儿，只是轻微中暑。", {"money": -80, "temp": -0.2, "cure": True}, "good"),
    ]),
     _choice("咬牙继续干活", "硬扛高温", "d6", [
        _out(1, 3, "你眼前一黑，被送去了医院。",
             {"func": _apply_disease_definite("heatstroke", 1.2)}, "bad"),
        _out(4, 6, "靠着意志力撑了过去。", {"health": -5, "happy": -3}, "neutral"),
    ])],
    tone="bad", tags=["disease"],
    cond=lambda p: get_city(p.city)["tag"] == "炎热" or p.ambient_temp >= 30)


# ------------------------------------------------------------------------------
# 8.2 工作事业类事件
# ------------------------------------------------------------------------------

def _func_join_work(level=1, happiness=3):
    def _apply(player):
        if player.employed:
            return []
        player.employed = True
        player.job_level = max(1, level)
        return ["你正式入职，开始了打工人生涯（职级 %d）。" % player.job_level]
    return _apply


def _func_promote(level=1):
    def _apply(player):
        if not player.employed:
            return []
        player.job_level = min(10, player.job_level + level)
        return ["职级提升到 %d 级。" % player.job_level]
    return _apply


def _func_fire(reason="被裁员"):
    def _apply(player):
        if not player.employed:
            return []
        player.employed = False
        player.job_level = 0
        return ["你失去了工作。"]
    return _apply


_ev("work_gain_job", "找到工作", "工作", 16,
    ["你投出的简历终于有了回音，HR 约你下周一入职。",
     "几轮面试之后，你拿到了一份还算满意的 offer。"],
    [_choice("接受这份工作", "开始稳定收入", "d6", [
        _out(1, 4, "你顺利入职，工资按职级发放。", {"happy": +6, "func": _func_join_work(1)}, "good"),
        _out(5, 6, "入职第一天就发现团队氛围极好，你干劲十足。", {"happy": +10, "func": _func_join_work(2)}, "good"),
    ]),
     _choice("再等等更好的机会", "空窗期继续", "d6", [
        _out(1, 3, "更好的机会没来，你还得继续找。", {"happy": -3}, "bad"),
        _out(4, 6, "三天后你等到了一个待遇更好的岗位。", {"happy": +8, "func": _func_join_work(2)}, "good"),
    ])],
    tone="good", tags=["work"], cond=lambda p: (not p.employed) and p.age >= 18)

_ev("work_hard_work", "工作任务", "工作", 20,
    ["主管把一个棘手的项目丢给了你，说「年轻人多锻炼」。",
     "季度考核临近，桌面上堆着做不完的报表。"],
    [_choice("加班加点完成", "健康换钱", "d10", [
        _out(1, 3, "你熬了通宵，成果不错，但身体透支了。", {"money": +600, "health": -6, "happy": -4}, "neutral"),
        _out(4, 8, "项目顺利完成，拿到了绩效奖金。", {"money": +1000, "happy": +3, "health": -3}, "good"),
        _out(9, 10, "你的方案被高层看中，全组通报表扬。", {"money": +1800, "happy": +10, "func": _func_promote(1)}, "good"),
    ]),
     _choice("按部就班不加班", "保住生活节奏", "d6", [
        _out(1, 3, "进度落后，被主管约谈了一顿。", {"happy": -6}, "bad"),
        _out(4, 6, "你按时交付，虽然不出彩，但也没出错。", {"money": +300}, "neutral"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: p.employed)

_ev("work_promotion", "升职机会", "工作", 12,
    ["部门要提拔一名骨干，名单里出现了你的名字。",
     "领导找你谈话，暗示有一个晋升名额正在考虑你。"],
    [_choice("主动争取", "表现欲拉满", "d20", [
        _out(1, 4, "你用力过猛，反而让领导觉得你浮躁。", {"happy": -8}, "bad"),
        _out(5, 15, "你的积极态度被认可，顺利升职。", {"money": +1200, "happy": +10, "func": _func_promote(1)}, "good"),
        _out(16, 20, "你在关键汇报中大放异彩，连升两级！", {"money": +2400, "happy": +16, "func": _func_promote(2)}, "good"),
    ]),
     _choice("谦虚观望", "稳中求进", "d6", [
        _out(1, 3, "机会给了别人，你只能看着。", {"happy": -5}, "bad"),
        _out(4, 6, "领导觉得你沉稳可靠，下次优先考虑你。", {"happy": +4}, "neutral"),
    ])],
    tone="good", tags=["work"], cond=lambda p: p.employed and p.job_level >= 1)

_ev("work_unemployed", "裁员风波", "工作", 12,
    ["公司业绩下滑，会议室里传出裁员的消息。",
     "HR 把你叫进小房间，桌上放着一份赔偿协议。"],
    [_choice("争取赔偿后离开", "体面收场", "d6", [
        _out(1, 3, "赔偿谈得很难看，只拿到一半。", {"money": +1500, "happy": -10, "func": _func_fire()}, "bad"),
        _out(4, 6, "你拿到了 N+1 赔偿，平静地离开了。", {"money": +4000, "happy": -4, "func": _func_fire()}, "neutral"),
    ]),
     _choice("接受降薪留下", "保住饭碗", "d6", [
        _out(1, 3, "留下后你被边缘化，处处受限。", {"happy": -12, "money": -200}, "bad"),
        _out(4, 6, "公司熬过了寒冬，你也保住了职位。", {"happy": -2, "money": -500}, "neutral"),
    ])],
    tone="bad", tags=["work"], cond=lambda p: p.employed)

_ev("work_side_job", "副业机会", "工作", 14,
    ["朋友介绍你一个周末做外包的活儿，报酬不错。",
     "你在网上看到有人靠副业月入过万，心动了。"],
    [_choice("接下来做", "牺牲休息换钱", "d10", [
        _out(1, 3, "活儿比想象中麻烦，客户还拖欠尾款。", {"money": +200, "happy": -5, "health": -3}, "bad"),
        _out(4, 9, "副业收入稳定进账。", {"money": +1400, "health": -3, "happy": +2}, "good"),
        _out(10, 10, "副业意外爆单，收入超过主业。", {"money": +3600, "happy": +8, "health": -4}, "good"),
    ]),
     _choice("专心主业", "保持生活质量", "d6", [
        _out(1, 6, "你把时间用在了休息和学习上。", {"happy": +4, "health": +2}, "good"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: p.employed and p.age >= 18)

_ev("work_conflict", "职场矛盾", "工作", 12,
    ["同事把你做的方案署上了自己的名字，你气得手抖。",
     "跨部门沟通时对方当众否定你，会议室气氛瞬间凝固。"],
    [_choice("当场据理力争", "正面刚", "d20", [
        _out(1, 6, "你情绪失控，反而被扣上「不好合作」的标签。", {"happy": -12}, "bad"),
        _out(7, 18, "你拿出了证据，赢得了同事的尊重。", {"happy": +8}, "good"),
        _out(19, 20, "你的表现被大领导看到，获得了额外赏识。", {"happy": +12, "money": +800, "func": _func_promote(1)}, "good"),
    ]),
     _choice("私下沟通化解", "以柔克刚", "d10", [
        _out(1, 3, "对方不吃这套，矛盾反而加深了。", {"happy": -8}, "bad"),
        _out(4, 10, "你们把话说开了，之后配合顺畅很多。", {"happy": +5}, "good"),
    ])],
    tone="bad", tags=["work"], cond=lambda p: p.employed)

_ev("work_salary_up", "加薪谈判", "工作", 12,
    ["你所在岗位的市场价涨了不少，你决定找领导谈加薪。",
     "年底调薪窗口开启，你准备了一份业绩清单。"],
    [_choice("开门见山提数字", "强硬姿态", "d20", [
        _out(1, 5, "领导觉得你太急功近利，谈判失败。", {"happy": -8}, "bad"),
        _out(6, 17, "你的业绩有说服力，加薪成功。", {"money": +1500, "happy": +8}, "good"),
        _out(18, 20, "领导不仅加了薪，还给你配了团队。", {"money": +2500, "happy": +12, "func": _func_promote(1)}, "good"),
    ]),
     _choice("聊聊职业发展", "迂回策略", "d10", [
        _out(1, 3, "领导画了一堆大饼，什么都没落地。", {"happy": -5}, "bad"),
        _out(4, 10, "虽然没有立刻加薪，但获得了培训机会。", {"happy": +3, "money": +300}, "neutral"),
    ])],
    tone="good", tags=["work"], cond=lambda p: p.employed and p.job_level >= 1)

_ev("work_startup", "创业邀请", "工作", 8,
    ["老同学拉你合伙创业，说「这次风口是真的」。",
     "一个投资人看上了你的想法，愿意投一笔启动资金。"],
    [_choice("押上积蓄全力以赴", "高风险高回报", "d20", [
        _out(1, 8, "项目半年就黄了，钱打了水漂。", {"money": -6000, "happy": -18}, "bad"),
        _out(9, 17, "业务慢慢跑起来了，开始有稳定分红。", {"money": +3000, "happy": +10, "func": _func_promote(1)}, "good"),
        _out(18, 20, "你踩中了风口，收入翻了好几倍！", {"money": +20000, "happy": +20}, "good"),
    ]),
     _choice("婉拒，稳住工作", "不冒风险", "d6", [
        _out(1, 6, "后来那家公司真的上市了，你只能感慨。", {"happy": -4}, "neutral"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: p.age >= 22 and p.money >= 3000)

_ev("work_overtime_sick", "过度加班", "工作", 10,
    ["连续两周每天工作到凌晨，你的身体开始报警。",
     "项目冲刺期，你在工位上连续坐了十二个小时。"],
    [_choice("请病假休息", "少赚点钱", "d6", [
        _out(1, 3, "主管不太高兴，扣了全勤。", {"money": -400, "health": +4, "happy": +2}, "neutral"),
        _out(4, 6, "好好睡了两天，身体恢复了不少。", {"health": +6, "happy": +5}, "good"),
    ]),
     _choice("咬牙继续扛", "健康换绩效", "d10", [
        _out(1, 3, "你的身体彻底撑不住，晕倒在工位上。", {"health": -14, "happy": -10, "money": -800}, "bad"),
        _out(4, 8, "项目按时上线，奖金到手。", {"money": +1600, "health": -6}, "neutral"),
        _out(9, 10, "你成了团队里公认的铁人。", {"money": +2200, "health": -4, "happy": +4, "func": _func_promote(1)}, "good"),
    ])],
    tone="bad", tags=["work"], cond=lambda p: p.employed)


# ------------------------------------------------------------------------------
# 8.2b 成长与家庭类事件（覆盖童年 / 求学 / 中年人生阶段）
# ------------------------------------------------------------------------------

_ev("grow_baby", "咿呀学语", "情感", 18,
    ["你含糊地发出了第一个像样的音节，全家欢呼。",
     "你扶着桌沿摇摇晃晃地站了起来，迈出了第一步。"],
    [_choice("扑进父母怀里", "被爱包围的童年", "d6", [
        _out(1, 4, "家里给你办了小小的庆祝，你笑得停不下来。", {"happy": +6}, "good"),
        _out(5, 6, "父母把这一刻录成了视频，珍藏了很多年。", {"happy": +8, "health": +2}, "good"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: p.age <= 3)

_ev("grow_school", "开学第一天", "情感", 16,
    ["你背上新书包，站在陌生的教室门口有点紧张。",
     "老师点名时你举手的动作慢了半拍，全班都笑了。"],
    [_choice("努力当个好学生", "从小自律", "d10", [
        _out(1, 4, "功课有点跟不上，你被留下来补作业。", {"happy": -4}, "bad"),
        _out(5, 9, "你很快交到了好朋友，成绩也不错。", {"happy": +8, "money": -200}, "good"),
        _out(10, 10, "你第一次考试就拿了满分，被老师当众表扬。", {"happy": +12, "money": -200}, "good"),
    ]),
     _choice("只想玩", "快乐教育", "d6", [
        _out(1, 3, "家长被请去学校谈话，你被训了一顿。", {"happy": -6}, "bad"),
        _out(4, 6, "你在操场上度过了最快乐的时光。", {"happy": +7, "health": +2}, "good"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 5 <= p.age <= 9)

_ev("grow_exam", "重要考试", "工作", 14,
    ["这场考试的成绩，可能会决定你未来几年的去向。",
     "考场外站满了陪考的家长，你深吸了一口气走进教室。"],
    [_choice("全力备考", "拼一把", "d20", [
        _out(1, 6, "压力太大，考场上脑子一片空白。", {"happy": -12, "health": -4}, "bad"),
        _out(7, 17, "成绩出来，你考上了理想的学校。", {"happy": +16, "money": -800}, "good"),
        _out(18, 20, "你成了当年的状元，亲友纷纷来道贺。", {"happy": +24, "money": +2000}, "good"),
    ]),
     _choice("尽力就好", "不给自己压力", "d10", [
        _out(1, 5, "成绩平平，你多少有点遗憾。", {"happy": -4}, "neutral"),
        _out(6, 10, "结果比预想中好，你挺满意。", {"happy": +6}, "good"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: p.age in (15, 18, 22))

_ev("grow_bully", "校园摩擦", "情感", 12,
    ["有人故意把你的作业本扔到了地上。",
     "放学路上，几个高个子堵住了你的去路。"],
    [_choice("告诉老师家长", "寻求帮助", "d6", [
        _out(1, 3, "事情被压下去了，但对方变本加厉。", {"happy": -10}, "bad"),
        _out(4, 6, "老师严肃处理，再没人敢欺负你。", {"happy": +8}, "good"),
    ]),
     _choice("自己解决", "硬碰硬", "d10", [
        _out(1, 4, "你吃了亏，脸上挂了彩。", {"health": -6, "happy": -8}, "bad"),
        _out(5, 10, "你据理力争，对方反倒退了。", {"happy": +4, "health": -2}, "neutral"),
    ])],
    tone="bad", tags=["growth"], cond=lambda p: 8 <= p.age <= 18)

_ev("grow_parents", "父母生病", "情感", 12,
    ["电话那头母亲的声音很虚弱，说只是小毛病。",
     "父亲住院了，检查单上写着你不太懂的术语。"],
    [_choice("承担医药费并陪护", "尽孝", "d6", [
        _out(1, 3, "治疗费用高昂，你几乎花光了积蓄。", {"money": -8000, "happy": -6, "health": -4}, "neutral"),
        _out(4, 6, "父母康复了，你心里踏实了许多。", {"money": -4000, "happy": +8}, "good"),
    ]),
     _choice("先忙完工作再说", "现实的压力", "d10", [
        _out(1, 5, "你赶到时已经晚了，心里留下永远的遗憾。", {"happy": -22}, "bad"),
        _out(6, 10, "家人理解你的难处，病情也没恶化。", {"happy": -6}, "neutral"),
    ])],
    tone="bad", tags=["family"], cond=lambda p: p.age >= 25)

_ev("grow_midlife", "中年危机", "工作", 12,
    ["你突然发现自己成了公司里年纪最大的那批人。",
     "体检报告、房贷账单和孩子的学费同时摆在桌上。"],
    [_choice("转型学习新技能", "投资自己", "d20", [
        _out(1, 8, "学了半年没派上用场，还花了钱。", {"money": -3000, "happy": -8}, "bad"),
        _out(9, 17, "新技能让你在职场重新有了竞争力。", {"money": +4000, "happy": +12, "func": _func_promote(1)}, "good"),
        _out(18, 20, "你抓住行业风口，收入翻了倍。", {"money": +15000, "happy": +18}, "good"),
    ]),
     _choice("稳住现状", "不折腾", "d10", [
        _out(1, 5, "行业变化太快，你越来越吃力。", {"happy": -10, "money": -1000}, "bad"),
        _out(6, 10, "虽然没突破，但日子过得安稳。", {"happy": +2}, "neutral"),
    ])],
    tone="neutral", tags=["work"], cond=lambda p: 38 <= p.age <= 58)

_ev("grow_retire", "退休生活", "情感", 14,
    ["你办完了退休手续，工牌被收回的那一刻有些不真实。",
     "早上不用再定闹钟，你反而醒得更早了。"],
    [_choice("培养爱好，享受生活", "辛苦半生，值得", "d6", [
        _out(1, 3, "你把时间都花在了钓鱼和书法上。", {"happy": +14, "money": -1000, "health": +4}, "good"),
        _out(4, 6, "你加入了社区合唱团，认识了很多新朋友。", {"happy": +18, "health": +6, "money": -500}, "good"),
    ]),
     _choice("返聘继续赚钱", "闲不下来", "d10", [
        _out(1, 4, "身体吃不消，你很快又辞了。", {"health": -8, "money": +3000}, "neutral"),
        _out(5, 10, "返聘收入不错，你干得挺起劲。", {"money": +8000, "health": -4, "happy": +4}, "good"),
    ])],
    tone="good", tags=["family"], cond=lambda p: p.age >= 60)

_ev("grow_memory", "回忆往事", "情感", 12,
    ["翻看旧相册，你发现很多人已经很久没见了。",
     "老同学群里传来一条消息，说有人已经离开了。"],
    [_choice("联系老朋友", "珍惜眼前人", "d6", [
        _out(1, 6, "你们聊了很久，仿佛回到年少时。", {"happy": +10}, "good"),
    ]),
     _choice("把感慨留在心里", "独自消化", "d4", [
        _out(1, 4, "你泡了杯茶，安静地坐了一下午。", {"happy": +3}, "neutral"),
    ])],
    tone="neutral", tags=["social"], cond=lambda p: p.age >= 45)


# ------------------------------------------------------------------------------
# 8.2c 婴幼儿 / 童年专属事件（0~12 岁：不会说话、不能独自出门、食物有限）
# ------------------------------------------------------------------------------

_ev("baby_feed", "喝奶与辅食", "情感", 26,
    ["你还不会说话，饿了只能用哭声表达。妈妈试着换了两种奶粉。",
     "大人把米糊调得稀稀的，一勺一勺喂进你嘴里。"],
    [_choice("乖乖喝完", "吃饱就睡，最幸福的年纪", "d6", [
        _out(1, 4, "你一口气喝完了，打了个小小的嗝。", {"health": +1, "happy": +4}, "good"),
        _out(5, 6, "你喝得满脸都是，逗得全家大笑。", {"health": +2, "happy": +7}, "good"),
    ]),
     _choice("扭头不肯吃", "挑食的小脾气", "d6", [
        _out(1, 3, "你哭闹了半天，最后只喝了半瓶。", {"happy": -2, "health": -1}, "bad"),
        _out(4, 6, "换成另一种口味后你终于肯吃了。", {"happy": +3, "money": -80}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: p.age <= 2)

_ev("baby_sleep", "哭闹的夜晚", "情感", 24,
    ["半夜你又哭醒了，父母轮流抱着你在屋里走来走去。",
     "你被噩梦惊醒，怎么哄都不肯睡。"],
    [_choice("被抱着哄睡", "有安全感的孩子", "d6", [
        _out(1, 4, "你在妈妈的怀里很快又睡着了。", {"health": +1, "happy": +5}, "good"),
        _out(5, 6, "大人一夜没睡，第二天顶着黑眼圈上班。", {"happy": +3}, "neutral"),
    ]),
     _choice("自己哭到累", "大人实在太困了", "d6", [
        _out(1, 3, "你哭到嗓子哑了，全家都没休息好。", {"health": -2, "happy": -3}, "bad"),
        _out(4, 6, "哭累了之后你自己睡着了。", {"happy": -1}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: p.age <= 3)

_ev("baby_sick_care", "发烧的婴儿", "疾病", 16,
    ["你半夜烧到 38.6℃，还不会说话的只能一直哼哼。",
     "大人摸你的额头觉得烫手，赶紧翻出体温计。"],
    [_choice("连夜去医院", "婴儿病情不能拖", "d6", [
        _out(1, 6, "医生说是普通感染，开了药，第二天就退烧了。", {"money": -400, "health": -1, "happy": +3}, "good"),
    ]),
     _choice("物理降温观察", "先试试看", "d10", [
        _out(1, 4, "烧一直退不下来，最后还是去了医院。", {"money": -600, "health": -4, "happy": -3}, "bad"),
        _out(5, 10, "温水擦身之后体温慢慢降了下来。", {"health": -1}, "neutral"),
    ])],
    tone="bad", tags=["disease", "growth"], cond=lambda p: p.age <= 4)

_ev("baby_first_word", "第一次说话", "情感", 22,
    ["你清晰地喊出了人生第一个词，全家人愣了两秒后笑作一团。",
     "你指着窗外，含含糊糊地说出了一个像样的音节。"],
    [_choice("继续学新词", "语言爆发期", "d6", [
        _out(1, 4, "你很快学会了「爸爸」「妈妈」，家里天天充满笑声。", {"happy": +9}, "good"),
        _out(5, 6, "你学会的词越来越多，还会学大人说话的语气。", {"happy": +12, "health": +1}, "good"),
    ]),
     _choice("只顾着玩", "说话的事不着急", "d4", [
        _out(1, 4, "你还是更喜欢用哭声和手指表达。", {"happy": +2}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 1 <= p.age <= 4)

_ev("baby_crawl", "学步", "情感", 20,
    ["你扶着沙发摇摇晃晃地站起来，朝玩具的方向挪了两步。",
     "你扶着墙一点点往前挪，膝盖一软又坐到了地上。"],
    [_choice("继续练", "摔了也不哭", "d6", [
        _out(1, 3, "你摔了好几次，膝盖蹭破了点皮。", {"health": -1, "happy": +4}, "neutral"),
        _out(4, 6, "你终于能自己走几步了，全家鼓掌。", {"health": +2, "happy": +10}, "good"),
    ]),
     _choice("抱着不撒手", "大人怕你摔", "d6", [
        _out(1, 6, "你被抱在怀里，安安静静地看着别人跑跳。", {"happy": +2}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 1 <= p.age <= 3)

_ev("baby_kindergarten", "幼儿园第一天", "情感", 18,
    ["你被送进幼儿园，转身发现妈妈已经走了，眼泪一下子涌出来。",
     "小朋友们在玩积木，你抱着自己的小书包站在门口不敢进去。"],
    [_choice("试着融入大家", "迈出社交第一步", "d6", [
        _out(1, 3, "你想妈妈想了半天，午睡时偷偷哭了。", {"happy": -4}, "bad"),
        _out(4, 6, "老师牵着你一起搭积木，你很快交到了第一个朋友。", {"happy": +10}, "good"),
    ]),
     _choice("不想上幼儿园", "抱着门框不撒手", "d6", [
        _out(1, 6, "大人在门口哄了你半个小时。", {"happy": -2}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 3 <= p.age <= 6)

_ev("child_chore", "被安排做家务", "情感", 14,
    ["父母让你把自己的玩具收好，说「自己的事情自己做」。",
     "家里大扫除，你被分配了擦桌子的活儿。"],
    [_choice("认真做完", "从小养成习惯", "d6", [
        _out(1, 4, "你把桌子擦得干干净净，得到了表扬。", {"happy": +6}, "good"),
        _out(5, 6, "你还顺便整理了书架，妈妈奖励了你零花钱。", {"happy": +8, "money": +50}, "good"),
    ]),
     _choice("偷懒溜走", "去看动画片", "d6", [
        _out(1, 3, "你被抓了回来，还被没收了遥控器。", {"happy": -6}, "bad"),
        _out(4, 6, "你成功溜掉了，看得正开心。", {"happy": +3}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 4 <= p.age <= 12)

_ev("child_pocket_money", "零花钱", "情感", 16,
    ["过年收到的红包被妈妈「帮忙保管」了，你手里只剩下一点零钱。",
     "你攒了两个月的零花钱，正犹豫要买什么。"],
    [_choice("买心心念念的玩具", "童年的快乐", "d6", [
        _out(1, 4, "你把玩具抱回家，玩了整整一个下午。", {"money": -100, "happy": +9}, "good"),
        _out(5, 6, "玩具比想象中好玩，你还和同学交换着玩。", {"money": -100, "happy": +12}, "good"),
    ]),
     _choice("存起来", "小小理财家", "d6", [
        _out(1, 6, "你把钱塞进了储蓄罐，看着数字变多很有成就感。", {"happy": +4}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 5 <= p.age <= 14)

_ev("child_food_limit", "挑食", "情感", 16,
    ["餐桌上是你不爱吃的青菜，你把碗推开了一点。",
     "家里条件有限，今晚的菜色和昨天差不多。"],
    [_choice("乖乖吃完", "不挑食长得高", "d6", [
        _out(1, 4, "你把青菜吃完了，妈妈给你盛了第二碗饭。", {"health": +2, "happy": +3}, "good"),
        _out(5, 6, "你渐渐习惯了这种味道，身体也结实了些。", {"health": +3, "happy": +4}, "good"),
    ]),
     _choice("坚决不吃", "饿着也不碰", "d6", [
        _out(1, 3, "你饿了一顿，半夜爬起来找饼干。", {"health": -1, "happy": -3}, "bad"),
        _out(4, 6, "大人无奈，给你煮了个鸡蛋。", {"happy": +2}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 2 <= p.age <= 12)

_ev("child_homework", "写不完的作业", "工作", 18,
    ["明天要交的作业还剩一大半，你的铅笔却越写越慢。",
     "老师布置的卷子摊在桌上，窗外传来小伙伴的笑声。"],
    [_choice("先写完再玩", "自律的孩子", "d10", [
        _out(1, 4, "你写到很晚，眼皮一直在打架。", {"health": -2, "happy": -2}, "neutral"),
        _out(5, 9, "你把作业写完才出门，玩得特别踏实。", {"happy": +6}, "good"),
        _out(10, 10, "作业全对，老师在班上念了你的名字。", {"happy": +10}, "good"),
    ]),
     _choice("先出去玩", "明天再说", "d10", [
        _out(1, 5, "你玩到天黑，回家被批评了一顿，作业写到半夜。", {"happy": -6, "health": -1}, "bad"),
        _out(6, 10, "你玩得开心，作业赶在睡前写完了。", {"happy": +5}, "neutral"),
    ])],
    tone="neutral", tags=["growth"], cond=lambda p: 6 <= p.age <= 15)

_ev("child_parent_trip", "全家出游", "情感", 12,
    ["父母带你去了动物园，你第一次见到真的长颈鹿。",
     "一家人坐了很远的车去海边，你的鞋里全是沙子。"],
    [_choice("尽情玩耍", "童年最好的回忆", "d6", [
        _out(1, 4, "你玩到太阳落山，回家路上在车上睡着了。", {"money": -500, "happy": +12}, "good"),
        _out(5, 6, "你拍了很多照片，多年后还会翻出来看。", {"money": -500, "happy": +16}, "good"),
    ]),
     _choice("嫌累不想走", "闹起了脾气", "d6", [
        _out(1, 3, "你在景区门口哭闹，全家行程被打乱。", {"money": -300, "happy": -4}, "bad"),
        _out(4, 6, "吃了冰淇淋之后你又开心起来了。", {"money": -400, "happy": +6}, "neutral"),
    ])],
    tone="good", tags=["growth"], cond=lambda p: 3 <= p.age <= 14)


# ------------------------------------------------------------------------------
# 8.2d 平凡的一天（无事发生）：占比最高，让日子不总是跌宕起伏
# ------------------------------------------------------------------------------

_ev("plain_day_1", "平凡的一天", "日常", 40,
    ["今天和往常没什么两样：起床、吃饭、做事、睡觉。",
     "平淡的一天过去了，没有什么值得记录的事。"],
    [_choice("就这样过去", "风平浪静", "d6", [
        _out(1, 4, "一天平平淡淡地结束了。", {"happy": +1}, "neutral"),
        _out(5, 6, "你在路上看到一场很美的晚霞。", {"happy": +3}, "good"),
    ])],
    tone="neutral", tags=["plain"], cond=lambda p: True)

_ev("plain_day_2", "安静的日常", "日常", 34,
    ["今天没有意外，也没有惊喜，日子按部就班。",
     "你把该做的事都做完了，剩下的时间发了一会儿呆。"],
    [_choice("享受平静", "平淡是福", "d6", [
        _out(1, 4, "你在窗边坐了一会儿，心里很安静。", {"happy": +2}, "neutral"),
        _out(5, 6, "你顺手整理了房间，心情也清爽了。", {"happy": +4, "health": +1}, "good"),
    ])],
    tone="neutral", tags=["plain"], cond=lambda p: True)

_ev("plain_day_3", "重复的节奏", "日常", 30,
    ["闹钟、通勤、三餐、睡觉——今天几乎和昨天一模一样。",
     "一整天的安排都被填满，却又好像什么都没发生。"],
    [_choice("照常度过", "生活本来的样子", "d6", [
        _out(1, 3, "你在重复的节奏里感到一点疲惫。", {"happy": -1}, "neutral"),
        _out(4, 6, "习惯了之后，你反而觉得踏实。", {"happy": +2}, "good"),
    ])],
    tone="neutral", tags=["plain"], cond=lambda p: True)

_ev("plain_day_4", "小小的惬意", "日常", 26,
    ["你给自己泡了杯热茶，看着窗外发了会儿呆。",
     "今天天气不错，你把被子拿出去晒了晒。"],
    [_choice("慢慢过日子", "给自己一点温柔", "d6", [
        _out(1, 4, "你睡了个舒服的午觉。", {"health": +1, "happy": +3}, "good"),
        _out(5, 6, "你随手拍下一张照片，觉得这一天很好。", {"happy": +5}, "good"),
    ])],
    tone="good", tags=["plain"], cond=lambda p: True)



_ev("env_outdoor_child", "父母带出门", "环境", 700,
    ["父母推着婴儿车带你去公园，你在树荫下睡得特别香。",
     "爸妈带你去超市买菜，你坐在购物车里东张西望。"],
    [_choice_parent("开心出门", "有大人陪着才安全", "d6", [
        _out_parent(1, 4, "你晒了晒太阳，回家后睡得格外好。", {"health": +1, "happy": +6}, "good"),
        _out_parent(5, 6, "路上遇到了同龄的小朋友，你们玩到了一起。", {"happy": +9}, "good"),
    ]),
     _choice_parent("出门就哭", "只想待在家里", "d6", [
        _out_parent(1, 3, "你在公园哭了半小时，父母只好提前带你回家。", {"happy": -3}, "bad"),
        _out_parent(4, 6, "哄了一会儿你就安静下来了。", {"happy": +2}, "neutral"),
    ])],
    tone="good", tags=["outdoor", "growth"],
    cond=lambda p: p.age <= 6)

_ev("grow_family_trip", "全家远行", "情感", 600,
    ["一家人坐了很久的车去看海，你全程被抱着。",
     "父母带你回老家探亲，火车上你趴在窗边看了很久。"],
    [_choice_parent("跟着父母出远门", "幼年第一次远行", "d6", [
        _out_parent(1, 3, "路上你晕车吐了，闹了一路。", {"money": -300, "health": -2, "happy": +2}, "neutral"),
        _out_parent(4, 6, "你第一次见到海，兴奋得手舞足蹈。", {"money": -500, "happy": +14}, "good"),
    ]),
     _choice_parent("留在家里", "不出门更安稳", "d6", [
        _out_parent(1, 6, "你留在家里，由爷爷奶奶照看。", {"happy": +2}, "neutral"),
    ])],
    tone="good", tags=["outdoor", "commute", "growth"],
    cond=lambda p: p.age <= 6)

_ev("school_commute", "上学路上", "环境", 800,
    ["早晨的路口人来车往，你背着书包等红绿灯。",
     "放学时下起了雨，你站在校门口犹豫要不要冲出去。"],
    [_choice("和同学结伴走", "结伴更安全，也可能贪玩", "d6", [
        _out(1, 3, "你们一路打闹，回家晚了半小时。", {"happy": +3, "health": -1}, "neutral"),
        _out(4, 6, "你们安全到家，还顺路买了零食。", {"money": -20, "happy": +5}, "good"),
    ]),
     _choice("自己走快一点", "想早点回家", "d10", [
        _out(1, 3, "你跑得太急，在台阶上摔了一跤。", {"health": -4, "happy": -3}, "bad"),
        _out(4, 10, "你一路小跑，准时赶回了家。", {"happy": +1}, "neutral"),
    ])],
    tone="neutral", tags=["commute", "school"],
    cond=lambda p: 7 <= p.age <= 18)


# ------------------------------------------------------------------------------
# 8.3 情感社交类事件（婚恋、社交；婴幼儿不会说话、不能独自出门，故有严格年龄限制）
# ------------------------------------------------------------------------------

#: 伴侣姓名池（结婚时随机取名）
PARTNER_NAME_POOL = [
    "晓雯", "静怡", "雅琴", "思颖", "欣妍", "梦琪", "文博", "皓宇", "子墨", "浩然",
    "嘉俊", "志远", "雨桐", "舒然", "书瑶", "亦辰", "若岚", "明轩", "佳怡", "承泽",
]


def _func_marry():
    """结婚：登记婚姻状态、生成伴侣姓名与结婚日期（供生育系统使用）。"""
    def _apply(player):
        if player.married:
            return []
        player.married = True
        if not getattr(player, "partner_name", ""):
            try:
                idx = int(player.rng.random() * len(PARTNER_NAME_POOL))
                player.partner_name = PARTNER_NAME_POOL[idx % len(PARTNER_NAME_POOL)]
            except Exception:
                player.partner_name = "伴侣"
        player.married_date = player.date_full
        return ["你结婚了，伴侣是%s，从此有了一个家。" % player.partner_name]
    return _apply


def _func_child():
    def _apply(player):
        player.children += 1
        return ["家里迎来了第 %d 个孩子。" % player.children]
    return _apply


_ev("love_meet", "邂逅", "情感", 16,
    ["在朋友的聚会上，你遇到了一个让你心跳加速的人。",
     "地铁上有人帮你捡起掉落的书，抬头时你们对视了一秒。"],
    [_choice("主动要联系方式", "勇敢一点", "d20", [
        _out(1, 6, "你紧张得说错了话，对方礼貌地走开了。", {"happy": -5}, "bad"),
        _out(7, 17, "你们聊得很投机，约好了下次见面。", {"happy": +14}, "good"),
        _out(18, 20, "你遇见了灵魂伴侣，感情迅速升温。", {"happy": +22}, "good"),
    ]),
     _choice("把心动留在心里", "安全但平淡", "d6", [
        _out(1, 3, "你后悔了很久，总觉得错过了什么。", {"happy": -4}, "bad"),
        _out(4, 6, "你很快就把这件事忘了。", {}, "neutral"),
    ])],
    tone="good", tags=["love"], cond=lambda p: p.age >= 16)

_ev("love_fall", "恋爱", "情感", 14,
    ["你们开始频繁约会，街边的每一家店都留下了你们的影子。",
     "对方在深夜发来一条消息：「我们在一起吧。」"],
    [_choice("认真投入这段感情", "全心付出", "d10", [
        _out(1, 3, "你付出太多，反而让对方感到压力。", {"happy": -6, "money": -800}, "bad"),
        _out(4, 9, "恋爱让你整个人都亮了起来。", {"happy": +18, "money": -600}, "good"),
        _out(10, 10, "你们认定彼此就是那个人。", {"happy": +26, "money": -400}, "good"),
    ]),
     _choice("保持距离观察", "理性派", "d6", [
        _out(1, 3, "对方觉得你不够真诚，选择了离开。", {"happy": -8}, "bad"),
        _out(4, 6, "你们以朋友的身份继续相处。", {"happy": +3}, "neutral"),
    ])],
    tone="good", tags=["love"], cond=lambda p: p.age >= 16 and not p.married)

_ev("love_breakup", "分手", "情感", 10,
    ["争吵越来越多，你们终于坐在了咖啡馆里谈「结束」。",
     "对方的手机里出现了别人的名字，你选择了摊牌。"],
    [_choice("平静地放手", "及时止损", "d6", [
        _out(1, 3, "你还是难过了很久。", {"happy": -14}, "bad"),
        _out(4, 6, "分开之后你反而轻松了。", {"happy": -4}, "neutral"),
    ]),
     _choice("努力挽回", "再试一次", "d20", [
        _out(1, 10, "挽回失败，还消耗了最后的体面。", {"happy": -18, "money": -500}, "bad"),
        _out(11, 20, "你们重新开始，感情比以前更好。", {"happy": +10}, "good"),
    ])],
    tone="bad", tags=["love"], cond=lambda p: p.age >= 16 and not p.married)

_ev("love_marriage", "结婚", "情感", 12,
    ["双方父母见了面，婚期被提上了日程。",
     "你们决定领证，把这段关系变成一辈子的事。"],
    [_choice("办一场体面的婚礼", "花钱买仪式感", "d6", [
        _out(1, 3, "预算超支，为钱吵了一架。", {"money": -12000, "happy": +8}, "neutral"),
        _out(4, 6, "婚礼圆满，亲友都为你高兴。", {"money": -8000, "happy": +22, "func": _func_marry()}, "good"),
    ]),
     _choice("简单领证旅行结婚", "省钱实惠", "d6", [
        _out(1, 6, "两个人在海边拍了照，幸福很简单。", {"money": -2000, "happy": +16, "func": _func_marry()}, "good"),
    ])],
    tone="good", tags=["love"], cond=lambda p: p.age >= 22 and not p.married)

_ev("love_child", "迎接新生命", "情感", 12,
    ["检查报告显示：家里要多一个小成员了。",
     "产房外你来回踱步，直到听到那声响亮的啼哭。"],
    [_choice("迎接孩子的到来", "人生新阶段", "d10", [
        _out(1, 3, "养育的辛苦远超想象，你几乎没睡过整觉。", {"money": -6000, "happy": +10, "health": -4, "func": _func_child()}, "neutral"),
        _out(4, 10, "抱着孩子的那一刻，你觉得一切都值得。", {"money": -5000, "happy": +24, "func": _func_child()}, "good"),
    ])],
    tone="good", tags=["family"],
    cond=lambda p: p.married and 22 <= p.age <= 50 and p.children < 3)

_ev("love_friend_gather", "朋友聚会", "情感", 16,
    ["老同学组了个局，微信群里热闹了一整天。",
     "几个好朋友约你撸串，说好久没见了。"],
    [_choice("赴约叙旧", "花点钱换快乐", "d6", [
        _out(1, 3, "酒喝多了，第二天头疼欲裂。", {"money": -300, "happy": +6, "health": -3}, "neutral"),
        _out(4, 6, "聊到深夜，心里的郁结都散了。", {"money": -200, "happy": +12}, "good"),
    ]),
     _choice("在家休息", "省钱省力", "d4", [
        _out(1, 4, "你在家看了部老电影，也挺好。", {"happy": +3, "health": +1}, "good"),
    ])],
    tone="good", tags=["social"], cond=lambda p: p.age >= 6)

_ev("love_quarrel", "和亲近的人吵架", "情感", 12,
    ["一句话没说好，你和最亲近的人吵得面红耳赤。",
     "积压的情绪终于爆发，家里气氛降到了冰点。"],
    [_choice("主动道歉和解", "放下面子", "d6", [
        _out(1, 3, "对方还在气头上，道歉没被接受。", {"happy": -6}, "bad"),
        _out(4, 6, "你们抱在一起，把话说开了。", {"happy": +8}, "good"),
    ]),
     _choice("冷战到底", "谁也不低头", "d10", [
        _out(1, 5, "冷战持续了很久，关系出现裂痕。", {"happy": -14, "health": -3}, "bad"),
        _out(6, 10, "时间冲淡了怒气，日子照旧。", {"happy": -4}, "neutral"),
    ])],
    tone="bad", tags=["social"], cond=lambda p: p.age >= 6)

_ev("love_help_stranger", "帮助陌生人", "情感", 14,
    ["路口有位老人摔倒，围观的人都不敢上前。",
     "有人在地铁里急得直哭，说是钱包和证件全丢了。"],
    [_choice("伸出援手", "善意可能被辜负，也可能被回报", "d10", [
        _out(1, 3, "你被误会成肇事者，费了好大劲才说清。", {"happy": -10, "money": -300}, "bad"),
        _out(4, 9, "对方连声道谢，你心里暖暖的。", {"happy": +12}, "good"),
        _out(10, 10, "受助者恰是某公司高管，后来给了你一份大礼。", {"happy": +16, "money": +5000}, "good"),
    ]),
     _choice("拍视频报警后离开", "理性处理", "d6", [
        _out(1, 6, "警察及时赶到，事情妥善解决。", {"happy": +4}, "neutral"),
    ])],
    tone="good", tags=["social"], cond=lambda p: p.age >= 10)

_ev("love_gift", "送礼", "情感", 10,
    ["爸妈的生日快到了，你想买点像样的礼物。",
     "朋友帮了你一个大忙，你觉得该表示一下。"],
    [_choice("买份贵重礼物", "心意到位", "d6", [
        _out(1, 6, "对方收到礼物时眼睛都亮了。", {"money": -1200, "happy": +12}, "good"),
    ]),
     _choice("手写一封信", "用心不花钱", "d6", [
        _out(1, 3, "对方觉得你有点敷衍。", {"happy": -3}, "bad"),
        _out(4, 6, "朴实的话语让对方红了眼眶。", {"happy": +9}, "good"),
    ])],
    tone="good", tags=["social"], cond=lambda p: p.age >= 12)


# ------------------------------------------------------------------------------
# 8.4 环境气候类事件
# ------------------------------------------------------------------------------

_ev("env_cold_wave", "寒潮来袭", "环境", 18,
    ["气象台发布寒潮蓝色预警，气温一夜之间掉了十几度。",
     "寒风呼啸，路上的行人都缩着脖子快步走。"],
    [_choice("添置厚衣、开足暖气", "花钱保暖", "d6", [
        _out(1, 4, "穿得严严实实，寒潮对你影响不大。", {"money": -500, "temp": -0.1}, "good"),
        _out(5, 6, "暖气坏了，夜里还是冻得发抖。", {"money": -500, "temp": -0.6, "health": -2}, "neutral"),
    ]),
     _choice("硬扛过去", "省下开销，身体受罪", "d10", [
        _out(1, 4, "你在寒风里冻得嘴唇发紫。", {"temp": -1.2, "happy": -4}, "bad"),
        _out(5, 8, "多穿了两件旧衣服，勉强撑住。", {"temp": -0.5}, "neutral"),
        _out(9, 10, "你的抗寒能力出乎意料地强。", {"happy": +3}, "good"),
    ])],
    tone="bad", tags=["env"], cond=lambda p: p.ambient_temp <= 12 or get_city(p.city)["tag"] == "寒冷")

_ev("env_heat_wave", "高温预警", "环境", 18,
    ["连续三天最高气温超过 38℃，空调外机嗡嗡作响。",
     "柏油路被晒得发软，新闻里反复提醒减少外出。"],
    [_choice("开空调宅在家", "电费换舒适", "d6", [
        _out(1, 6, "屋里凉爽，你安稳地度过了热浪。", {"money": -400, "temp": +0.1}, "good"),
    ]),
     _choice("照常出门办事", "硬碰高温", "d10", [
        _out(1, 4, "你在烈日下头晕目眩。", {"temp": +1.1, "happy": -4}, "bad"),
        _out(5, 8, "你躲进商场蹭了空调，问题不大。", {"temp": +0.3}, "neutral"),
        _out(9, 10, "傍晚出门，居然赶上了难得的凉风。", {"happy": +3}, "good"),
    ])],
    tone="bad", tags=["env"], cond=lambda p: p.ambient_temp >= 24 or get_city(p.city)["tag"] == "炎热")

_ev("env_rain", "暴雨", "环境", 14,
    ["暴雨如注，路面很快积起了水。",
     "雨点砸在窗户上啪啪作响，出门成了难题。"],
    [_choice("打车通勤", "花钱买干爽", "d6", [
        _out(1, 3, "堵在路上两个小时，还是湿了鞋。", {"money": -200, "happy": -4}, "bad"),
        _out(4, 6, "顺利抵达，衣服一点没湿。", {"money": -150, "happy": +1}, "good"),
    ]),
     _choice("冒雨出行", "省钱但狼狈", "d10", [
        _out(1, 3, "你淋成了落汤鸡，第二天开始打喷嚏。", {"temp": -0.4, "happy": -4, "health": -2}, "bad"),
        _out(4, 10, "一把伞走天下，居然没怎么淋到。", {"happy": +1}, "neutral"),
    ])],
    tone="neutral", tags=["env"])

_ev("env_haze", "雾霾天", "环境", 12,
    ["窗外一片灰黄，能见度不足两百米。",
     "空气质量指数爆表，口罩成了出门必备。"],
    [_choice("买口罩和净化器", "保护呼吸道", "d6", [
        _out(1, 6, "呼吸顺畅，雾霾对你影响很小。", {"money": -600, "health": +1}, "good"),
    ]),
     _choice("将就一下", "省钱的代价", "d10", [
        _out(1, 4, "你咳了整整一周，喉咙发炎。", {"health": -5, "happy": -3}, "bad"),
        _out(5, 10, "只是嗓子有点干，没什么大碍。", {"health": -1}, "neutral"),
    ])],
    tone="bad", tags=["env"])

_ev("env_blizzard", "暴雪封路", "环境", 10,
    ["一夜暴雪，小区门口的车全被埋了。",
     "公交停运、航班取消，城市几乎停摆。"],
    [_choice("囤好物资在家办公", "稳妥应对", "d6", [
        _out(1, 6, "你提前囤了菜，安稳地过了两天。", {"money": -300, "happy": +2, "temp": -0.2}, "good"),
    ]),
     _choice("冒险出门", "危险系数高", "d10", [
        _out(1, 4, "你在雪地里滑倒，扭伤了脚踝。", {"health": -8, "happy": -6, "temp": -0.8}, "bad"),
        _out(5, 10, "你小心翼翼地走完了全程。", {"temp": -0.4, "happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["env"], cond=lambda p: get_city(p.city)["tag"] == "寒冷" or p.ambient_temp <= 0)

_ev("env_sandstorm", "沙尘暴", "环境", 10,
    ["天空变成土黄色，风里全是沙粒。",
     "沙尘暴过境，出门五分钟嘴里都是土。"],
    [_choice("关窗戴口罩", "防护到位", "d6", [
        _out(1, 6, "你安然度过了沙尘天。", {"money": -200, "health": -1}, "good"),
    ]),
     _choice("照常外出", "沙尘直冲口鼻", "d10", [
        _out(1, 4, "你的眼睛和喉咙都被刺激得通红。", {"health": -5, "happy": -4}, "bad"),
        _out(5, 10, "回来后洗了把脸就没事了。", {"health": -1}, "neutral"),
    ])],
    tone="bad", tags=["env"],
    cond=lambda p: p.city in ("harbin", "beijing") and p.month in (3, 4, 5))

_ev("env_heatstroke_risk", "闷热难耐", "环境", 8,
    ["梅雨天湿度接近饱和，走两步就一身汗。",
     "夜里闷热得睡不着，空调开了又怕感冒。"],
    [_choice("买个除湿机", "改善环境", "d4", [
        _out(1, 4, "屋里清爽多了，睡眠质量明显提升。", {"money": -900, "happy": +6, "health": +1}, "good"),
    ]),
     _choice("忍着", "省钱", "d6", [
        _out(1, 3, "你整夜没睡好，白天昏昏沉沉。", {"happy": -5, "health": -3}, "bad"),
        _out(4, 6, "身体慢慢适应了这种天气。", {}, "neutral"),
    ])],
    tone="neutral", tags=["env"], cond=lambda p: p.city in ("shanghai", "guangzhou"))


# ------------------------------------------------------------------------------
# 8.5 随机意外类事件
# ------------------------------------------------------------------------------

_ev("rand_lottery", "买彩票", "意外", 14,  # 成年人专属
    ["路过彩票店，你鬼使神差地买了两注。",
     "朋友凑钱合买刮刮乐，硬塞给你一张。"],
    [_choice("试试运气", "小赌怡情", "d100", [
        _out(1, 60, "什么都没中，彩票成了书签。", {"money": -50}, "neutral"),
        _out(61, 95, "中了个小奖，够吃顿好的。", {"money": +500, "happy": +8}, "good"),
        _out(96, 99, "中了大奖，你反复确认了三遍号码。", {"money": +20000, "happy": +25}, "good"),
        _out(100, 100, "【隐藏·天降横财】你中了大奖，金额高到需要去省城领奖。", {"money": +80000, "happy": +30}, "good"),
    ]),
     _choice("不参与", "踏实过日子", "d4", [
        _out(1, 4, "你觉得钱还是攥在手里最实在。", {"happy": +2}, "neutral"),
    ])],
    tone="neutral", tags=["random"], cond=lambda p: p.age >= 18)

_ev("rand_lose_money", "丢钱", "意外", 16,
    ["手机不见了，你翻遍了所有口袋。",
     "钱包被划开一道口子，现金全没了。"],
    [_choice("报警并挂失", "减少损失", "d6", [
        _out(1, 3, "追回来的希望渺茫，你只能自认倒霉。", {"money": -1500, "happy": -8}, "bad"),
        _out(4, 6, "警察很快找回了丢失的物品。", {"happy": +4}, "good"),
    ]),
     _choice("算了，破财免灾", "心态放平", "d6", [
        _out(1, 6, "你安慰自己：钱没了可以再赚。", {"money": -1200, "happy": -3}, "neutral"),
    ])],
    cond=lambda p: p.age >= 8, tone="bad", tags=["random"])

_ev("rand_injury", "意外受伤", "意外", 14,
    ["下楼梯时一脚踩空，脚踝传来剧痛。",
     "搬东西时腰闪了一下，直都直不起来。"],
    [_choice("立刻去医院", "规范治疗", "d6", [
        _out(1, 3, "医生说需要静养两周，医药费不便宜。", {"money": -1200, "health": -6, "happy": -4}, "neutral"),
        _out(4, 6, "只是软组织挫伤，包扎后就回家了。", {"money": -300, "health": -3}, "neutral"),
    ]),
     _choice("自己贴膏药", "能省则省", "d10", [
        _out(1, 4, "没处理好，落下了老毛病。", {"health": -10, "happy": -6}, "bad"),
        _out(5, 10, "休息几天就好了。", {"health": -4, "happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["random"])

_ev("rand_adventure", "奇遇", "意外", 10,
    ["你在旧书摊上淘到一本泛黄的手稿，里面写满了奇怪的符号。",
     "深夜加班回家，你在天桥上遇到一个自称会算命的老先生。"],
    [_choice("认真研究 / 听他说完", "可能改变人生", "d20", [
        _out(1, 7, "对方只是想骗点钱，你损失了一笔。", {"money": -600, "happy": -6}, "bad"),
        _out(8, 17, "你从中得到灵感，做出了一个不错的副业产品。", {"money": +3000, "happy": +10}, "good"),
        _out(18, 20, "手稿里夹着一张旧邮票，鉴定后价值不菲。", {"money": +30000, "happy": +18}, "good"),
    ]),
     _choice("一笑而过", "不理会", "d6", [
        _out(1, 6, "你继续过自己的日子。", {"happy": +1}, "neutral"),
    ])],
    cond=lambda p: p.age >= 16, tone="neutral", tags=["random"])

_ev("rand_gift", "意外之财", "意外", 10,
    ["大学同学突然转来一笔钱，说是当年借的。",
     "公司年会上你被抽中了一台新手机。"],
    [_choice("欣然接受", "好事成双", "d6", [
        _out(1, 6, "这笔意外收入让你心情大好。", {"money": +2000, "happy": +10}, "good"),
    ])],
    cond=lambda p: p.age >= 12, tone="good", tags=["random"])

_ev("rand_car_accident", "交通事故", "意外", 8,
    ["过马路时一辆电动车擦着你飞驰而过。",
     "前方车辆急刹，你差一点就撞了上去。"],
    [_choice("立刻检查伤情", "谨慎为上", "d6", [
        _out(1, 3, "你被撞倒在地，膝盖擦破了很大一片。", {"money": -800, "health": -8, "happy": -6}, "bad"),
        _out(4, 6, "只是虚惊一场，衣服蹭脏了。", {"happy": -4}, "neutral"),
    ]),
     _choice("自认倒霉继续走", "懒得纠缠", "d10", [
        _out(1, 4, "伤情比想象中严重，后来还是去了医院。", {"money": -1500, "health": -6}, "bad"),
        _out(5, 10, "确实没什么事，你快步离开了现场。", {"happy": -2}, "neutral"),
    ])],
    tone="bad", tags=["random"], cond=lambda p: p.age >= 6)

_ev("rand_found_money", "捡到钱包", "意外", 10,
    ["路边有个鼓鼓的钱包，四下无人。",
     "自动取款机吐出一张没人认领的钞票。"],
    [_choice("交给警察", "心安理得", "d6", [
        _out(1, 5, "失主赶来时对你千恩万谢。", {"happy": +12}, "good"),
        _out(6, 6, "失主是本地企业家，硬塞给你一笔谢礼。", {"money": +3000, "happy": +14}, "good"),
    ]),
     _choice("据为己有", "良心不安", "d10", [
        _out(1, 3, "钱包主人的朋友正好看到，你被当场抓住。", {"money": -2000, "happy": -18}, "bad"),
        _out(4, 10, "你把钱花了，但心里一直不舒服。", {"money": +1500, "happy": -6}, "neutral"),
    ])],
    cond=lambda p: p.age >= 8, tone="neutral", tags=["random"])


# ------------------------------------------------------------------------------
# 8.6 隐藏特殊事件（极端骰点触发）
# ------------------------------------------------------------------------------

_ev("secret_special_100", "天命所归", "隐藏", 0,
    ["骰子掷出满值 100——命运的齿轮发出清脆的响声。",
     "你从未想过，随手的善举会引来如此巨大的回响。"],
    [_choice("接受这份馈赠", "骰神站在你这边", "d20", [
        _out(1, 4, "一份神秘遗产落到你手里。", {"money": +50000, "happy": +20}, "good"),
        _out(5, 12, "你被贵人提携，事业一步登天。", {"money": +30000, "happy": +22, "func": _func_promote(2)}, "good"),
        _out(13, 20, "你的人生从此开挂：财富、健康、幸福全面爆发。", {"money": +88888, "health": +30, "happy": +30, "func": _func_promote(3)}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_disaster_1", "天崩开局", "隐藏", 0,
    ["骰子掷出大失败 1——今天似乎做什么都不顺。",
     "一早醒来，你就有一种说不出的不祥预感。"],
    [_choice("稳住心态，减少损失", "灾祸中保住底线", "d20", [
        _out(1, 6, "你被连环霉运击中，钱财与健康双双受损。", {"money": -5000, "health": -18, "happy": -16, "temp": +0.8}, "bad"),
        _out(7, 14, "虽然损失不小，但你及时止损了。", {"money": -2000, "health": -8, "happy": -8, "temp": +0.4}, "bad"),
        _out(15, 20, "你靠着冷静与一点运气，只擦破了皮。", {"money": -500, "health": -3, "happy": -3}, "neutral"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_lucky_99", "一线生机", "隐藏", 0,
    ["骰子掷出 99——在最绝望的地方，你看见了一道光。"],
    [_choice("抓住它", "绝境翻盘", "d20", [
        _out(1, 10, "你抓住了机会，境况明显好转。", {"money": +8000, "happy": +14, "health": +10}, "good"),
        _out(11, 20, "这不仅是一次转机，而是人生的分水岭。", {"money": +30000, "happy": +20, "health": +20}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_omen_2", "劫数初现", "隐藏", 0,
    ["骰子掷出 2——冥冥之中，阴影正在靠近。"],
    [_choice("提前防备", "是否能避开？", "d20", [
        _out(1, 8, "预警毫无作用，厄运还是降临了。", {"money": -3000, "health": -10, "happy": -10}, "bad"),
        _out(9, 20, "你提前做了准备，把损失降到了最低。", {"money": -300, "happy": -2}, "neutral"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_windfall_d20", "大成功", "隐藏", 0,
    ["d20 掷出 20——你从未想过事情能顺利到这种程度。"],
    [_choice("乘胜追击", "机会难得", "d6", [
        _out(1, 6, "你把这份好运扩大了三倍。", {"money": +12000, "happy": +18, "health": +8}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_catastrophe_d20", "大失败", "隐藏", 0,
    ["d20 掷出 1——所有糟糕的可能性同时发生了。"],
    [_choice("咬牙承受", "活着就有希望", "d6", [
        _out(1, 6, "你损失惨重，但还没到绝境。", {"money": -4000, "health": -12, "happy": -12, "temp": +0.5}, "bad"),
    ])],
    tone="secret", special=True, tags=["secret"])

_ev("secret_birthday", "生日", "隐藏", 0,
    ["今天是你的生日，朋友圈里刷满了祝福。",
     "手机一早就开始响，都是记得你生日的朋友。"],
    [_choice("好好庆祝一下", "一年只有一次", "d6", [
        _out(1, 3, "你请自己吃了顿大餐。", {"money": -600, "happy": +12}, "good"),
        _out(4, 6, "亲友们凑在一起为你庆生，你收到了很多礼物。", {"money": +300, "happy": +18, "health": +3}, "good"),
    ]),
     _choice("安静地度过", "平淡也是幸福", "d4", [
        _out(1, 4, "你给自己写了一封信，回顾这一年。", {"happy": +8}, "good"),
    ])],
    tone="secret", special=True, tags=["secret", "birthday"])

_ev("secret_milestone", "人生里程碑", "隐藏", 0,
    ["回望这一年，你发现自己已经走了很远。"],
    [_choice("记录下来", "为人生留个纪念", "d6", [
        _out(1, 6, "你为自己的人生写下了一页总结。", {"happy": +6}, "good"),
    ])],
    tone="secret", special=True, tags=["secret"])


# ------------------------------------------------------------------------------
# 8.7 事件抽取逻辑
# ------------------------------------------------------------------------------
# 事件概率采用**万分之一**精度（d10000）：
#   1) 先用 d10000 判定"今天是否发生值得记录的事件"（各人生阶段概率不同）
#   2) 再用 d10000 在允许的大类里按权重抽取
# 这样事件不再天天发生（例如幼儿园阶段约 7% 的日子有事，工作期约 16%）。
# ------------------------------------------------------------------------------

#: 隐藏事件触发条件：骰面 -> 事件id
SECRET_BY_D100 = {
    100: "secret_special_100",
    99: "secret_lucky_99",
    2: "secret_omen_2",
    1: "secret_disaster_1",
}
SECRET_BY_D20 = {20: "secret_windfall_d20", 1: "secret_catastrophe_d20"}

#: 大类抽取权重（万分位，总和 10000）——「日常」占比最高，避免天天跌宕起伏
CATEGORY_BANDS = [
    ("日常", 1, 3800),
    ("疾病", 3801, 5400),
    ("工作", 5401, 6800),
    ("情感", 6801, 8400),
    ("环境", 8401, 9200),
    ("意外", 9201, 10000),
]

#: 旧接口兼容：百分位区间（供外部工具/测试引用）
CATEGORY_BANDS_PERCENT = [
    ("日常", 1, 38),
    ("疾病", 39, 54),
    ("工作", 55, 68),
    ("情感", 69, 84),
    ("环境", 85, 92),
    ("意外", 93, 100),
]

#: 全部大类名称（含"日常/隐藏/综合"，用于冷却记录与展示）
CATEGORY_BANDS_NAMES = tuple([name for name, _l, _h in CATEGORY_BANDS]
                             + ["隐藏", "综合"])

#: 按人生阶段划分可触发的事件大类（孩子不会遇到职场与婚恋事件）
STAGE_CATEGORY_RULES = {
    "infant":       ("日常", "疾病", "情感"),
    "preschool":    ("日常", "疾病", "情感", "环境"),
    "kindergarten": ("日常", "疾病", "情感", "环境"),
    "primary":      ("日常", "疾病", "情感", "环境", "意外"),
    "middle":       ("日常", "疾病", "情感", "环境", "意外"),
    "zhongkao":     ("日常", "疾病", "情感", "环境", "意外"),
    "high":         ("日常", "疾病", "情感", "环境", "意外"),
    "gaokao":       ("日常", "疾病", "情感", "环境"),
    "university":   ("日常", "疾病", "情感", "环境", "意外", "工作"),
    "postgrad":     ("日常", "疾病", "情感", "环境", "意外", "工作"),
    "work":         ("日常", "疾病", "工作", "情感", "环境", "意外"),
    "retired":      ("日常", "疾病", "情感", "环境", "意外"),
    "dropout":      ("日常", "疾病", "工作", "情感", "环境", "意外"),
    "jobless":      ("日常", "疾病", "工作", "情感", "环境", "意外"),
}

#: 按年龄的兜底规则（当阶段信息缺失时使用）
AGE_CATEGORY_RULES = [
    (3, ("日常", "疾病", "情感")),
    (6, ("日常", "疾病", "情感", "环境")),
    (12, ("日常", "疾病", "情感", "环境", "意外")),
    (16, ("日常", "疾病", "情感", "环境", "意外")),
    (22, ("日常", "疾病", "情感", "环境", "意外")),
    (60, ("日常", "疾病", "工作", "情感", "环境", "意外")),
    (200, ("日常", "疾病", "情感", "环境", "意外")),
]


def categories_for_stage(stage_id, age=None):
    """返回该人生阶段允许触发的事件大类集合。"""
    rules = STAGE_CATEGORY_RULES.get(stage_id)
    if rules:
        return set(rules)
    return categories_for_age(age if age is not None else 0)


def categories_for_age(age):
    """返回该年龄允许触发的事件大类集合（兜底）。"""
    for limit, categories in AGE_CATEGORY_RULES:
        if age <= limit:
            return set(categories)
    return {name for name, _l, _h in CATEGORY_BANDS}


def category_from_roll(value):
    """根据 d10000 点数决定事件大类。"""
    for name, low, high in CATEGORY_BANDS:
        if low <= value <= high:
            return name
    return "意外"


def event_allowed_today(player, event, category, engine=None):
    """
    事件过滤：除"阶段允许"外，还做现实性校验与同类冷却：
      * 幼年（<6 岁）的"出门 / 通勤 / 独自行动"类事件必须由父母带领
      * 同一大类事件在 EVENT_CATEGORY_COOLDOWN_DAYS 天内不重复
      * 疾病类事件还要满足生病间隔（由引擎负责）
    """
    tags = set(event.get("tags") or [])

    # 1) 幼年出门限制：需要父母陪同
    if player.age < 6 and ("outdoor" in tags or "commute" in tags):
        with_parents = bool(event.get("with_parents", False))
        if not with_parents:
            # 事件本身没标记时，只要它所有选项都带 with_parents 也视为"父母陪同"
            choices = event.get("choices") or []
            with_parents = bool(choices) and all(
                bool(c.get("with_parents")) for c in choices)
        if not with_parents:
            return False

    # 2) 上学/工作在读阶段才有的校园、职场类事件
    if "school" in tags and getattr(player, "age", 0) < 5:
        return False

    # 3) 同类事件冷却
    if engine is not None:
        last_days = getattr(engine, "category_last_day", {}) or {}
        last = last_days.get(category)
        if last is not None and (player.total_days - last) < EVENT_CATEGORY_COOLDOWN_DAYS:
            return False
    return True


def available_events(category, player, allow_special=False, engine=None):
    """筛选当前条件下可触发的普通事件。"""
    result = []
    for eid in EVENT_ORDER:
        ev = EVENTS[eid]
        if ev["category"] != category:
            continue
        if ev["special"] and not allow_special:
            continue
        if ev["weight"] <= 0:
            continue
        try:
            if not ev["cond"](player):
                continue
        except Exception:
            continue
        if not event_allowed_today(player, ev, category, engine):
            continue
        result.append(ev)
    return result


def pick_event_weighted(dice, candidates, tag="事件抽取"):
    """
    加权抽取事件（万分位精度），返回 (事件, DiceResult)。
    """
    if not candidates:
        return None, dice.roll(10000, 1, 0, tag)
    res = dice.roll(10000, 1, 0, tag)
    total = float(sum(max(0.0, ev["weight"]) for ev in candidates)) or 1.0
    target = (res.value - 0.5) / 10000.0 * total
    acc = 0.0
    for ev in candidates:
        acc += max(0.0, ev["weight"])
        if target <= acc:
            return ev, res
    return candidates[-1], res


def roll_daily_event(dice, player, engine=None):
    """
    每日事件抽签主入口（万分位精度）。
    返回 dict：
        {"event": 事件或None, "category": 大类, "roll": DiceResult,
         "secret_reason": 隐藏触发说明 或 None, "internal": 事件id,
         "no_event": True/False}
    抽签规则：
        1. 先掷 d10000 判定"今天是否发生值得记录的事件"
           （各阶段概率在 EVENT_CHANCE_D10000 中配置，如幼儿园 700/10000 = 7%）
        2. 事件日再掷 d100 决定大类（极端点数 100/99/2/1 触发隐藏剧情）
        3. 大类受人生阶段限制（孩子不会遇到职场与婚恋事件）
        4. 最后用 d10000 在对应大类里按权重抽具体事件
    """
    # ---- 第一步：今天有没有事 ----
    chance_roll = dice.roll(10000, 1, 0, "事件发生判定")
    chance = event_chance_of(player)
    dice.remember(chance_roll, "事件发生判定（万分位）")
    if chance_roll.value > max(1.0, chance * 10000.0):
        return {"event": None, "category": "日常", "roll": chance_roll,
                "secret_reason": None, "internal": "", "no_event": True,
                "chance": chance}

    # ---- 第二步：事件大类 + 隐藏剧情 ----
    roll = dice.d100("事件大类判定")
    dice.remember(roll, "事件大类")
    secret_reason = roll.hidden
    if roll.value in SECRET_BY_D100 and not roll.flat:
        eid = SECRET_BY_D100[roll.value]
        return {"event": EVENTS[eid], "category": "隐藏", "roll": roll,
                "secret_reason": secret_reason, "internal": eid, "no_event": False,
                "chance": chance}

    allowed = categories_for_stage(getattr(player, "stage", None), getattr(player, "age", 0))
    category = category_from_roll(roll.value * 100) if False else category_from_d100(roll.value)
    if category not in allowed:
        ordered = [name for name, _l, _h in CATEGORY_BANDS if name in allowed]
        if not ordered:
            ordered = [name for name, _l, _h in CATEGORY_BANDS]
        reroll = dice.d100("阶段事件重抽")
        dice.remember(reroll, "阶段事件重抽")
        category = ordered[(reroll.value - 1) % len(ordered)]

    candidates = available_events(category, player, engine=engine)
    if not candidates:
        for name in sorted(allowed):
            candidates.extend(available_events(name, player, engine=engine))
        category = "综合"
    if not candidates:
        return {"event": None, "category": category, "roll": roll,
                "secret_reason": secret_reason, "internal": "", "no_event": True,
                "chance": chance}
    event, pick_roll = pick_event_weighted(dice, candidates, "%s事件挑选" % category)
    dice.remember(pick_roll, "%s事件挑选" % category)
    return {"event": event, "category": category, "roll": roll,
            "secret_reason": secret_reason, "internal": event["id"] if event else "",
            "no_event": False, "chance": chance}


def category_from_d100(value):
    """把 d100 结果映射到万分位大类区间（保持与 CATEGORY_BANDS 一致）。"""
    scaled = value * 100
    if scaled > 10000:
        scaled = 10000
    return category_from_roll(scaled)



def resolve_outcome(dice, choice):
    """
    根据选项掷骰并匹配结果区间，返回 (outcome, DiceResult)。
    区间写法 "d6" / "2d6" / "d100"；区间不覆盖时取最接近的一个。
    """
    res = dice.roll_notation(choice.get("roll", "d6"), "结果判定")
    outcomes = choice.get("outcomes") or []
    if not outcomes:
        return _out(0, 999, "什么也没有发生。"), res
    for out in outcomes:
        lo, hi = out["range"]
        if lo <= res.value <= hi:
            return out, res
    # 越界兜底：取区间距离最近的结果
    best = outcomes[0]
    best_dist = None
    for out in outcomes:
        lo, hi = out["range"]
        dist = 0 if lo <= res.value <= hi else min(abs(res.value - lo), abs(res.value - hi))
        if best_dist is None or dist < best_dist:
            best, best_dist = out, dist
    return best, res



# ==============================================================================
# 9. 人物（玩家）状态
# ==============================================================================

SAVE_VERSION = 1


class Player:
    """
    人物对象：保存四项核心属性、时间、城市、疾病与人生记录。
    所有属性变更都通过 apply_effects 统一处理，保证边界约束与死亡判定一致。
    """

    def __init__(self, name="无名氏", city="beijing", rng=None):
        self.name = (name or "无名氏").strip()[:12] or "无名氏"
        self.city = city if city in CITIES else "beijing"

        # ---- 四项核心属性 ----
        self.health = float(INIT_HEALTH)     # 健康 0~100，归零死亡
        self.happy = float(INIT_HAPPY)       # 幸福 0~100
        self.money = float(INIT_MONEY)       # 金钱，可负债
        self.temp = float(INIT_TEMP)         # 体温，正常 36.0~37.0

        # ---- 开局随机固定参数：体质 / 家境 ----
        _rng = rng or random.Random()
        self.constitution = round(_rng.gauss(CONSTITUTION_MEAN, CONSTITUTION_SD), 1)
        self.constitution = max(CONSTITUTION_MIN, min(CONSTITUTION_MAX, self.constitution))
        self.family_wealth = round(_rng.gauss(FAMILY_WEALTH_MEAN, FAMILY_WEALTH_SD), 1)
        self.family_wealth = max(FAMILY_WEALTH_MIN, min(FAMILY_WEALTH_MAX, self.family_wealth))
        self.family_bankrupt = False         # 家庭是否破产（破产后不再提供支持）
        self.left_home = False               # 是否已离家独立（不再接受家庭支持）
        self.family_notes = []               # 家庭相关记录

        # ---- 时间 ----
        self.age = INIT_AGE                  # 年龄（岁）
        self.year = 1                        # 第几年（从 1 开始）
        self.month = 1                       # 1~12
        self.day = 1                         # 1~30
        self.total_days = 0                  # 已度过天数
        self.birth_month = 1                 # 生日（月）
        self.birth_day = 1                   # 生日（日）

        # ---- 人生阶段与学业 ----
        self.stage = "infant"                # 当前人生阶段 id
        self.stage_history = []              # 阶段变化记录
        self.education = []                  # 学历记录（幼儿园/小学/初中/高中/大学/研究生）
        self.exam_results = {}               # 考试成绩（中考/高考/考研）
        self.university_ok = None            # 是否考上大学
        self.postgrad_ok = None              # 是否考上研究生

        # ---- 行动点（游戏内同一天最多 8 次操作）----
        self.action_points = ACTION_POINTS_PER_DAY
        self.actions_today = 0
        self.action_tally = {}               # 当天各类操作次数（用于收益衰减）
        self.days_played = 0                 # 已经历的游戏内天数

        # ---- 状态 ----
        self.diseases = []                   # 活动疾病列表
        self.employed = False                # 是否在职
        self.job_level = 0                   # 职级（影响工资）
        self.married = False                 # 已婚
        self.children = 0                    # 子女数量
        # ---- 生育系统 ----
        self.partner_name = ""               # 伴侣姓名
        self.married_date = ""               # 结婚日期
        self.pregnant = False                # 是否处于孕期
        self.pregnancy_days = 0              # 已怀孕天数
        self.pregnancy_count = 0             # 累计怀孕次数
        self.birth_count = 0                 # 累计生产次数
        self.child_list = []                 # 子女档案（姓名/生日/性别/体质）
        self.intimacy_today = 0              # 今天已进行的亲密次数
        self.intimacy_last_day = None        # 上次亲密的天数
        self.contraception = "避孕套"         # 当前避孕方式
        self.conception_history = []         # 受孕记录
        self.miscarriage = 0                 # 流产次数
        self.next_child_gender = None         # 占位（保留）
        self.carried_effects = []            # 跨天持续效果
        self.milestones = []                 # 人生大事记
        self.event_history = []              # 已触发事件记录
        self.last_illness_day = None         # 上次生病的天数（用于生病间隔）
        self.plain_days = 0                  # 平凡的一天计数
        self.illness_count = 0               # 累计生病次数
        self.stats = {                       # 统计信息
            "days_worked": 0, "days_rested": 0, "days_played": 0,
            "total_income": 0.0, "total_expense": 0.0,
            "disease_count": 0, "cure_count": 0, "max_money": float(INIT_MONEY),
            "rest_streak": 0, "low_health_days": 0, "hospital_count": 0,
            "family_support_total": 0.0, "actions_total": 0, "skipped_days": 0,
            "study_points": 0, "debt": 0.0,
        }
        self.dead = False
        self.death_reason = ""
        self.death_date = ""
        self.summary_done = False

        self.ambient_temp = 15.0             # 当日气温（引擎写入）
        self.rng = rng or random.Random()    # 独立随机源（用于环境温度存盘一致性）

    # ------------------------------------------------------------------
    # 属性读写
    # ------------------------------------------------------------------
    @property
    def date_text(self):
        return "%d 年 %d 月 %d 日" % (self.year, self.month, self.day)

    @property
    def date_full(self):
        return "%d 岁 · %d 年 %d 月 %d 日" % (self.age, self.year, self.month, self.day)

    @property
    def life_stage(self):
        """根据年龄返回人生阶段描述。"""
        a = self.age
        if a <= 3:
            return "婴幼儿"
        if a <= 6:
            return "学龄前"
        if a <= 12:
            return "小学生"
        if a <= 15:
            return "初中生"
        if a <= 18:
            return "高中生"
        if a <= 22:
            return "大学生"
        if a <= 30:
            return "青年"
        if a <= 45:
            return "壮年"
        if a <= 60:
            return "中年"
        if a <= 75:
            return "老年"
        return "高龄"

    @property
    def status_text(self):
        if self.dead:
            return "已故"
        if self.health <= 20:
            return "奄奄一息"
        if self.health <= 45:
            return "虚弱"
        if self.happy <= 20:
            return "抑郁"
        if self.temp >= 38.0:
            return "高烧"
        if self.temp <= 35.0:
            return "失温"
        if self.health >= 85 and self.happy >= 60:
            return "状态良好"
        return "尚可"

    # ------------------------------------------------------------------
    # 疾病管理
    # ------------------------------------------------------------------
    def has_disease(self, disease_id):
        return any(d["id"] == disease_id for d in self.diseases)

    def disease_names(self):
        return "、".join(d["name"] for d in self.diseases) if self.diseases else "无"

    def worst_disease(self):
        """返回最严重的活动疾病（用于界面提示）。"""
        if not self.diseases:
            return None
        return max(self.diseases, key=lambda d: DISEASE_SEVERITY.get(d["id"], 0))

    def add_disease(self, disease_id, hp_scale=1.0, temp_scale=1.0, days_bonus=0,
                    dice=None, force=False):
        """
        施加疾病。若已患同类疾病则叠加病程与强度（雪上加霜）。
          * force=False（默认）：先按 U 型年龄曲线做一次"是否真的病倒"的判定，
            未通过时返回 (None, 说明)，用于模拟"多数时候身体扛得住"。
          * force=True：必定患病（用于病情必然恶化的连锁事件）。
        返回 (疾病实例 或 None, 说明文本)。
        """
        dice = dice or DiceSystem(self.rng)
        existing = next((d for d in self.diseases if d["id"] == disease_id), None)
        if existing:
            existing["days"] += 2
            existing["total_days"] += 2
            existing["hp_per_day"] = round(existing["hp_per_day"] * 1.25, 2)
            return existing, "旧病未愈，病情加重了"
        if not force:
            # 每日患病概率（万分位精度，含体质/年龄/状态/城市）
            prob = sickness_probability(self)
            roll = dice.roll(10000, 1, 0, "患病判定")
            if roll.value > max(1.0, prob * 10000.0):
                return None, "这次身体扛住了，没有真的病倒（万分位判定 %d > %.1f）" % (
                    roll.value, prob * 10000.0)
        info = make_disease(dice, disease_id, hp_scale=hp_scale,
                            days_bonus=days_bonus, temp_scale=temp_scale)
        # 体质影响病程：体质越差，病得越久
        factor = duration_factor(self.constitution)
        if factor != 1.0:
            info["days"] = max(1, int(round(info["days"] * factor)))
            info["total_days"] = info["days"]
        self.diseases.append(info)
        self.stats["disease_count"] += 1
        self.illness_count += 1
        self.last_illness_day = self.total_days
        return info, "新患病：%s（体质 %d 分，病程 %d 天）" % (
            info["name"], int(round(self.constitution)), info["days"])

    def worsen_disease(self, disease_id=None, factor=1.3, extra_days=2):
        """让疾病恶化：每日扣血更多、持续更久（强度有上限，避免数值失控）。"""
        target = None
        if disease_id:
            target = next((d for d in self.diseases if d["id"] == disease_id), None)
        target = target or self.worst_disease()
        if not target:
            return None
        base = DISEASES.get(target["id"], {}).get("hp_per_day", target["hp_per_day"])
        cap = base * 2.0                       # 单种疾病最多恶化到基础值的 2 倍
        target["hp_per_day"] = round(min(cap, target["hp_per_day"] * factor), 2)
        target["days"] += extra_days
        target["total_days"] += extra_days
        return target

    def cure_disease(self, disease_id=None):
        """
        治愈疾病。disease_id 为空时治愈最严重的一种。
        返回 (是否成功, 说明文本, 花费)
        """
        if not self.diseases:
            return False, "你身体很健康，没有需要治疗的疾病。", 0.0
        if disease_id:
            target = next((d for d in self.diseases if d["id"] == disease_id), None)
        else:
            target = self.worst_disease()
        if not target:
            return False, "没有找到对应的疾病。", 0.0
        cost = float(target["cure_cost"])
        if self.money < cost:
            return False, "金钱不足：治疗%s需要 %.2f，你只有 %.2f。" % (
                target["name"], cost, self.money), cost
        self.money = round_money(self.money - cost)
        self.stats["total_expense"] = round_money(self.stats.get("total_expense", 0.0) + cost)
        self.diseases.remove(target)
        self.stats["cure_count"] += 1
        # 治愈后体温向正常值靠拢
        self.temp = clamp_temp(self.temp + (36.5 - self.temp) * 0.6)
        return True, "你花了 %.2f 治好了%s。" % (cost, target["name"]), cost

    # ------------------------------------------------------------------
    # 效果应用（核心）
    # ------------------------------------------------------------------
    def apply_effects(self, effects, dice=None):
        """
        应用效果字典，返回 (属性差值字典, 描述文本列表)。
        差值字典包含实际生效的 health/happy/money/temp 变化量。
        """
        dice = dice or DiceSystem(self.rng)
        effects = effects or {}
        before = {"health": self.health, "happy": self.happy,
                  "money": self.money, "temp": self.temp}
        notes = []

        # 0) 未成年保护 + 巨款缩放：
        #    未成年人由家庭抚养，收入/奖金大幅缩减；
        #    大额金钱变化再按年龄与身价做一次缩放，避免"幼儿中巨奖"这类数值崩坏。
        money_change = float(effects.get("money", 0))
        if money_change != 0:
            mult = 1.0
            if self.age < 18:
                if self.age < 6:
                    mult *= 0.15
                elif self.age < 12:
                    mult *= 0.25
                elif self.age < 16:
                    mult *= 0.35
                else:
                    mult *= 0.6
            if abs(money_change) > 3000:
                # 大额金钱：随年龄增长而放大（成年后接近全额），儿童只能拿到象征性部分
                if abs(money_change) >= 100000:
                    age_factor = max(0.02, min(1.0, 0.02 + self.age * 0.033))
                else:
                    age_factor = max(0.10, min(1.0, 0.10 + self.age * 0.030))
                # 已是富豪时大额收益递减，防止数值无限膨胀
                wealth_factor = 1.0 - 0.5 * (1.0 - 1.0 / (1.0 + max(0.0, self.money) / 400000.0))
                mult *= age_factor * wealth_factor
            if abs(mult - 1.0) > 1e-9:
                effects = dict(effects)
                effects["money"] = money_change * mult
                if money_change > 0:
                    notes.append("（实际到手按年龄/身价折算：%.0f%%）" % (mult * 100))
                else:
                    notes.append("（实际支出按年龄/身价折算：%.0f%%）" % (mult * 100))

        # 1) 直接数值
        self.health = clamp_health(self.health + float(effects.get("health", 0)))
        self.happy = clamp_happy(self.happy + float(effects.get("happy", 0)))
        self.money = round_money(self.money + float(effects.get("money", 0)))
        if "temp" in effects:
            self.temp = clamp_temp(self.temp + float(effects["temp"]))

        # 2) 回复类（受上限限制，不会超过 100）
        if effects.get("health_boost"):
            boost = float(effects["health_boost"])
            self.health = clamp_health(min(HEALTH_MAX, self.health + boost))
        if effects.get("happy_boost"):
            boost = float(effects["happy_boost"])
            self.happy = clamp_happy(min(HAPPY_MAX, self.happy + boost))

        # 3) 体温趋势（次日生效）
        if effects.get("temp_drift"):
            self.carried_effects.append({
                "type": "temp_drift",
                "value": float(effects["temp_drift"]),
                "days": int(effects.get("temp_drift_days", 2)),
                "name": effects.get("title", "体温趋势"),
            })

        # 4) 疾病
        if effects.get("worsen_disease"):
            target = self.worsen_disease(effects.get("worsen_disease"))
            if target:
                notes.append("%s 恶化，每日健康 -%.1f" % (target["name"], target["hp_per_day"]))

        if effects.get("disease"):
            spec = effects["disease"]
            days_bonus = 0
            hp_scale, temp_scale = 1.0, 1.0
            force = bool(effects.get("force_disease", False))
            if isinstance(spec, (tuple, list)):
                did = spec[0]
                if len(spec) > 1:
                    days_bonus = int(spec[1])
                if len(spec) > 2:
                    hp_scale = float(spec[2])
            else:
                did = spec
            # 默认走 U 型年龄曲线的患病判定（add_disease 内部完成）
            info, msg = self.add_disease(did, hp_scale=hp_scale,
                                         temp_scale=temp_scale,
                                         days_bonus=days_bonus, dice=dice,
                                         force=force)
            if msg:
                notes.append(msg)

        if effects.get("cure"):
            cid = effects["cure"] if isinstance(effects["cure"], str) else None
            ok, msg, _cost = self.cure_disease(cid)
            notes.append(msg)

        # 5) 自定义回调
        func = effects.get("func")
        if callable(func):
            try:
                extra = func(self)
                if extra:
                    notes.extend(extra)
            except Exception as exc:
                notes.append("（效果结算出现异常：%s）" % exc)

        # 6) 额外属性（体力等扩展属性一律走 clamp）
        for key, value in (effects.get("extra") or {}).items():
            if key in ("health", "happy", "money", "temp"):
                continue
            setattr(self, key, value)

        # 7) 统计
        delta = {
            "health": round(self.health - before["health"], 2),
            "happy": round(self.happy - before["happy"], 2),
            "money": round_money(self.money - before["money"]),
            "temp": round(self.temp - before["temp"], 2),
        }
        if delta["money"] > 0:
            self.stats["total_income"] = round_money(self.stats.get("total_income", 0.0) + delta["money"])
        elif delta["money"] < 0:
            self.stats["total_expense"] = round_money(self.stats.get("total_expense", 0.0) - delta["money"])
        self.stats["max_money"] = max(self.stats.get("max_money", 0.0), self.money)
        return delta, notes

    # ------------------------------------------------------------------
    # 大事记
    # ------------------------------------------------------------------
    def add_milestone(self, text, tag="life"):
        """记录人生大事（生日、恋爱、结婚、失业、重病、死亡等）。"""
        item = {"date": self.date_full, "text": text, "tag": tag}
        self.milestones.append(item)
        if len(self.milestones) > 500:
            self.milestones = self.milestones[-500:]
        return item

    def remember_event(self, name, category, summary):
        """记录触发过的事件（用于存档与日志回看）。"""
        self.event_history.append({
            "date": self.date_full, "name": name,
            "category": category, "summary": summary[:120],
        })
        if len(self.event_history) > 3000:
            self.event_history = self.event_history[-3000:]

    # ------------------------------------------------------------------
    # 结算辅助
    # ------------------------------------------------------------------
    def net_worth(self):
        """粗略身价：现金 + 房产/资产估算（资产按职级与年限估算）。"""
        asset = self.job_level * 2000.0 + min(self.total_days, 36000) * 0.4
        return round_money(self.money + asset)

    def attribute_rows(self):
        """返回界面用的属性表：[(名称, 当前值文本, 备注, 颜色)]"""
        rows = [
            ("健康", "%.1f / %d" % (self.health, HEALTH_MAX),
             "归零即死亡" if self.health > 20 else "！！！濒临死亡", self.health_color()),
            ("幸福", "%.1f / %d" % (self.happy, HAPPY_MAX),
             "低于 %d 会持续扣健康" % LOW_HAPPY_THRESHOLD, self.happy_color()),
            ("金钱", "%.2f" % self.money, "负债状态" if self.money < 0 else "可治病 / 消费", self.money_color()),
            ("体温", "%.1f ℃" % self.temp,
             "正常 36.0~37.0" if TEMP_NORMAL_LOW <= self.temp <= TEMP_NORMAL_HIGH else "异常！每日扣健康",
             self.temp_color()),
        ]
        return rows

    def health_color(self):
        """极简配色：健康充裕时用白字，偏低时用橙色警示。"""
        if self.health <= 20:
            return "#ff8c00"
        if self.health <= 50:
            return "#ff8c00"
        return "#ffffff"

    def happy_color(self):
        if self.happy < LOW_HAPPY_THRESHOLD:
            return "#ff8c00"
        if self.happy < 45:
            return "#ff8c00"
        return "#ffffff"

    def money_color(self):
        if self.money < 0 or self.money < 500:
            return "#ff8c00"
        return "#ffffff"

    def temp_color(self):
        if TEMP_NORMAL_LOW <= self.temp <= TEMP_NORMAL_HIGH:
            return "#ffffff"
        return "#ff8c00"

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self):
        return {
            "name": self.name, "city": self.city,
            "health": self.health, "happy": self.happy,
            "money": self.money, "temp": self.temp,
            "constitution": self.constitution, "family_wealth": self.family_wealth,
            "family_bankrupt": self.family_bankrupt, "left_home": self.left_home,
            "family_notes": self.family_notes[-50:],
            "age": self.age, "year": self.year, "month": self.month, "day": self.day,
            "total_days": self.total_days,
            "birth_month": self.birth_month, "birth_day": self.birth_day,
            "stage": self.stage, "stage_history": self.stage_history[-100:],
            "education": self.education, "exam_results": self.exam_results,
            "university_ok": self.university_ok, "postgrad_ok": self.postgrad_ok,
            "action_points": self.action_points, "actions_today": self.actions_today,
            "action_tally": self.action_tally, "days_played": self.days_played,
            "diseases": self.diseases, "employed": self.employed,
            "job_level": self.job_level, "married": self.married,
            "children": self.children, "carried_effects": self.carried_effects,
            "partner_name": self.partner_name, "married_date": self.married_date,
            "pregnant": self.pregnant, "pregnancy_days": self.pregnancy_days,
            "pregnancy_count": self.pregnancy_count, "birth_count": self.birth_count,
            "child_list": self.child_list, "intimacy_today": self.intimacy_today,
            "intimacy_last_day": self.intimacy_last_day,
            "contraception": self.contraception,
            "conception_history": self.conception_history[-50:],
            "miscarriage": self.miscarriage,
            "last_illness_day": self.last_illness_day,
            "plain_days": self.plain_days, "illness_count": self.illness_count,
            "milestones": self.milestones, "event_history": self.event_history[-500:],
            "stats": self.stats, "dead": self.dead,
            "death_reason": self.death_reason, "death_date": self.death_date,
            "summary_done": self.summary_done, "ambient_temp": self.ambient_temp,
            "rng_state": self.rng.getstate() if hasattr(self.rng, "getstate") else None,
        }

    @classmethod
    def from_dict(cls, data, rng=None):
        """从存档字典恢复人物；字段缺失时使用默认值，保证兼容旧存档。"""
        if not isinstance(data, dict):
            raise ValueError("存档内容不是合法的对象")
        player = cls(name=data.get("name", "无名氏"),
                     city=data.get("city", "beijing"), rng=rng)
        for key, caster in (("health", clamp_health), ("happy", clamp_happy),
                            ("money", round_money), ("temp", clamp_temp)):
            try:
                setattr(player, key, caster(float(data.get(key, getattr(player, key)))))
            except Exception:
                pass
        for key in ("age", "year", "month", "day", "total_days",
                    "birth_month", "birth_day", "job_level", "children"):
            try:
                setattr(player, key, int(data.get(key, getattr(player, key))))
            except Exception:
                pass
        player.month = int(clamp(player.month, 1, MONTHS_PER_YEAR))
        player.day = int(clamp(player.day, 1, DAYS_PER_MONTH))
        player.birth_month = int(clamp(player.birth_month, 1, MONTHS_PER_YEAR))
        player.birth_day = int(clamp(player.birth_day, 1, DAYS_PER_MONTH))
        player.employed = bool(data.get("employed", False))
        player.married = bool(data.get("married", False))
        player.dead = bool(data.get("dead", False))
        player.death_reason = data.get("death_reason", "") or ""
        player.death_date = data.get("death_date", "") or ""
        player.summary_done = bool(data.get("summary_done", False))
        # ---- 体质 / 家境（旧存档没有这两个字段时按均值补齐）----
        for key, lo, hi, mean in (("constitution", CONSTITUTION_MIN, CONSTITUTION_MAX,
                                   CONSTITUTION_MEAN),
                                  ("family_wealth", FAMILY_WEALTH_MIN, FAMILY_WEALTH_MAX,
                                   FAMILY_WEALTH_MEAN)):
            try:
                setattr(player, key, max(lo, min(hi, float(data.get(key, mean)))))
            except Exception:
                setattr(player, key, mean)
        player.family_bankrupt = bool(data.get("family_bankrupt", False))
        player.left_home = bool(data.get("left_home", False))
        player.family_notes = [str(x) for x in (data.get("family_notes") or [])][-50:]
        # ---- 人生阶段 / 学业 ----
        stage = data.get("stage")
        player.stage = stage if stage in STAGE_BY_ID else stage_of_age(player.age)
        player.stage_history = [s for s in (data.get("stage_history") or [])
                               if isinstance(s, dict)][-100:]
        player.education = [str(x) for x in (data.get("education") or [])]
        exams = data.get("exam_results")
        player.exam_results = exams if isinstance(exams, dict) else {}
        player.university_ok = data.get("university_ok", None)
        player.postgrad_ok = data.get("postgrad_ok", None)
        # ---- 行动点 ----
        try:
            player.action_points = int(data.get("action_points", ACTION_POINTS_PER_DAY))
        except Exception:
            player.action_points = ACTION_POINTS_PER_DAY
        player.action_points = max(0, min(ACTION_POINTS_PER_DAY, player.action_points))
        try:
            player.actions_today = max(0, int(data.get("actions_today", 0)))
            player.days_played = max(0, int(data.get("days_played", 0)))
        except Exception:
            pass
        tally = data.get("action_tally")
        player.action_tally = tally if isinstance(tally, dict) else {}
        # ---- 生育系统字段（旧存档缺失时补齐）----
        player.partner_name = str(data.get("partner_name", "") or "")
        player.married_date = str(data.get("married_date", "") or "")
        player.pregnant = bool(data.get("pregnant", False))
        try:
            player.pregnancy_days = max(0, int(data.get("pregnancy_days", 0)))
            player.pregnancy_count = max(0, int(data.get("pregnancy_count", 0)))
            player.birth_count = max(0, int(data.get("birth_count", 0)))
            player.intimacy_today = max(0, int(data.get("intimacy_today", 0)))
            player.miscarriage = max(0, int(data.get("miscarriage", 0)))
        except Exception:
            pass
        try:
            player.intimacy_last_day = (None if data.get("intimacy_last_day") is None
                                        else int(data.get("intimacy_last_day")))
        except Exception:
            player.intimacy_last_day = None
        player.contraception = str(data.get("contraception", "避孕套") or "避孕套")
        if player.contraception not in [o[0] for o in CONTRACEPTION_OPTIONS]:
            player.contraception = "避孕套"
        child_list = []
        for item in (data.get("child_list") or []):
            if not isinstance(item, dict):
                continue
            child_list.append({
                "name": str(item.get("name", "孩子")),
                "gender": str(item.get("gender", "未知")),
                "birth_date": str(item.get("birth_date", "")),
                "constitution": float(item.get("constitution", CONSTITUTION_MEAN)),
                "mother_age": int(item.get("mother_age", player.age)),
            })
        player.child_list = child_list
        player.children = max(player.children, len(child_list))
        player.conception_history = [x for x in (data.get("conception_history") or [])
                                     if isinstance(x, dict)][-50:]
        try:
            player.last_illness_day = (None if data.get("last_illness_day") is None
                                       else int(data.get("last_illness_day")))
            player.plain_days = max(0, int(data.get("plain_days", 0)))
            player.illness_count = max(0, int(data.get("illness_count", 0)))
        except Exception:
            pass
        try:
            player.ambient_temp = float(data.get("ambient_temp", player.ambient_temp))
        except Exception:
            pass
        # 疾病：清洗字段，避免损坏的存档导致崩溃
        diseases = []
        for item in (data.get("diseases") or []):
            if not isinstance(item, dict):
                continue
            did = item.get("id")
            if did not in DISEASES:
                continue
            base = DISEASES[did]
            diseases.append({
                "id": did,
                "name": item.get("name", base["name"]),
                "kind": item.get("kind", base["kind"]),
                "days": max(1, int(item.get("days", 1))),
                "total_days": max(1, int(item.get("total_days", 1))),
                "hp_per_day": float(item.get("hp_per_day", base["hp_per_day"])),
                "happy_per_day": float(item.get("happy_per_day", base["happy_per_day"])),
                "cure_cost": float(item.get("cure_cost", base["cure_cost"])),
                "self_heal": float(item.get("self_heal", base["self_heal"])),
                "temp_mod": float(item.get("temp_mod", base["temp_mod"])),
                "needs_cure": bool(item.get("needs_cure", base.get("needs_cure", False))),
                "fatal": bool(item.get("fatal", base.get("fatal", False))),
            })
        player.diseases = diseases
        # 持续效果
        carried = []
        for item in (data.get("carried_effects") or []):
            if isinstance(item, dict) and item.get("type"):
                carried.append({
                    "type": item.get("type"),
                    "value": float(item.get("value", 0)),
                    "days": max(0, int(item.get("days", 0))),
                    "name": item.get("name", "持续效果"),
                })
        player.carried_effects = carried
        player.milestones = [m for m in (data.get("milestones") or []) if isinstance(m, dict)][-500:]
        player.event_history = [e for e in (data.get("event_history") or []) if isinstance(e, dict)][-500:]
        stats = data.get("stats")
        if isinstance(stats, dict):
            player.stats.update({k: v for k, v in stats.items() if k in player.stats})
        return player


# ==============================================================================
# 10. 人生日志（life_log.txt）
# ==============================================================================

class LifeLog:
    """负责把每日关键事件、属性变化与人生节点写入 life_log.txt。"""

    #: 日志文件大小上限（约 8MB），超过后不再追加逐日流水（人生总结仍会写入）
    MAX_LOG_BYTES = 8 * 1024 * 1024

    def __init__(self, path=None, player_name="", city_name=""):
        self.path = path
        self.player_name = player_name
        self.city_name = city_name
        self.memory = []          # 内存中的日志行（界面回看用）
        self.error = None
        self.oversize = False     # 日志文件是否已达上限

    # ------------------------------------------------------------------
    def _write(self, text, force=False):
        """写入一行日志；写入失败只记录错误，不抛出异常。"""
        stamp = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s" % (stamp, text)
        self.memory.append(line)
        if len(self.memory) > 20000:
            self.memory = self.memory[-20000:]
        if not self.path:
            return False
        if self.oversize and not force:
            return False
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            # 控制日志体积，避免长时间挂机后文件过大
            try:
                if os.path.getsize(self.path) > self.MAX_LOG_BYTES:
                    self.oversize = True
                    with open(self.path, "a", encoding="utf-8") as fh2:
                        fh2.write("[日志已达大小上限，之后仅记录重大节点与人生总结]\n")
            except Exception:
                pass
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    # ------------------------------------------------------------------
    def start(self, player):
        """开局：写入分隔线与人物档案。"""
        self.player_name = player.name
        self.city_name = get_city(player.city)["name"]
        sep = "=" * 78
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write("\n" + sep + "\n")
                fh.write("【新的人生开始】%s\n" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                fh.write("姓名：%s    城市：%s（%s）\n" % (
                    player.name, self.city_name, get_city(player.city)["tag"]))
                fh.write("初始属性：健康 %.0f / 幸福 %.0f / 金钱 %.2f / 体温 %.1f℃\n" % (
                    player.health, player.happy, player.money, player.temp))
                fh.write(sep + "\n")
        except Exception as exc:
            self.error = str(exc)
        self.memory.append("【新的人生开始】%s · %s" % (player.name, self.city_name))

    def daily(self, player, event_name, summary, delta, ambient=None):
        """记录一天的关键事件与属性变化。"""
        delta_text = "健康%+.1f 幸福%+.1f 金钱%+.0f 体温%+.1f" % (
            delta.get("health", 0), delta.get("happy", 0),
            delta.get("money", 0), delta.get("temp", 0))
        ambient_text = ("气温 %.1f℃" % ambient) if ambient is not None else ""
        line = "%s｜%s｜事件：%s｜%s｜%s｜当前：健康%.1f 幸福%.1f 金钱%.2f 体温%.1f℃" % (
            player.date_full, player.life_stage, event_name, summary,
            (ambient_text + "｜" if ambient_text else "") + delta_text,
            player.health, player.happy, player.money, player.temp)
        self._write(line)

    def milestone(self, player, text, tag="life"):
        """记录人生重大节点。"""
        self._write("★【%s】%s｜%s" % (tag, player.date_full, text), force=True)

    def disease(self, player, text):
        self._write("＋【疾病】%s｜%s" % (player.date_full, text), force=True)

    def settlement(self, player, text):
        self._write("￥【结算】%s｜%s" % (player.date_full, text), force=True)

    def death(self, player, reason):
        self._write("☠【死亡】%s｜%s" % (player.date_full, reason), force=True)

    # ------------------------------------------------------------------
    def life_summary(self, player):
        """生成完整人生总结（死亡时调用），并追加到日志。"""
        lines = []
        sep = "=" * 78
        lines.append("")
        lines.append(sep)
        lines.append("【人生总结】%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("姓名：%s（%s）    城市：%s" % (
            player.name, player.life_stage, get_city(player.city)["name"]))
        lines.append("享年：%d 岁（共度过 %d 天，约 %.1f 年）" % (
            player.age, player.total_days, player.total_days / float(DAYS_PER_YEAR)))
        lines.append("离世时间：%s" % (player.death_date or player.date_text))
        lines.append("离世原因：%s" % (player.death_reason or "自然衰老"))
        lines.append("-" * 78)
        lines.append("最终属性：健康 %.1f / 幸福 %.1f / 金钱 %.2f / 体温 %.1f℃" % (
            player.health, player.happy, player.money, player.temp))
        lines.append("身价估算：%.2f（最高峰 %.2f）" % (
            player.net_worth(), player.stats.get("max_money", 0.0)))
        lines.append("婚恋状况：%s    子女：%d 人    职级：%d 级" % (
            "已婚" if player.married else "未婚", player.children, player.job_level))
        lines.append("统计：工作 %d 天 / 休息 %d 天 / 患病 %d 次 / 治愈 %d 次" % (
            player.stats.get("days_worked", 0), player.stats.get("days_rested", 0),
            player.stats.get("disease_count", 0), player.stats.get("cure_count", 0)))
        lines.append("累计收入 %.2f    累计支出 %.2f" % (
            player.stats.get("total_income", 0.0), player.stats.get("total_expense", 0.0)))
        lines.append("-" * 78)
        lines.append("【生平大事记】")
        if player.milestones:
            for item in player.milestones:
                lines.append("  · %s  %s" % (item.get("date", ""), item.get("text", "")))
        else:
            lines.append("  · （这一生波澜不惊，没有什么值得特别记录的。）")
        lines.append("-" * 78)
        lines.append("【事件总览（最近 40 条）】")
        for item in player.event_history[-40:]:
            lines.append("  · %s｜%s｜%s" % (item.get("date", ""), item.get("name", ""),
                                             item.get("summary", "")))
        lines.append(sep)
        text = "\n".join(lines)
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception as exc:
            self.error = str(exc)
        self.memory.append("【人生总结】享年 %d 岁，%s" % (player.age, player.death_reason))
        return text


    def tail_lines(self, count=200):
        """读取日志文件末尾若干行（用于界面回看）。"""
        if not self.path or not os.path.isfile(self.path):
            return list(self.memory[-count:])
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
            return [ln.rstrip("\n") for ln in lines[-count:]]
        except Exception as exc:
            self.error = str(exc)
            return list(self.memory[-count:])


# ==============================================================================
# 11. 存档系统（save.json）
# ==============================================================================

def save_game(path, player, log=None):
    """
    保存进度到 JSON 文件（先写临时文件再替换，避免中途失败损坏存档）。
    返回 (是否成功, 提示信息)
    """
    data = {
        "version": SAVE_VERSION,
        "app": APP_NAME,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "player": player.to_dict(),
    }
    tmp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    except Exception:
        pass
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return True, "进度已保存到：\n%s" % path
    except Exception as exc:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False, "保存失败：%s" % exc


def load_game(path, rng=None):
    """
    读取存档。
    返回 (player 或 None, 提示信息)
    """
    if not path or not os.path.isfile(path):
        return None, "找不到存档文件：\n%s\n\n请先开始一局游戏并保存进度。" % (path or "(未设置路径)")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:
        return None, "读取存档失败：%s" % exc
    try:
        data = json.loads(raw)
    except Exception as exc:
        return None, "存档内容已损坏，无法解析：%s" % exc
    if not isinstance(data, dict) or "player" not in data:
        return None, "存档格式不正确（缺少人物数据）。"
    try:
        player = Player.from_dict(data["player"], rng=rng)
    except Exception as exc:
        return None, "存档人物数据异常：%s" % exc
    saved_at = data.get("saved_at", "未知时间")
    return player, "读取成功。\n存档时间：%s\n姓名：%s    时间：%s" % (
        saved_at, player.name, player.date_full)


def save_exists(path):
    return bool(path) and os.path.isfile(path)


def delete_save(path):
    """删除存档，返回 (是否成功, 提示)。"""
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True, "存档已删除。"
        return False, "没有找到可删除的存档。"
    except Exception as exc:
        return False, "删除存档失败：%s" % exc


# ==============================================================================
# 12. 每日结算引擎（模拟器）
# ==============================================================================

class DailyReport:
    """一天结算后的完整结果，供界面展示与日志记录。"""

    def __init__(self, player):
        self.player = player
        self.date = player.date_full
        self.ambient = player.ambient_temp
        self.roll_lines = []          # 骰子说明行
        self.lines = []               # 结算说明行
        self.delta = {"health": 0.0, "happy": 0.0, "money": 0.0, "temp": 0.0}
        self.event_name = ""
        self.death = False
        self.birthday = False
        self.secret = False
        self.month_settlement = None

    def add_line(self, text):
        if text:
            self.lines.append(text)

    def accumulate(self, delta):
        for key in self.delta:
            self.delta[key] = round(self.delta[key] + float(delta.get(key, 0)), 2)


class Simulator:
    """
    游戏引擎：时间推进、日月年结算、事件抽取、疾病与体温结算。
    与界面完全解耦——界面只调用 step_roll / resolve_choice / apply_daily_action。
    """

    def __init__(self, player, log=None, base_dir="", seed=None):
        self.player = player
        self.log = log
        self.base_dir = base_dir
        self.dice = DiceSystem(random.Random(seed) if seed is not None else random.Random())
        self.pending = None            # 待结算的事件卡
        self.last_report = None
        self.game_over = False
        self.pending_followup = None   # 连锁事件
        self.current_seed = seed
        self.category_last_day = {}    # 各大类事件最近一次发生的天数（冷却用）
        self.mod_hooks_used = []       # 记录本次运行里被用到的模组钩子
        # 把玩家同步为"标准流程"下该年龄的阶段（旧存档/外部构造时兜底）
        if not self.player.stage or self.player.stage not in STAGE_BY_ID:
            self.player.stage = stage_of_age(self.player.age)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _log_delta(self, report):
        if self.log:
            self.log.daily(self.player, report.event_name or "日常",
                           "；".join(report.lines[:6]) or "平静的一天",
                           report.delta, report.ambient)

    def _money(self, amount, reason="", report=None):
        """统一的金钱收支入口（保持 2 位小数并统计）。"""
        self.player.money = round_money(self.player.money + amount)
        if amount > 0:
            self.player.stats["total_income"] = round_money(
                self.player.stats.get("total_income", 0.0) + amount)
        elif amount < 0:
            self.player.stats["total_expense"] = round_money(
                self.player.stats.get("total_expense", 0.0) - amount)

    # ------------------------------------------------------------------
    # 时间推进
    # ------------------------------------------------------------------
    def advance_calendar(self):
        """推进一天：处理跨月、跨年与生日。返回跨月结算信息列表。"""
        p = self.player
        p.day += 1
        p.total_days += 1
        notes = []

        if p.day > DAYS_PER_MONTH:
            p.day = 1
            p.month += 1
            notes.append(("month", p.month))
        if p.month > MONTHS_PER_YEAR:
            p.month = 1
            p.year += 1
            p.age += 1
            notes.append(("year", p.age))

        # 生日判定：出生日为 1 月 1 日，则每年 1 月 1 日过生日
        birthday = (p.month == p.birth_month and p.day == p.birth_day)
        return notes, birthday

    def settle_month(self, report):
        """每月初结算工资收入与固定生活支出。"""
        p = self.player
        # 未满 16 岁不可能拥有正式工作（防止异常状态导致的错误收入）
        if p.age < 16 and p.employed:
            p.employed = False
            p.job_level = 0
        month_income = 0.0
        month_expense = 0.0
        detail = []

        # ---- 收入 ----
        if p.age < 6:
            month_income = 0.0
            detail.append("未成年（%d 岁），由父母抚养，无收入" % p.age)
        elif p.age < 16:
            month_income = 100.0 + 10 * p.job_level
            detail.append("零花钱收入 %.0f" % month_income)
        else:
            if p.employed:
                base = BASE_WAGE + 700.0 * max(0, p.job_level - 1)
                base += 400.0 if p.job_level >= 4 else 0.0
                age_mod = 1.0
                if p.age < 22:
                    age_mod = 0.55
                elif p.age >= 60:
                    age_mod = 0.6
                month_income = round(base * age_mod, 2)
                detail.append("职级 %d 工资 %.2f" % (p.job_level, month_income))
            else:
                # 失业补助 / 打零工
                month_income = 200.0 if p.age >= 18 else 0.0
                detail.append("无业，打零工收入 %.0f" % month_income)
        if p.age >= 60 and p.employed:
            pension = 500.0
            month_income += pension
            detail.append("退休返聘补贴 %.0f" % pension)
        # 资产增值：长期积累也会带来一点被动收益（身价越高收益越多）
        if p.money > 100000:
            passive = round(p.money * 0.0015, 2)
            month_income += passive
            detail.append("资产收益 %.2f" % passive)

        # ---- 家庭支持（成年前 / 大学毕业前由父母承担开销）----
        support = family_support_amount(p)
        fname, fdesc, _fsup = family_tier(p.family_wealth)
        if support > 0:
            month_income += support
            p.stats["family_support_total"] = round_money(
                p.stats.get("family_support_total", 0.0) + support)
            detail.append("父母供养 %.2f（%s家庭：%s）" % (support, fname, fdesc))
        elif p.family_bankrupt and p.age < 22 and p.stage in FAMILY_SUPPORT_STAGES:
            detail.append("家庭已破产，父母无力再提供任何支持")
        elif p.left_home:
            detail.append("已离家独立，一切开销自负")

        # ---- 支出 ----
        city = get_city(p.city)
        month_expense = BASE_EXPENSE * city["cost_factor"]
        month_expense += 120.0 * p.children          # 子女抚养
        # 子女养育开销（按年龄递增：婴儿期最费钱）
        for child in (p.child_list or []):
            cage = self._child_age(child)
            factor = 0.6 if cage <= 2 else (1.0 if cage <= 6 else (1.3 if cage <= 15 else 0.8))
            month_expense += CHILD_MONTHLY_COST * factor
        if p.pregnant:
            month_expense += 800.0                   # 产检、营养、待产用品
        if p.married:
            month_expense *= 1.30
        if p.age < 16:
            month_expense *= 0.30                    # 由家庭承担大部分
        if p.age >= 22:
            # 生活水平随身价缓慢提高（避免金钱无限积累）
            wealth_factor = 1.0 + min(2.5, max(0.0, p.money) / 50000.0)
            month_expense *= wealth_factor
        if p.diseases:
            month_expense += 120.0 * len(p.diseases)  # 医药零碎开销
        # 读书阶段（大学/读研）会有一笔学杂费
        if p.stage == "university":
            month_expense += 300.0
        elif p.stage == "postgrad":
            month_expense += 200.0
        month_expense = round(month_expense, 2)
        detail.append("生活支出 %.2f（%s 消费系数 %.2f）" % (
            month_expense, city["name"], city["cost_factor"]))

        net = round(month_income - month_expense, 2)
        # 未成年 / 在读且家庭未破产时：父母兜底，保证孩子不会因为"不能挣钱"而负债累累
        if net < 0 and support > 0 and p.age <= 25:
            covered = round(min(-net, max(0.0, p.money + support * 2)), 2)
            if covered > 0:
                net += covered
                detail.append("父母替你垫付了 %.2f 的开销" % covered)
        delta, notes = p.apply_effects({"money": net}, dice=self.dice)
        report.accumulate(delta)
        for note in notes:
            report.add_line(note)
        report.add_line("本月结算：收入 %.2f，支出 %.2f，净变化 %s" % (
            month_income, month_expense, fmt_signed(net, 2)))
        for item in detail:
            report.add_line("    · %s" % item)
        if self.log:
            self.log.settlement(p, "收入 %.2f / 支出 %.2f（%s）" % (
                month_income, month_expense, "；".join(detail)))

    # ------------------------------------------------------------------
    # 家庭破产与人生阶段推进
    # ------------------------------------------------------------------
    def settle_family_phase(self, report):
        """
        家庭破产判定：每年一次，概率极低（万分位配置，默认每年约 3‰）。
        破产后父母不再提供任何经济支持。
        """
        p = self.player
        if p.family_bankrupt or p.left_home:
            return
        if p.age < FAMILY_BANKRUPTCY_MIN_AGE or p.age > 25:
            return
        if not (p.month == p.birth_month and p.day == p.birth_day):
            return
        roll = self.dice.roll(10000, 1, 0, "家庭变故判定")
        self.dice.remember(roll, "家庭变故判定")
        threshold = FAMILY_BANKRUPTCY_PERMILLE * 10    # 3‰ = 30/10000
        # 家境越差，越容易出变故
        if p.family_wealth < 30:
            threshold = int(threshold * 2.2)
        elif p.family_wealth < 50:
            threshold = int(threshold * 1.4)
        if roll.value <= threshold:
            p.family_bankrupt = True
            msg = "【家庭变故】家中生意失败/负债累累，家庭破产了。从此父母无法再提供经济支持。"
            p.family_notes.append(p.date_full + " 家庭破产")
            p.add_milestone("家庭破产（%d 岁）" % p.age, tag="家庭")
            report.add_line(msg)
            delta, _ = p.apply_effects({"happy": -18}, dice=self.dice)
            report.accumulate(delta)
            if self.log:
                self.log.milestone(p, "家庭破产，家中再也拿不出钱", "家庭")
        else:
            report.add_line("家庭平安（变故判定 %d > %d）" % (roll.value, threshold))

    def advance_stage(self, report):
        """
        人生阶段推进：按年龄与考试结果推进
        学龄前 -> 幼儿园 -> 小学 -> 初中 -> 中考 -> 高中 -> 高考 -> 大学(有概率不上)
        -> 读研(有概率读不上) -> 工作 -> 退休
        """
        p = self.player
        stage = STAGE_BY_ID.get(p.stage) or STAGE_BY_ID["infant"]
        end_age = stage.get("end", 200)
        if p.age <= end_age:
            return
        nxt = stage.get("next")
        if not nxt:
            return
        # ---- 中考 / 高考 / 考研的分支判定 ----
        if stage.get("exam") == "zhongkao":
            ok = self._roll_exam("zhongkao", report)
            p.exam_results["zhongkao"] = "考上高中" if ok else "没考上高中"
            if not ok:
                # 没考上高中 -> 辍学打工
                self.change_stage("dropout", report, "中考失利，你提前离开校园")
                return
        elif stage.get("exam") == "gaokao":
            ok = self._roll_exam("gaokao", report)
            p.university_ok = ok
            p.exam_results["gaokao"] = "考上大学" if ok else "落榜"
            if not ok:
                self.change_stage("work", report, "高考落榜，你提前进入社会")
                return
        elif p.stage == "university":
            # 大学毕业：有概率继续读研（受家境与学业表现影响）
            ok = self._roll_exam("postgrad", report)
            p.postgrad_ok = ok
            if ok:
                self.change_stage("postgrad", report, "你考上了研究生")
                return
            p.exam_results["postgrad"] = "未考研/未考上"
            self.change_stage("work", report, "你大学毕业，开始工作")
            return
        elif p.stage == "postgrad":
            self.change_stage("work", report, "研究生毕业，你正式进入职场")
            return

        self.change_stage(nxt, report, None)

    def _roll_exam(self, exam, report):
        """
        考试判定：d100 + 学业加成 >= 目标值。
        学业表现（study_points）来自「学习充电」操作与相关事件：
            约每 40 点学业表现 +1 分，最多 +25 分
            家境好则额外 +0~4 分，健康差则 -8 分
        目标值：中考 45 / 高考 52 / 考研 58（"不学习就考不上"是合理的）
        """
        p = self.player
        target_map = {"zhongkao": 45, "gaokao": 52, "postgrad": 58}
        target = target_map.get(exam, 50)
        bonus = min(25, int(p.stats.get("study_points", 0) // 40))
        bonus += int(max(0, (p.family_wealth - 50)) // 12)
        if p.health < 50:
            bonus -= 8
        roll = self.dice.d100("考试判定")
        self.dice.remember(roll, "%s判定" % {"zhongkao": "中考", "gaokao": "高考",
                                             "postgrad": "考研"}.get(exam, exam))
        total = roll.value + bonus
        ok = total >= target
        report.add_line("考试判定：骰子 %d + 学业/家境加成 %d = %d，目标 %d → %s" % (
            roll.value, bonus, total, target, "通过" if ok else "未通过"))
        return ok

    def change_stage(self, stage_id, report=None, note=None):
        """切换人生阶段，并记录学历。"""
        p = self.player
        if stage_id not in STAGE_BY_ID:
            return
        old = p.stage
        p.stage = stage_id
        meta = STAGE_BY_ID[stage_id]
        p.stage_history.append({
            "date": p.date_full, "age": p.age,
            "from": old, "to": stage_id, "name": meta["name"],
        })
        edu_map = {"primary": "小学", "middle": "初中", "high": "高中",
                   "university": "大学", "postgrad": "研究生"}
        if stage_id in edu_map and edu_map[stage_id] not in p.education:
            p.education.append(edu_map[stage_id])
        if stage_id == "work" and not p.employed:
            p.employed = True
            p.job_level = max(1, p.job_level)
        if stage_id in ("retired",):
            p.employed = False
        text = "【人生阶段】%d 岁：进入「%s」——%s" % (p.age, meta["name"], meta["desc"])
        if note:
            text = "【人生阶段】%d 岁：%s（%s）" % (p.age, note, meta["name"])
        p.add_milestone("进入%s阶段" % meta["name"], tag="阶段")
        if report is not None:
            report.add_line(text)
        if self.log:
            self.log.milestone(p, text.replace("【人生阶段】", ""), "阶段")

    def auto_progress_stages(self, report):
        """连续推进阶段（时间跳跃后可能出现跨多个阶段的情况）。"""
        for _ in range(8):
            before = self.player.stage
            self.advance_stage(report)
            if self.player.stage == before:
                break
            if self.player.dead:
                break

    # ------------------------------------------------------------------
    # 环境与疾病每日结算
    # ------------------------------------------------------------------
    def roll_ambient(self):
        """投掷当日气温并写入人物状态。"""
        p = self.player
        ambient, res = roll_ambient_temp(self.dice, p.city, p.month)
        p.ambient_temp = ambient
        self.dice.remember(res, "当日气温")
        return ambient, res

    def settle_disease_phase(self, report):
        """疾病按天结算：扣血、扣幸福、影响体温、自愈与死亡风险。"""
        p = self.player
        if not p.diseases:
            return
        # 体质影响每日扣血（体质弱的人病得更重）
        sus = constitution_susceptibility(p.constitution)
        hp_factor = round((0.75 + 0.25 * sus) * DISEASE_HEALTH_IMPACT, 3)
        # 怀孕期间用药受限，病情更难受
        if p.pregnant:
            hp_factor = round(hp_factor * 1.15, 3)
        for disease in list(p.diseases):
            hp_loss = round(disease["hp_per_day"] * hp_factor, 2)
            happy_loss = disease["happy_per_day"]
            delta, _ = p.apply_effects({"health": -hp_loss, "happy": -happy_loss,
                                        "temp": disease["temp_mod"]}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("%s 发作：健康 %s，幸福 %s，体温 %s" % (
                disease["name"], fmt_signed(delta["health"], 1),
                fmt_signed(delta["happy"], 1), fmt_signed(delta["temp"], 2)))

            # 自愈判定
            if disease["self_heal"] > 0:
                roll = self.dice.d100("自愈判定")
                self.dice.remember(roll, "%s自愈判定" % disease["name"])
                if roll.value <= disease["self_heal"] * 100:
                    p.diseases.remove(disease)
                    report.add_line("你的%s自愈了（骰子 %d ≤ %d）。" % (
                        disease["name"], roll.value, int(disease["self_heal"] * 100)))
                    if self.log:
                        self.log.disease(p, "%s 自愈" % disease["name"])
                    continue

            disease["days"] -= 1
            if disease["days"] <= 0:
                if disease["needs_cure"]:
                    # 慢性病不治疗会一直存在，只是每 10 天"提醒"一次
                    disease["days"] = 10
                    report.add_line("慢性病仍在持续，建议尽快治疗。")
                else:
                    p.diseases.remove(disease)
                    report.add_line("你的%s已经痊愈。" % disease["name"])
                    if self.log:
                        self.log.disease(p, "%s 痊愈" % disease["name"])

            # 危重疾病致死判定
            if disease.get("fatal") and p.health <= 25:
                roll = self.dice.d20("危重判定")
                self.dice.remember(roll, "危重判定")
                if roll.value <= 6:
                    report.add_line("病情危重，骰子判定失败……")
                    self.kill("因%s病情恶化，抢救无效" % disease["name"], report)
                    return

    def settle_env_phase(self, report):
        """环境结算：体温回归/偏移 + 体温异常每日扣血。"""
        p = self.player
        drift, desc, res = temperature_adjust(self.dice, p)
        self.dice.remember(res, "体温变动")
        delta, _ = p.apply_effects({"temp": drift}, dice=self.dice)
        report.accumulate(delta)
        if abs(delta["temp"]) >= 0.05:
            report.add_line("体温变动 %s%s" % (fmt_signed(delta["temp"], 2),
                                           ("（%s）" % desc) if desc else ""))

        # 体温异常 → 每日扣健康
        if p.temp > TEMP_NORMAL_HIGH:
            excess = p.temp - TEMP_NORMAL_HIGH
            loss = 1.6 + excess * 2.0
            if p.temp >= 39.0:
                loss += 3.5
            delta, _ = p.apply_effects({"health": -loss}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("体温过高（%.1f℃）→ 健康 %s" % (p.temp, fmt_signed(delta["health"], 1)))
        elif p.temp < TEMP_NORMAL_LOW:
            deficit = TEMP_NORMAL_LOW - p.temp
            loss = 1.6 + deficit * 2.0
            if p.temp <= 35.0:
                loss += 3.5
            delta, _ = p.apply_effects({"health": -loss}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("体温过低（%.1f℃）→ 健康 %s" % (p.temp, fmt_signed(delta["health"], 1)))

    def settle_recover_phase(self, report):
        """
        自然恢复：没有生病时身体会缓慢回血；带病期间恢复能力大幅下降，
        因此"生病了要休息/看病"才是正确策略。
        每日回血有上限（收益递减），避免数值无限膨胀。
        """
        p = self.player
        if p.health >= HEALTH_MAX:
            return
        gain = 0.8
        if p.diseases:
            gain *= 0.25           # 病中恢复极慢
        if p.temp < TEMP_NORMAL_LOW or p.temp > TEMP_NORMAL_HIGH:
            gain *= 0.4            # 体温异常时恢复变差
        if 16 <= p.age < 40:
            gain -= 0.2            # 成年后不再有童年红利
        if p.age <= 12:
            gain += 0.3            # 孩子恢复得更快
        elif p.age >= 55:
            gain -= 0.25           # 年长者恢复更慢
        if p.happy >= 70:
            gain += 0.3
        elif p.happy < LOW_HAPPY_THRESHOLD:
            gain -= 0.2
        if p.health < 10:
            gain += 0.8            # 危急时身体全力自救
        # 健康越高，自然恢复越慢（收益递减，避免长期顶格）
        if p.health >= 90:
            gain *= 0.4
        elif p.health >= 75:
            gain *= 0.7
        gain = max(0.15, gain)
        delta, _ = p.apply_effects({"health_boost": gain}, dice=self.dice)
        if delta["health"] > 0.01:
            report.accumulate(delta)
            report.add_line("自然恢复：健康 %s" % fmt_signed(delta["health"], 1))

    def settle_hospital_phase(self, report):
        """
        医院抢救：健康跌破危险线时自动送医治疗最严重的疾病。
          * 钱够 -> 直接付清
          * 钱不够 -> 允许按医保赊账一部分（最多自付一半），既避免必死，也带来负债压力
        另外给低健康角色一点紧急缓冲，避免"毫无操作空间地被病死"。
        """
        p = self.player
        if p.dead:
            return False
        # 危急缓冲：健康跌破 5 时，身体会强制保住最后一线生机（每天一次）
        if 0 < p.health < 5:
            delta, _ = p.apply_effects({"health_boost": 2.0}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("【求生本能】你强撑着没有倒下（健康 %s）" % fmt_signed(delta["health"], 1))
        if not p.diseases or p.health > 12:
            return False
        target = p.worst_disease()
        if target is None:
            return False
        cost = float(target["cure_cost"])
        if p.money >= cost:
            ok, msg, paid = p.cure_disease(target["id"])
        else:
            ok, msg = False, ""
            need = round(cost * 0.5, 2)
            if p.money + need >= cost:
                # 医保/亲友垫付：先借钱付清，形成负债
                borrow = round(cost - p.money, 2)
                p.money = round_money(p.money + borrow)
                p.stats["total_income"] = round_money(
                    p.stats.get("total_income", 0.0) + borrow)
                p.stats["debt"] = round_money(p.stats.get("debt", 0.0) + borrow)
                ok, msg, paid = p.cure_disease(target["id"])
                if ok:
                    msg += "（向亲友/医保借款 %.2f 支付了医药费）" % borrow
        if ok:
            p.stats["hospital_count"] = p.stats.get("hospital_count", 0) + 1
            report.add_line("【紧急送医】健康跌至 %.1f，你被送进医院：%s" % (p.health, msg))
            if self.log:
                self.log.disease(p, "紧急送医治愈%s" % target["name"])
            p.add_milestone("紧急送医：治愈%s" % target["name"], tag="疾病")
            return True
        return False

    def natural_death_roll(self, report):
        """
        自然寿命判定：每年生日掷一次"生死骰"（d100）。
        死亡率随年龄指数上升，目标是把角色的平均寿命稳定在 80 岁左右。
        返回 True 表示本轮判定死亡。
        """
        p = self.player
        if p.age < NATURAL_DEATH_START:
            return False
        rate = natural_death_rate(p.age, p.health, p.diseases)
        roll = self.dice.d100("寿命判定")
        self.dice.remember(roll, "%d 岁寿命判定" % p.age)
        report.add_line("寿命判定：%d 岁，本年自然死亡概率 %.1f%%，骰子 %d" % (
            p.age, rate * 100.0, roll.value))
        if roll.value <= rate * 100.0:
            self.kill("寿终正寝，享年 %d 岁（自然衰老）" % p.age, report)
            return True
        return False

    def settle_aging_phase(self, report):
        """
        衰老阶段：
          * 45 岁之后健康上限逐年降低（上限 = 100 - 每岁 0.35，最低 55）
          * 60 岁后每天有衰老损耗，年龄越大损耗越快
        """
        p = self.player
        if p.age >= NATURAL_DEATH_START and p.month == p.birth_month and p.day == p.birth_day:
            if self.natural_death_roll(report):
                return
        if p.age < 45:
            return
        # 健康上限随年龄降低
        cap = max(55.0, HEALTH_MAX - (p.age - 45) * 0.35)
        if p.health > cap:
            cut = round(min(p.health - cap, 1.2), 2)
            delta, _ = p.apply_effects({"health": -cut}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("岁月痕迹：健康上限降至 %.0f（健康 %s）" % (cap, fmt_signed(delta["health"], 1)))
        # 60 岁之后每天自然衰老损耗
        if p.age >= 60:
            loss = 0.5 + (p.age - 60) * 0.06
            delta, _ = p.apply_effects({"health": -round(loss, 2)}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("年老体衰：健康 %s" % fmt_signed(delta["health"], 1))

    # ------------------------------------------------------------------
    # 家庭 / 生育系统
    # ------------------------------------------------------------------
    def can_be_intimate(self):
        """
        检查能否进行「夫妻亲密」，返回 (是否允许, 提示文本)。
        现实向限制：成年 + 已婚（或有伴侣）+ 不在孕期 + 每天最多 1 次。
        """
        p = self.player
        if p.dead:
            return False, "人物已经离世。"
        if p.age < INTIMACY_MIN_AGE:
            return False, "还没有成年（需 %d 岁以上）。" % INTIMACY_MIN_AGE
        if not p.married and not p.partner_name:
            return False, ("你还是单身。\n\n"
                           "需要先经历恋爱、结婚（16 岁后可恋爱，22 岁后可结婚）。")
        if p.pregnant:
            return False, "伴侣正在孕期，医生建议静养。"
        if getattr(p, "intimacy_today", 0) >= INTIMACY_MAX_PER_DAY:
            return False, "今天已经有过亲密时光了，注意身体。"
        if p.health < 20:
            return False, "身体太虚弱了，先养好身体吧。"
        return True, ""

    def do_intimacy(self, contraception=None):
        """
        「夫妻亲密」：提升幸福度，并按概率受孕（可指定避孕方式）。
        返回结果卡 dict。
        """
        p = self.player
        ok, why = self.can_be_intimate()
        if not ok:
            return {"tone": "warn", "text": why}
        report = DailyReport(p)
        report.event_name = "夫妻亲密"
        if contraception is not None and contraception in [o[0] for o in CONTRACEPTION_OPTIONS]:
            p.contraception = contraception

        # ---- 幸福提升 ----
        happy_gain = INTIMACY_HAPPY_BASE
        if p.married:
            happy_gain += INTIMACY_HAPPY_MARRIED_BONUS
        if p.health >= 70:
            happy_gain += 2
        if p.happy < 40:
            happy_gain += 2      # 情绪低落时安慰作用更明显
        roll = self.dice.d10("亲密感受")
        self.dice.remember(roll, "亲密感受")
        if roll.value >= 8:
            happy_gain += 3
            report.add_line("你们聊了很久，彼此都觉得更亲近了。")
        elif roll.value <= 2:
            happy_gain = max(2, happy_gain - 3)
            report.add_line("今天两人都有些疲惫，只是安静地靠在一起。")
        delta, _ = p.apply_effects({"happy": happy_gain, "health": +1}, dice=self.dice)
        report.accumulate(delta)
        p.intimacy_today = p.intimacy_today + 1
        p.intimacy_last_day = p.total_days
        report.add_line("亲密时光：幸福 %s，健康 %s（避孕方式：%s）" % (
            fmt_signed(delta["happy"], 1), fmt_signed(delta["health"], 1), p.contraception))

        # ---- 受孕判定 ----
        conceive, note = self._try_conceive()
        report.add_line(note)
        if conceive:
            report.add_line("例假迟迟没来，你们买了验孕棒——两条杠。")
            p.add_milestone("确认怀孕（%d 岁）" % p.age, tag="生育")
            if self.log:
                self.log.milestone(p, "确认怀孕", "生育")
        self.last_report = report
        return {
            "tone": "intimacy",
            "title": "夫妻亲密",
            "report": report,
            "settlement_lines": list(report.lines),
            "dice_lines": self.dice.today_lines(),
            "conceived": conceive,
            "action_points": p.action_points,
        }

    def _try_conceive(self):
        """
        受孕判定：年龄 + 避孕成功率 + 已生育数量 + 健康状况。
        返回 (是否受孕, 说明文本)
        """
        p = self.player
        if p.pregnant:
            return False, "目前已在孕期中。"
        if p.age < CONCEPTION_MIN_AGE:
            return False, "年龄还太小，暂时不考虑生育。"
        if p.age > CONCEPTION_MAX_AGE_FEMALE:
            return False, "医学上已过最佳生育年龄，很难再怀孕（%d 岁）。" % p.age
        if len(p.child_list) >= MAX_CHILDREN:
            return False, "家里孩子已经很多了，再添一个实在养不起。"
        base = conception_rate(p.age)
        rate_map = {name: success for name, success, _desc in CONTRACEPTION_OPTIONS}
        protect = rate_map.get(p.contraception, 0.0)
        chance = base * (1.0 - protect)
        if p.health < 50:
            chance *= 0.6
        if p.happy < LOW_HAPPY_THRESHOLD:
            chance *= 0.7
        if len(p.child_list) >= 2:
            chance *= 0.6 ** (len(p.child_list) - 1)   # 孩子越多越不容易再怀
        roll = self.dice.roll(10000, 1, 0, "受孕判定")
        self.dice.remember(roll, "受孕判定")
        threshold = chance * 10000.0
        if roll.value <= max(0.5, threshold):
            p.pregnant = True
            p.pregnancy_days = 0
            p.pregnancy_count += 1
            p.conception_history.append({
                "date": p.date_full, "age": p.age,
                "contraception": p.contraception,
            })
            return True, "受孕判定：%d ≤ %.0f（避孕方式：%s）→ 怀孕了！" % (
                roll.value, threshold, p.contraception)
        return False, "受孕判定：%d > %.0f（避孕方式：%s）→ 这次没有怀上。" % (
            roll.value, threshold, p.contraception)

    def settle_pregnancy_phase(self, report):
        """
        孕期结算：每"月"推进一次，9 个月（270 天）后分娩。
        期间有孕期反应、流产风险与分娩风险，孩子会继承父母体质。
        """
        p = self.player
        if not p.pregnant or p.dead:
            return
        p.pregnancy_days += 1
        if p.pregnancy_days % DAYS_PER_MONTH != 0:
            return
        month = p.pregnancy_days // DAYS_PER_MONTH
        roll = self.dice.d10("孕期反应")
        self.dice.remember(roll, "孕期反应")
        if month <= 3:
            if roll.value <= 6:
                delta, _ = p.apply_effects({"health": -1.2, "happy": -2}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("孕期第 %d 月：孕吐反应明显，健康 %s、幸福 %s" % (
                    month, fmt_signed(delta["health"], 1), fmt_signed(delta["happy"], 1)))
            else:
                report.add_line("孕期第 %d 月：反应不重，一切正常。" % month)
        elif month <= 6:
            delta, _ = p.apply_effects({"happy": +3, "health": -0.5}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("孕期第 %d 月：肚子一天天大起来，家里开始准备婴儿用品。" % month)
        else:
            if roll.value <= 4:
                delta, _ = p.apply_effects({"health": -2, "happy": -2}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("孕期第 %d 月：腰酸背痛、睡不好，健康 %s" % (
                    month, fmt_signed(delta["health"], 1)))
            else:
                report.add_line("孕期第 %d 月：产检一切正常，医生说随时可能发动。" % month)

        # ---- 流产风险（年龄越大、健康越差越高）----
        if month <= 4:
            risk = birth_risk(p.age) * 0.35 + (0.03 if p.health < 50 else 0.0)
            check = self.dice.roll(10000, 1, 0, "流产判定")
            if check.value <= risk * 10000.0:
                p.pregnant = False
                p.pregnancy_days = 0
                p.miscarriage += 1
                delta, _ = p.apply_effects({"health": -6, "happy": -18}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("【不幸】孕期第 %d 月发生了流产。健康 %s、幸福 %s" % (
                    month, fmt_signed(delta["health"], 1), fmt_signed(delta["happy"], 1)))
                p.add_milestone("流产（%d 岁）" % p.age, tag="生育")
                if self.log:
                    self.log.milestone(p, "流产", "生育")
                return

        # ---- 到预产期：分娩 ----
        if p.pregnancy_days >= PREGNANCY_DAYS:
            self._deliver(report)

    def _deliver(self, report):
        """分娩：判定并发症与孩子情况，生成孩子档案并加入家庭。"""
        p = self.player
        risk = birth_risk(p.age)
        if p.health < 50:
            risk *= 1.5
        if p.diseases:
            risk *= 1.3
        roll = self.dice.roll(10000, 1, 0, "分娩判定")
        self.dice.remember(roll, "分娩判定")
        p.pregnant = False
        p.pregnancy_days = 0
        p.birth_count += 1
        gender_roll = self.dice.roll(2, 1, 0, "性别判定")
        baby_gender = "男孩" if gender_roll.value == 1 else "女孩"
        baby_name = self.dice.pick(CHILD_NAME_POOL, "取名")[0]
        # 孩子体质：父母体质均值 + 随机波动（体现遗传）
        base_con = (p.constitution + CONSTITUTION_MEAN) / 2.0
        inherit = self.dice.roll(10000, 1, 0, "体质遗传")
        baby_con = max(CONSTITUTION_MIN, min(CONSTITUTION_MAX,
                                            base_con + (inherit.value - 5000) / 420.0))
        child = {
            "name": baby_name, "gender": baby_gender,
            "birth_date": p.date_full, "constitution": round(baby_con, 1),
            "mother_age": p.age,
        }
        p.child_list.append(child)
        p.children = len(p.child_list)
        happy_gain = 22
        health_cost = 6.0
        if roll.value <= risk * 10000.0:
            severity = self.dice.d10("并发症程度").value
            if severity >= 8:
                health_cost += 14
                happy_gain = 8
                report.add_line("【难产】分娩过程中出现并发症，母子都经历了危险。")
            else:
                health_cost += 6
                happy_gain = 14
                report.add_line("【并发症】分娩不太顺利，好在医生处理及时。")
        delta, _ = p.apply_effects({"health": -health_cost, "happy": happy_gain,
                                    "money": -3000.0}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("【喜讯】%s出生了（%s，先天体质 %.1f 分）。" % (
            baby_name, baby_gender, baby_con))
        report.add_line("分娩消耗：健康 %s，幸福 %s，生育与住院花费约 3000" % (
            fmt_signed(delta["health"], 1), fmt_signed(delta["happy"], 1)))
        p.add_milestone("孩子出生：%s（%s）" % (baby_name, baby_gender), tag="生育")
        if self.log:
            self.log.milestone(p, "孩子出生：%s（%s，体质 %.1f）" % (
                baby_name, baby_gender, baby_con), "生育")

    def settle_child_phase(self, report):
        """子女成长结算：每年生日时给出孩子的成长反馈（影响父母幸福）。"""
        p = self.player
        if not p.child_list:
            return
        if not (p.month == p.birth_month and p.day == p.birth_day):
            return
        for child in p.child_list:
            age = self._child_age(child)
            if age in (1, 3, 6, 12, 18):
                roll = self.dice.d10("孩子成长")
                if roll.value >= 7:
                    delta, _ = p.apply_effects({"happy": +4}, dice=self.dice)
                    report.accumulate(delta)
                    report.add_line("%s 今年 %d 岁了，懂事又健康，你心里很满足。" % (
                        child["name"], age))
                else:
                    delta, _ = p.apply_effects({"happy": -2, "money": -300}, dice=self.dice)
                    report.accumulate(delta)
                    report.add_line("%s 今年 %d 岁了，正是最费心的时候。" % (
                        child["name"], age))
                if age == 18:
                    p.add_milestone("%s 成年了" % child["name"], tag="家庭")
                    if self.log:
                        self.log.milestone(p, "%s 成年了" % child["name"], "家庭")

    def _child_age(self, child):
        """按"出生时母亲年龄"推算孩子当前年龄（稳健，不依赖日期解析）。"""
        mother_age = int(child.get("mother_age", 0))
        return max(0, self.player.age - mother_age)

    def children_summary(self):
        """子女概览文本。"""
        p = self.player
        if not p.child_list:
            return "暂无子女"
        lines = []
        for child in p.child_list:
            lines.append("    · %s（%s）%d 岁，先天体质 %.1f 分，出生于 %s" % (
                child.get("name", "孩子"), child.get("gender", "未知"),
                self._child_age(child), child.get("constitution", 50.0),
                child.get("birth_date", "")))
        return "\n".join(lines)

    def settle_mood_phase(self, report):
        """幸福过低 debuff：长期低于阈值会持续扣健康。"""
        p = self.player
        if p.happy < LOW_HAPPY_THRESHOLD:
            loss = 2.5 + (LOW_HAPPY_THRESHOLD - p.happy) * 0.25
            delta, _ = p.apply_effects({"health": -loss}, dice=self.dice)
            report.accumulate(delta)
            report.add_line("幸福过低（%.1f < %d）→ 抑郁侵蚀健康 %s" % (
                p.happy, LOW_HAPPY_THRESHOLD, fmt_signed(delta["health"], 1)))
        # 幸福自然回落（避免长期顶格）
        if p.happy > 90:
            p.happy = clamp_happy(p.happy - 0.6)

    def settle_carried(self, report):
        """跨天持续效果结算（例如寒潮后的体温趋势）。"""
        p = self.player
        remain = []
        for item in p.carried_effects:
            value = float(item.get("value", 0))
            if item.get("type") == "temp_drift":
                delta, _ = p.apply_effects({"temp": value}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("%s：体温 %s" % (item.get("name", "持续效果"),
                                              fmt_signed(delta["temp"], 2)))
            elif item.get("type") == "health":
                delta, _ = p.apply_effects({"health": value}, dice=self.dice)
                report.accumulate(delta)
                report.add_line("%s：健康 %s" % (item.get("name", "持续效果"),
                                              fmt_signed(delta["health"], 1)))
            item["days"] = int(item.get("days", 1)) - 1
            if item["days"] > 0:
                remain.append(item)
        p.carried_effects = remain

    def check_death(self, report):
        """死亡判定：健康归零、体温极端、年龄过大自然衰老。"""
        p = self.player
        if p.dead:
            return True
        if p.health <= HEALTH_MIN:
            if p.diseases:
                reason = "因%s导致身体机能衰竭" % p.worst_disease()["name"]
            elif p.temp >= TEMP_NORMAL_HIGH:
                reason = "因持续高热导致器官衰竭"
            elif p.temp < TEMP_NORMAL_LOW:
                reason = "因长期失温导致心脏骤停"
            elif p.happy < LOW_HAPPY_THRESHOLD:
                reason = "因长期抑郁、身心俱疲而离世"
            else:
                reason = "因健康状况持续恶化而离世"
            self.kill(reason, report)
            return True
        if p.temp >= TEMP_HARD_HIGH - 0.5 or p.temp <= TEMP_HARD_LOW + 0.5:
            self.kill("体温达到极端值（%.1f℃），生命体征消失" % p.temp, report)
            return True
        if p.age >= AGE_MAX_LIMIT:
            self.kill("寿终正寝，享年 %d 岁" % p.age, report)
            return True
        return False

    def kill(self, reason, report=None):
        """人物死亡：写入状态与日志。"""
        p = self.player
        if p.dead:
            return
        p.dead = True
        p.health = 0.0
        p.death_reason = reason
        p.death_date = p.date_full
        p.add_milestone("离世：%s" % reason, tag="死亡")
        if report is not None:
            report.death = True
            report.add_line("【死亡】%s" % reason)
        if self.log:
            self.log.death(p, reason)
        self.game_over = True

    # ------------------------------------------------------------------
    # 每日事件抽取
    # ------------------------------------------------------------------
    def roll_illness_opportunity(self):
        """
        每日"生病机会"判定（与普通事件独立）：
          * 概率 = sickness_probability(player)（含体质、年龄 U 型曲线、状态、城市）
          * 受"生病最短间隔"限制（默认 25 天），避免一个月生好几次病
          * 体质越好概率越低；当天的"锻炼身体"操作有额外保护
        返回 (是否生病, DiceResult 或 None, 说明文本)
        """
        p = self.player
        if not illness_gap_ok(p):
            return False, None, "距上次生病不足 %d 天，本次跳过患病判定" % MIN_ILLNESS_GAP_DAYS
        prob = sickness_probability(p)
        # 锻炼身体的保护效果（当天每锻炼一次约 -25%，最多 -60%）
        exercise = int((p.stats or {}).get("exercise_today", 0) or 0)
        if exercise > 0:
            prob *= max(0.40, 0.75 ** exercise)
        roll = self.dice.roll(10000, 1, 0, "生病机会判定")
        self.dice.remember(roll, "生病机会判定（万分位）")
        if roll.value <= max(1.0, prob * 10000.0):
            return True, roll, "生病机会判定通过（%d ≤ %.1f）：今天身体有些不舒服" % (
                roll.value, prob * 10000.0)
        return False, roll, "身体无恙（生病机会判定 %d > %.1f）" % (
            roll.value, prob * 10000.0)

    def step_roll(self):
        """
        「推进一天」：
            时间 +1 天 → 跨月/跨年结算 → 生病机会判定 → 掷骰抽事件
            → 重置行动点 → 返回待决策事件卡（一天最多触发一次事件）。
        返回 dict(tone="event" / "nothing" / "dead", ...)
        """
        if self.player.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        # 上一张卡未处理完时不允许重复推进
        if self.pending is not None:
            return {"tone": "nothing", "text": "请先处理完当前事件。"}
        self.dice.reset_today()
        self.pending_followup = None
        p = self.player
        report = DailyReport(p)
        events_notes, birthday = self.advance_calendar()
        p.days_played += 1
        p.stats["days_played"] = p.stats.get("days_played", 0) + 1

        # ---- 跨年 / 跨月提示 ----
        for kind, value in events_notes:
            if kind == "month":
                self.settle_month(report)
                self.settle_family_phase(report)
                p.add_milestone("进入第 %d 月" % value, tag="时间")
            elif kind == "year":
                self.log and self.log.milestone(p, "满 %d 岁" % p.age, "年龄")
                p.add_milestone("满 %d 岁" % p.age, tag="年龄")
                report.add_line("★ 你满 %d 岁了（%s阶段：%s）。" % (
                    p.age, stage_name(p.stage), STAGE_BY_ID[p.stage]["desc"]))

        # ---- 生日事件 ----
        forced_event = None
        if birthday:
            forced_event = EVENTS["secret_birthday"]
            p.add_milestone("生日（%d 岁）" % p.age, tag="生日")
            if self.log:
                self.log.milestone(p, "生日，%d 岁" % p.age, "生日")

        # ---- 环境 / 持续效果结算 ----
        self.roll_ambient()
        self.settle_carried(report)
        # ---- 人生阶段推进（生日后可能升学/毕业）----
        self.auto_progress_stages(report)
        if self.check_death(report):
            self.last_report = report
            self.pending = None
            self._log_delta(report)
            return {"tone": "dead", "text": "\n".join(report.lines), "report": report}

        # ---- 新的一天：重置行动点（游戏内同一天最多 8 次操作）----
        p.action_points = ACTION_POINTS_PER_DAY
        p.actions_today = 0
        p.action_tally = {}
        p.stats.pop("exercise_today", None)

        # ---- 抽取今日事件 ----
        pick = None
        illness_note = ""
        if forced_event is None:
            # 1) 生病机会（独立的每日判定，遵守最短间隔）
            sick, iroll, illness_note = self.roll_illness_opportunity()
            report.add_line(illness_note)
            if sick:
                illness_event = self._pick_illness_event()
                if illness_event is not None:
                    pick = {"event": illness_event, "category": "疾病",
                            "roll": iroll, "secret_reason": None,
                            "internal": illness_event["id"], "no_event": False}
            # 2) 普通事件（万分位精度：先判"今天有没有事"）
            if pick is None:
                pick = roll_daily_event(self.dice, p, engine=self)

        if forced_event is not None:
            pick = {"event": forced_event, "category": "隐藏",
                    "roll": self.dice.d100("生日事件"),
                    "secret_reason": "今天是你的生日，触发特殊事件。",
                    "internal": forced_event["id"], "no_event": False}

        event = pick.get("event") if pick else None
        if event is None:
            p.plain_days += 1
            chance = pick.get("chance") if pick else None
            report.add_line("今天什么也没有发生，日子平静地流过。")
            if chance is not None:
                report.add_line("（当日事件概率 %.2f%%，判定结果：无事发生）" % (chance * 100))
            report.event_name = "平静的一天"
            p.remember_event("平静的一天", "日常", "无事件")
            self.last_report = report
            self._log_delta(report)
            return {"tone": "nothing", "text": "\n".join(report.lines),
                    "report": report, "action_points": p.action_points,
                    "illness_note": illness_note}

        desc = self.dice.pick(event["descs"], "事件描述")[0] if len(event["descs"]) > 1 else event["descs"][0]
        desc = desc.replace("{name}", p.name).replace("{age}", str(p.age))
        report.event_name = event["name"]
        p.remember_event(event["name"], event["category"], desc)
        # 记录同类事件冷却
        if event["category"] in CATEGORY_BANDS_NAMES:
            self.category_last_day[event["category"]] = p.total_days

        card = {
            "tone": "event",
            "report": report,
            "event_id": event["id"],
            "event_name": event["name"],
            "category": event["category"],
            "tone_color": TRUE_TONE_COLORS.get(event["tone"], "#f0c040"),
            "special": event["special"],
            "desc": desc,
            "choices": [],
            "secret_reason": pick.get("secret_reason"),
            "roll_lines": self.dice.today_lines(),
            "settlement_lines": list(report.lines),
            "action_points": p.action_points,
            "illness_note": illness_note,
        }

        for idx, choice in enumerate(event["choices"]):
            hints = describe_effects(choice.get("outcomes", [{}])[0].get("effects", {}))
            card["choices"].append({
                "index": idx,
                "label": choice["label"],
                "hint": choice.get("hint", ""),
                "detail": "、".join(hints),
                "need_money": choice.get("need_money", 0),
                "need_disease": choice.get("need_disease", False),
                "roll": choice.get("roll", "d6"),
            })
        self.pending = {"event": event, "card": card, "report": report,
                        "followup": None}
        return card

    def _pick_illness_event(self):
        """
        生病机会命中时，挑选一个合适的疾病类事件（作为当天的"不舒服"叙事入口）。
        优先挑选轻症事件（感冒/肠胃/流感），重症留给事件链。
        """
        p = self.player
        candidates = []
        for eid in ("illness_cold", "illness_gastro", "illness_seasonal",
                    "illness_frostbite", "illness_heatstroke", "illness_pneumonia",
                    "illness_chronic", "baby_sick_care"):
            ev = EVENTS.get(eid)
            if ev is None:
                continue
            try:
                if not ev["cond"](p):
                    continue
            except Exception:
                continue
            # 重症/慢性病只在体质弱或年纪大时才优先
            if eid in ("illness_pneumonia", "illness_chronic"):
                if not (p.constitution < 35 or p.age >= 60 or p.age <= 3):
                    continue
            candidates.append(ev)
        if not candidates:
            return None
        # 用权重抽取（轻症权重更高）
        weights = {"illness_cold": 40, "illness_gastro": 25, "illness_seasonal": 20,
                   "illness_frostbite": 12, "illness_heatstroke": 12,
                   "illness_pneumonia": 8, "illness_chronic": 6, "baby_sick_care": 30}
        total = float(sum(weights.get(e["id"], 10) for e in candidates))
        res = self.dice.roll(10000, 1, 0, "疾病类型挑选")
        target = (res.value - 0.5) / 10000.0 * total
        acc = 0.0
        for ev in candidates:
            acc += weights.get(ev["id"], 10)
            if target <= acc:
                return ev
        return candidates[-1]

    # ------------------------------------------------------------------
    def resolve_choice(self, choice_index):
        """
        处理玩家在事件弹窗里的选择：
        掷骰判定结果 → 应用效果 → 疾病 / 体温 / 情绪结算 → 生成结果卡。
        """
        if self.pending is None:
            return {"tone": "nothing", "text": "当前没有待处理的事件。"}
        event = self.pending["event"]
        report = self.pending["report"]
        choices = event["choices"]
        if choice_index < 0 or choice_index >= len(choices):
            choice_index = 0
        choice = choices[choice_index]
        p = self.player

        # ---- 付费选项的金钱校验（友好提示，不崩溃）----
        need_money = float(choice.get("need_money", 0) or 0)
        if need_money > 0 and p.money < need_money:
            # 允许硬扛类选项兜底；若没有兜底选项则由界面提示
            fallback = next((i for i, c in enumerate(choices)
                             if float(c.get("need_money", 0) or 0) <= p.money), None)
            if fallback is None:
                return {"tone": "warn",
                        "text": "金钱不足：该选项需要 %.2f，你当前只有 %.2f。\n"
                                "请选择其它选项或先想办法赚钱。" % (need_money, p.money)}
            choice_index = fallback
            choice = choices[choice_index]

        outcome, roll = resolve_outcome(self.dice, choice)
        self.dice.remember(roll, "%s·结果判定" % event["name"])
        effects = dict(outcome.get("effects") or {})

        # 隐藏骰点的额外彩蛋：d100=100 时追加奖励，=1 时追加惩罚
        bonus_lines = []
        if roll.faces == 100 and roll.value == 100:
            effects = merge_effect(effects, {"money": 2000, "happy": 6})
            bonus_lines.append("【隐藏·骰运加身】满值骰点带来额外好运：金钱 +2000，幸福 +6。")
        elif roll.faces == 100 and roll.value == 1:
            effects = merge_effect(effects, {"health": -3, "happy": -3})
            bonus_lines.append("【隐藏·骰运反噬】大失败骰点带来额外打击：健康 -3，幸福 -3。")

        delta, notes = p.apply_effects(effects, dice=self.dice)
        report.accumulate(delta)

        lines = list(bonus_lines)
        if outcome.get("desc"):
            lines.append(outcome["desc"])
        lines.extend(notes)
        if roll.hidden:
            lines.append(roll.hidden)

        report.add_line("【%s】%s" % (event["name"], outcome.get("desc", "")))
        for note in notes:
            report.add_line("    · %s" % note)

        # ---- 连锁事件 ----
        followup = outcome.get("next_event")
        if followup and followup in EVENTS:
            self.pending_followup = followup

        # ---- 人生节点记录 ----
        self._record_milestones(event, outcome, delta)

        # ---- 当天其余结算（事件已处理完毕，清空待处理状态，允许继续当天操作/推进新的一天）----
        result_card = self._finish_day(report, keep_pending=False)
        result_card.update({
            "tone": "result",
            "event_name": event["name"],
            "outcome_desc": outcome.get("desc", ""),
            "delta": delta,
            "dice_lines": ["%s %s" % (choice["label"], roll)] + (
                ["隐藏骰点：%s" % roll.hidden] if roll.hidden else []),
            "extra_lines": lines,
            "roll": roll,
            "special": bool(event["special"]),
            "followup": followup,
        })
        return result_card

    def _record_milestones(self, event, outcome, delta):
        """把重大人生节点写进大事记与日志。"""
        p = self.player
        text = outcome.get("desc", "")
        tags = event.get("tags", [])
        if event["id"] == "love_marriage" and p.married:
            p.add_milestone("结婚", tag="婚姻")
            self.log and self.log.milestone(p, "结婚", "婚姻")
        if event["id"] == "love_child" and p.children > 0:
            p.add_milestone("迎来第 %d 个孩子" % p.children, tag="家庭")
            self.log and self.log.milestone(p, "迎来第 %d 个孩子" % p.children, "家庭")
        if event["id"] in ("work_unemployed",) and not p.employed:
            p.add_milestone("失业", tag="事业")
            self.log and self.log.milestone(p, "失业", "事业")
        if event["id"] == "work_gain_job" and p.employed:
            p.add_milestone("入职工作（职级 %d）" % p.job_level, tag="事业")
            self.log and self.log.milestone(p, "入职工作（职级 %d）" % p.job_level, "事业")
        if "disease" in tags:
            worst = p.worst_disease()
            if worst:
                if self.log:
                    self.log.disease(p, "患上/恶化：%s" % worst["name"])
                if DISEASE_SEVERITY.get(worst["id"], 0) >= 4:
                    p.add_milestone("重病：%s" % worst["name"], tag="疾病")
                    self.log and self.log.milestone(p, "重病：%s" % worst["name"], "疾病")
        if event["special"]:
            p.add_milestone("【%s】%s" % (event["name"], text[:40]), tag="奇遇")

    # ------------------------------------------------------------------
    def _finish_day(self, report, keep_pending=False):
        """事件结算之后的收尾：疾病 → 孕期 → 体温 → 情绪/子女 → 衰老 → 恢复 → 抢救 → 死亡 → 日志。"""
        self.settle_disease_phase(report)
        if not self.player.dead:
            self.settle_pregnancy_phase(report)
        if not self.player.dead:
            self.settle_env_phase(report)
        if not self.player.dead:
            self.settle_mood_phase(report)
        if not self.player.dead:
            self.settle_child_phase(report)
        if not self.player.dead:
            self.settle_aging_phase(report)
        if not self.player.dead:
            self.settle_recover_phase(report)
        if not self.player.dead:
            self.settle_hospital_phase(report)
        dead = self.check_death(report)
        self.last_report = report
        self._log_delta(report)
        if not keep_pending:
            self.pending = None
        if dead:
            self.pending = None
        return {
            "tone": "dead" if dead else "day_end",
            "report": report,
            "death": dead,
            "settlement_lines": list(report.lines),
        }

    # ------------------------------------------------------------------
    # 每日操作（休息 / 工作 / 娱乐）
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 行动点系统（游戏内同一天最多 8 次操作）
    # ------------------------------------------------------------------
    def action_points_left(self):
        return max(0, int(getattr(self.player, "action_points", 0)))

    def action_cost(self, action_key):
        return int(ACTION_COST.get(action_key, 2))

    def action_decay(self, action_key):
        """
        同一天内重复做同一件事的收益衰减：
        第 2 次 85%，第 3 次 72%……最低 40%。
        """
        used = int((self.player.action_tally or {}).get(action_key, 0))
        if used <= 0:
            return 1.0
        factor = ACTION_REPEAT_DECAY ** used
        return max(ACTION_REPEAT_FLOOR, factor)

    def can_do_action(self, action_key):
        """
        检查能否执行某个操作，返回 (是否允许, 提示文本)。
        """
        p = self.player
        if p.dead:
            return False, "人物已经离世。"
        if self.pending is not None:
            return False, "当前有事件尚未处理，请先做出选择。"
        cost = self.action_cost(action_key)
        if p.action_points < cost:
            return False, ("今天的行动点不够了（需要 %d 点，剩余 %d 点）。\n"
                           "每个游戏内的一天最多 8 点行动点；\n"
                           "可以点「跳过这一天」直接进入第二天。"
                           % (cost, p.action_points))
        return True, ""

    def apply_daily_action(self, action_key):
        """
        在**当天**执行一次操作（休息 / 工作 / 娱乐 / 学习 / 社交 / 锻炼）。
        重要：操作**不会推进日期**，只消耗行动点；一天最多 8 点。
        只有 step_roll()（推进一天）或 skip_day()（跳过这一天）才进入第二天。
        返回结果卡 dict。
        """
        p = self.player
        if p.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        ok, why = self.can_do_action(action_key)
        if not ok:
            return {"tone": "warn", "text": why}

        cost = self.action_cost(action_key)
        decay = self.action_decay(action_key)
        p.action_points -= cost
        p.actions_today += 1
        p.stats["actions_total"] = p.stats.get("actions_total", 0) + 1
        tally = dict(p.action_tally or {})
        tally[action_key] = int(tally.get(action_key, 0)) + 1
        p.action_tally = tally

        report = DailyReport(p)
        title = ACTION_LABELS.get(action_key, action_key)
        repeat_note = ""
        if decay < 0.999:
            repeat_note = "（今天第 %d 次做这件事，效果只有 %.0f%%）" % (
                tally[action_key], decay * 100)
            report.add_line(repeat_note)

        if action_key == "rest":
            self._do_rest(report, decay)
        elif action_key == "work":
            self._do_work(report, decay)
        elif action_key == "fun":
            result = self._do_fun(report, decay)
            if result is not None:
                # 金钱不足等情况：退回行动点
                p.action_points += cost
                p.actions_today = max(0, p.actions_today - 1)
                tally[action_key] = max(0, tally[action_key] - 1)
                p.action_tally = tally
                return result
        elif action_key == "study":
            self._do_study(report, decay)
        elif action_key == "social":
            self._do_social(report, decay)
        elif action_key == "exercise":
            self._do_exercise(report, decay)
        elif action_key == "parenting":
            result = self._do_parenting(report, decay)
            if result is not None:
                p.action_points += cost
                p.actions_today = max(0, p.actions_today - 1)
                tally[action_key] = max(0, tally[action_key] - 1)
                p.action_tally = tally
                return result
        else:
            p.action_points += cost
            p.actions_today = max(0, p.actions_today - 1)
            return {"tone": "warn", "text": "未知的操作：%s" % action_key}

        # 操作只影响当天状态，不做日期推进；但会做一次"当天身体反应"
        if not p.dead:
            self.settle_env_phase(report)
        if not p.dead:
            self.settle_recover_phase(report)
        self.check_death(report)
        self.last_report = report
        return {
            "tone": "dead" if p.dead else "action",
            "title": title,
            "report": report,
            "settlement_lines": list(report.lines),
            "dice_lines": self.dice.today_lines(),
            "death": p.dead,
            "action_points": p.action_points,
            "actions_today": p.actions_today,
        }

    def _do_rest(self, report, decay=1.0):
        p = self.player
        roll = self.dice.d10("休息效果")
        self.dice.remember(roll, "休息效果")
        heal = (4 + roll.value // 2) * decay
        happy_gain = (1 + roll.value // 4) * decay
        effects = {"health_boost": heal, "happy": happy_gain, "temp": (36.5 - p.temp) * 0.5}
        if roll.value >= 9:
            report.add_line("你睡了一个难得的好觉，醒来神清气爽。")
            effects["happy"] = happy_gain + 4 * decay
        elif roll.value <= 2:
            report.add_line("夜里翻来覆去，休息效果一般。")
            effects["health_boost"] = max(1.0, heal - 3)
        boredom = (1.0 - min(0.55, p.stats.get("rest_streak", 0) * 0.12))
        if boredom < 0.99:
            effects["health_boost"] = max(1.0, round(effects["health_boost"] * boredom, 2))
            effects["happy"] = round(effects["happy"] * boredom, 2)
            report.add_line("连续休息让你有些烦闷，恢复效果只有平时的 %d%%。" % (boredom * 100))
        delta, _ = p.apply_effects(effects, dice=self.dice)
        p.stats["days_rested"] += 1
        p.stats["rest_streak"] = p.stats.get("rest_streak", 0) + 1
        report.accumulate(delta)
        report.add_line("休息：健康 %s，幸福 %s，体温 %s" % (
            fmt_signed(delta["health"], 1), fmt_signed(delta["happy"], 1),
            fmt_signed(delta["temp"], 2)))

    def _do_work(self, report, decay=1.0):
        p = self.player
        stage = p.stage
        if p.age < 6:
            report.add_line("你还是个婴幼儿，只能在家里玩。")
            delta, _ = p.apply_effects({"happy": +2 * decay}, dice=self.dice)
            report.accumulate(delta)
            return
        if p.age < 16 or stage in ("primary", "middle", "kindergarten", "preschool"):
            # 学生时代：只能做点零工/跑腿，收入微薄，也不太伤身体
            roll = self.dice.d10("零工收益")
            self.dice.remember(roll, "零工收益")
            income = round((20.0 + 12.0 * roll.value) * decay, 2)
            cost_health = 0.8 + roll.value / 10.0
            delta, _ = p.apply_effects({"money": income, "health": -cost_health},
                                       dice=self.dice)
            p.stats["days_worked"] += 1
            report.accumulate(delta)
            report.add_line("打零工收入 %.2f，健康 %s（未成年/在读，收入有限）" % (
                income, fmt_signed(delta["health"], 1)))
            return
        roll = self.dice.d20("工作收益")
        self.dice.remember(roll, "工作收益")
        base = (80.0 + 30.0 * p.job_level) * (0.6 + roll.value / 20.0)
        if p.age >= 60:
            base *= 0.65
        elif not p.employed:
            base *= 0.7
        elif p.job_level == 0:
            base *= 0.8
        income = round(base * decay, 2)
        cost_health = (2.5 + roll.value / 6.0) / max(0.6, decay)
        if roll.value >= 19:
            income *= 1.8
            report.add_line("今天的工作异常顺利，客户当场追加了订单！")
        elif roll.value <= 2:
            cost_health += 3
            report.add_line("今天诸事不顺，还被上司说了一顿。")
        if p.age < 6:
            income = round(income * 0.15, 2)
        delta, _ = p.apply_effects(
            {"money": income, "health": -cost_health, "happy": -1}, dice=self.dice)
        p.stats["days_worked"] += 1
        report.accumulate(delta)
        report.add_line("工作收入 %.2f，健康 %s" % (income, fmt_signed(delta["health"], 1)))
        if p.diseases:
            report.add_line("（带病工作让身体更吃力……）")
        p.stats["rest_streak"] = 0

    def _do_fun(self, report, decay=1.0):
        """娱乐消费：金钱不足时返回提示卡（由上层退回行动点）。"""
        p = self.player
        roll = self.dice.d10("娱乐效果")
        self.dice.remember(roll, "娱乐效果")
        cost = round((120.0 + 60.0 * roll.value + 80.0 * max(0, p.job_level)) * decay, 2)
        if p.money > 20000:
            cost = round(cost * (1.0 + min(1.5, p.money / 60000.0)), 2)
        if p.money < cost:
            cheap = round(max(0.0, p.money * 0.35), 2)
            if cheap < 20:
                return {"tone": "warn",
                        "text": "金钱不足：娱乐消费需要 %.2f，你只有 %.2f。\n"
                                "建议先选择「工作赚钱」，或直接「跳过这一天」。\n"
                                "（身无分文的你什么也玩不了。）" % (cost, p.money)}
            report.add_line("你口袋里的钱不够原本的计划，只好改成低成本消遣。")
            cost = cheap
        happy_gain = (4 + roll.value + (3 if p.married or p.children else 0)) * decay
        delta, _ = p.apply_effects(
            {"money": -cost, "happy": happy_gain, "health": +1 * decay}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("娱乐消费 %.2f，幸福 %s" % (cost, fmt_signed(delta["happy"], 1)))
        p.stats["rest_streak"] = 0
        return None

    def _do_study(self, report, decay=1.0):
        """学习充电：积累学业表现（影响中考/高考/考研），消耗精力。"""
        p = self.player
        if p.age < 5:
            report.add_line("你还太小，只能看看图画书。")
            delta, _ = p.apply_effects({"happy": +1}, dice=self.dice)
            report.accumulate(delta)
            return
        roll = self.dice.d10("学习效果")
        self.dice.remember(roll, "学习效果")
        gain = int(round((1 + roll.value / 2.0) * decay))
        p.stats["study_points"] = p.stats.get("study_points", 0) + gain
        cost_health = 0.5 + roll.value / 20.0
        delta, _ = p.apply_effects({"health": -cost_health, "happy": -1}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("学习收获 %d 点学业表现（累计 %d），健康 %s" % (
            gain, p.stats["study_points"], fmt_signed(delta["health"], 1)))
        p.stats["rest_streak"] = 0

    def _do_social(self, report, decay=1.0):
        """社交联络：花钱提升幸福，可能带来机会。"""
        p = self.player
        if p.age < 4:
            report.add_line("你还不会说话，只能对着家人笑。")
            delta, _ = p.apply_effects({"happy": +2}, dice=self.dice)
            report.accumulate(delta)
            return
        roll = self.dice.d10("社交效果")
        self.dice.remember(roll, "社交效果")
        cost = round((60.0 + 40.0 * roll.value) * decay, 2)
        if p.money < cost:
            report.add_line("手头太紧，只能和家人聊聊天。")
            cost = 0.0
        happy_gain = (3 + roll.value * 0.8) * decay
        effects = {"money": -cost, "happy": happy_gain}
        if roll.value >= 9:
            effects["health"] = +1
            report.add_line("和朋友聊得很开心，还约好一起运动。")
        delta, _ = p.apply_effects(effects, dice=self.dice)
        report.accumulate(delta)
        report.add_line("社交花费 %.2f，幸福 %s" % (cost, fmt_signed(delta["happy"], 1)))
        p.stats["rest_streak"] = 0

    def _do_exercise(self, report, decay=1.0):
        """锻炼身体：小幅提升健康，并降低短期患病风险（改善体质表现）。"""
        p = self.player
        if p.age < 5:
            report.add_line("你在院子里跑来跑去，玩得满头是汗。")
            delta, _ = p.apply_effects({"health": +1, "happy": +1}, dice=self.dice)
            report.accumulate(delta)
            return
        if p.health < 25:
            report.add_line("身体太虚，强行锻炼反而吃不消。")
            delta, _ = p.apply_effects({"health": -1}, dice=self.dice)
            report.accumulate(delta)
            return
        roll = self.dice.d10("锻炼效果")
        self.dice.remember(roll, "锻炼效果")
        heal = (1.0 + roll.value / 6.0) * decay
        delta, _ = p.apply_effects({"health_boost": heal, "happy": +1 * decay,
                                    "temp": (36.5 - p.temp) * 0.3}, dice=self.dice)
        report.accumulate(delta)
        report.add_line("锻炼：健康 %s（体质 %d 分）" % (
            fmt_signed(delta["health"], 1), int(round(p.constitution))))
        # 当天锻炼会略微降低当天的患病概率
        p.stats["exercise_today"] = p.stats.get("exercise_today", 0) + 1
        p.stats["rest_streak"] = 0

    def _do_parenting(self, report, decay=1.0):
        """
        陪伴孩子：提升幸福、让孩子成长得更好（消耗当天时间）。
        没有孩子时返回提示卡（由上层退回行动点）。
        """
        p = self.player
        if not p.child_list:
            return {"tone": "warn",
                    "text": "你还没有孩子。\n\n"
                            "结婚后可以通过「夫妻亲密」迎接新生命。"}
        roll = self.dice.d10("陪伴效果")
        self.dice.remember(roll, "陪伴效果")
        happy_gain = (4 + roll.value * 0.6) * decay
        cost = round(80.0 * decay, 2)
        effects = {"happy": happy_gain, "money": -cost}
        if roll.value >= 8:
            effects["happy"] = happy_gain + 4
            report.add_line("你陪孩子玩了整整一下午，笑声一直没停过。")
        elif roll.value <= 2:
            report.add_line("孩子今天闹脾气，你怎么哄都不行。")
            effects["happy"] = max(1.0, happy_gain - 3)
        delta, _ = p.apply_effects(effects, dice=self.dice)
        report.accumulate(delta)
        # 孩子成长值累积（用于体现"陪伴"的长期作用）
        p.stats["parenting_points"] = p.stats.get("parenting_points", 0) + int(roll.value)
        report.add_line("陪伴孩子：幸福 %s，花费 %.2f（累计陪伴 %d 点）" % (
            fmt_signed(delta["happy"], 1), cost, p.stats.get("parenting_points", 0)))
        p.stats["rest_streak"] = 0
        return None

    # ------------------------------------------------------------------
    # 推进一天 / 跳过这一天
    # ------------------------------------------------------------------
    def skip_day(self, reason="今天什么也不做"):
        """
        「跳过这一天」：不消耗行动点，直接进入第二天（一天只能触发一次事件，
        跳过时会先掷骰判定当天是否发生事件；若已处理过事件则直接结束当天）。
        """
        p = self.player
        if p.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        if self.pending is not None:
            return {"tone": "warn", "text": "当前有事件尚未处理，请先做出选择。"}
        p.stats["skipped_days"] = p.stats.get("skipped_days", 0) + 1
        return self.end_day(reason=reason, allow_event=True)

    def end_day(self, reason="推进一天", allow_event=True):
        """
        结束当天：推进日期、跨月/跨年结算、阶段推进、环境与疾病结算。
        一天最多只掷骰触发一次事件（allow_event 控制）。
        """
        p = self.player
        report = DailyReport(p)
        p.stats["days_played"] = p.stats.get("days_played", 0) + 1
        calendar_notes, birthday = self.advance_calendar()
        p.days_played += 1

        for kind, value in calendar_notes:
            if kind == "month":
                self.settle_month(report)
                self.settle_family_phase(report)
                p.add_milestone("进入第 %d 月" % value, tag="时间")
            elif kind == "year":
                p.add_milestone("满 %d 岁" % p.age, tag="年龄")
                report.add_line("★ 你满 %d 岁了（%s阶段）。" % (
                    p.age, stage_name(p.stage)))
        if birthday:
            p.add_milestone("生日（%d 岁）" % p.age, tag="生日")
            report.add_line("🎂 今天是你的生日。")
            delta, _ = p.apply_effects({"happy": +3}, dice=self.dice)
            report.accumulate(delta)

        self.roll_ambient()
        self.settle_carried(report)
        self.auto_progress_stages(report)
        # ---- 每天的身体与家庭变化（与事件结算保持同一条流水线）----
        if not self.check_death(report):
            self.settle_pregnancy_phase(report)
        if not p.dead:
            self.settle_mood_phase(report)
        if not p.dead:
            self.settle_child_phase(report)
        if not p.dead:
            self.settle_aging_phase(report)
        if not p.dead:
            self.settle_recover_phase(report)
        if not p.dead:
            self.settle_hospital_phase(report)
        if self.check_death(report):
            self.last_report = report
            self.pending = None
            self._log_delta(report)
            return {"tone": "dead", "text": "\n".join(report.lines), "report": report}

        # ---- 新的一天：重置行动点与"当天计数" ----
        p.action_points = ACTION_POINTS_PER_DAY
        p.actions_today = 0
        p.action_tally = {}
        p.intimacy_today = 0
        p.stats.pop("exercise_today", None)

        self.last_report = report
        self.pending = None
        return {
            "tone": "dead" if p.dead else "day_end",
            "report": report,
            "death": p.dead,
            "settlement_lines": list(report.lines),
            "action_points": p.action_points,
        }

    # ------------------------------------------------------------------
    # 时间跳跃：按天 / 按月 / 按年跳过（只做合理汇总，不生成逐日事件）
    # ------------------------------------------------------------------
    def skip_time(self, days=0, months=0, years=0):
        """
        跳过一段时间。为保持合理性与性能，跳过期间**不生成逐日事件**，
        只做数值汇总：
          * 按天推进日期与月度结算（工资、生活支出、家庭供养）
          * 疾病按天结算（可能自愈/恶化/治愈）
          * 环境与体温按"平均值"结算，不做极端随机
          * 到年龄节点自动推进人生阶段
        返回结果卡 dict（含汇总文本）。
        """
        p = self.player
        if p.dead:
            return {"tone": "dead", "text": "人物已经离世。"}
        total_days = int(days) + int(months) * DAYS_PER_MONTH + int(years) * DAYS_PER_YEAR
        if total_days <= 0:
            return {"tone": "warn", "text": "跳过的时长必须大于 0。"}
        max_days = SKIP_MAX_YEARS * DAYS_PER_YEAR
        if total_days > max_days:
            total_days = max_days
        report = DailyReport(p)
        report.event_name = "时间跳跃"
        report.add_line("【时间跳跃】开始跳过 %d 天（约 %.1f 年）……" % (
            total_days, total_days / float(DAYS_PER_YEAR)))
        p.stats["skipped_days"] = p.stats.get("skipped_days", 0) + total_days

        start_money = p.money
        start_health = p.health
        start_age = p.age
        illnesses = 0
        cured = 0
        months_passed = 0
        day_count = 0

        while day_count < total_days and not p.dead:
            calendar_notes, birthday = self.advance_calendar()
            day_count += 1
            p.days_played += 1
            p.stats["days_played"] = p.stats.get("days_played", 0) + 1
            for kind, _value in calendar_notes:
                if kind == "month":
                    self.settle_month(report)
                    self.settle_family_phase(report)
                    months_passed += 1
                elif kind == "year":
                    p.add_milestone("满 %d 岁" % p.age, tag="年龄")
            if birthday:
                p.add_milestone("生日（%d 岁）" % p.age, tag="生日")
            self.auto_progress_stages(report)
            # 疾病按天结算（仍然遵守自愈/恶化规则）
            if p.diseases:
                self.settle_disease_phase(report)
            if p.dead:
                break
            # 时间跳跃期间的"平均环境"：每 10 天做一次温和结算，避免逐日开销过大
            if day_count % 10 == 0:
                self.roll_ambient()
                self.settle_env_phase(report)
                self.settle_mood_phase(report)
                self.settle_aging_phase(report)
                self.settle_recover_phase(report)
                self.settle_hospital_phase(report)
            self.check_death(report)

        illnesses = max(0, p.stats.get("disease_count", 0) - 0)
        report.add_line("跳过后：%s（%d 岁，%s阶段）" % (p.date_full, p.age, stage_name(p.stage)))
        report.add_line("数值汇总：健康 %s，幸福 %s，金钱 %s，体温 %.2f℃" % (
            fmt_signed(p.health - start_health, 1), fmt_signed(0, 0),
            fmt_signed(p.money - start_money, 2), p.temp))
        report.add_line("经历 %d 个月结算，疾病累计 %d 次，学历/阶段：%s" % (
            months_passed, p.stats.get("disease_count", 0), stage_name(p.stage)))
        p.add_milestone("跳过 %d 天（到 %d 岁）" % (total_days, p.age), tag="时间")
        self.last_report = report
        return {
            "tone": "dead" if p.dead else "skip",
            "title": "时间跳跃",
            "report": report,
            "settlement_lines": list(report.lines),
            "death": p.dead,
            "days": day_count,
            "action_points": p.action_points,
        }

    # ------------------------------------------------------------------
    def try_cure(self, disease_id=None):
        """
        主界面/菜单的「花钱治病」入口。
        返回 (是否成功, 提示文本, 花费)
        """
        p = self.player
        if not p.diseases:
            return False, "你目前没有疾病，不需要治疗。", 0.0
        target = (next((d for d in p.diseases if d["id"] == disease_id), None)
                  if disease_id else p.worst_disease())
        if target is None:
            return False, "没有找到对应的疾病。", 0.0
        cost = float(target["cure_cost"])
        if p.money < cost:
            return False, ("金钱不足：治疗%s需要 %.2f，你只有 %.2f。\n"
                           "可以选择「工作赚钱」攒钱，或者靠身体硬扛。"
                           % (target["name"], cost, p.money)), cost
        ok, msg, paid = p.cure_disease(target["id"])
        if ok:
            p.add_milestone("治愈%s（花费 %.2f）" % (target["name"], paid), tag="疾病")
            if self.log:
                self.log.disease(p, "治愈%s（花费 %.2f）" % (target["name"], paid))
        return ok, msg, paid

    # ------------------------------------------------------------------
    def finish_life(self):
        """人物死亡后生成人生总结（只生成一次）。"""
        p = self.player
        if not p.dead:
            return ""
        if p.summary_done:
            return "（人生总结已生成）"
        p.summary_done = True
        if self.log:
            return self.log.life_summary(p)
        return ""

    # ------------------------------------------------------------------
    def status_panel(self):
        """生成当前状态面板文本（供菜单/界面显示）。"""
        p = self.player
        city = get_city(p.city)
        con_name, con_desc = constitution_tier(p.constitution)
        fam_name, fam_desc, fam_support = family_tier(p.family_wealth)
        stage = STAGE_BY_ID.get(p.stage) or {}
        lines = []
        lines.append("姓名：%s        城市：%s（%s）" % (p.name, city["name"], city["tag"]))
        lines.append("时间：%s        当日气温：%.1f℃（%s）" % (
            p.date_full, p.ambient_temp, season_name(p.month)))
        lines.append("-" * 52)
        lines.append("人生阶段：%s（%d 岁）" % (stage.get("name", "?"), p.age))
        lines.append("    %s" % stage.get("desc", ""))
        lines.append("学历：%s" % ("、".join(p.education) if p.education else "尚未入学"))
        if p.exam_results:
            lines.append("考试结果：%s" % "；".join(
                "%s=%s" % (k, v) for k, v in p.exam_results.items()))
        lines.append("学业表现：%d 点        行动点：%d / %d（今天已操作 %d 次）" % (
            p.stats.get("study_points", 0), p.action_points, ACTION_POINTS_PER_DAY,
            p.actions_today))
        lines.append("-" * 52)
        lines.append("体质：%.1f 分（%s）—— %s" % (p.constitution, con_name, con_desc))
        lines.append("    易感倍率 %.2f 倍，预计每年生病 %.2f 次" % (
            constitution_susceptibility(p.constitution), illness_per_year(p.age, p.constitution)))
        lines.append("家境：%.1f 分（%s）—— %s" % (p.family_wealth, fam_name, fam_desc))
        support = family_support_amount(p)
        if p.family_bankrupt:
            lines.append("    【家庭已破产】父母无法再提供任何经济支持")
        elif support > 0:
            lines.append("    父母每月供养 %.2f（成年/毕业前由家庭承担开销）" % support)
        else:
            lines.append("    已独立，不再接受家庭供养")
        lines.append("-" * 52)
        lines.append("当前状态：%s" % p.status_text)
        for name, value, note, _color in p.attribute_rows():
            lines.append("%-4s：%-14s %s" % (name, value, note))
        lines.append("-" * 52)
        lines.append("疾病：%s" % p.disease_names())
        for d in p.diseases:
            lines.append("    · %s（%s）剩余 %d 天，每日健康 -%.1f，治愈费 %.0f" % (
                d["name"], d["kind"], d["days"], d["hp_per_day"], d["cure_cost"]))
        lines.append("工作：%s（职级 %d）        婚恋：%s        子女：%d 人" % (
            "在职" if p.employed else "无业", p.job_level,
            "已婚" if p.married else "单身", p.children))
        lines.append("身价估算：%.2f" % p.net_worth())
        lines.append("统计：度过 %d 天（平凡 %d 天）/ 操作 %d 次 / 患病 %d 次 / 治愈 %d 次" % (
            p.total_days, p.plain_days, p.stats.get("actions_total", 0),
            p.stats.get("disease_count", 0), p.stats.get("cure_count", 0)))
        lines.append("家庭累计供养：%.2f" % p.stats.get("family_support_total", 0.0))
        if p.carried_effects:
            lines.append("持续效果：")
            for item in p.carried_effects:
                lines.append("    · %s（剩余 %d 天）" % (item.get("name", "效果"), item.get("days", 0)))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def diary_panel(self, count=60):
        """返回最近的人生日志（用于界面回看）。"""
        if self.log:
            return "\n".join(self.log.tail_lines(count))
        return "（暂无日志）"



# ==============================================================================
# 13. Tkinter 界面层
# ==============================================================================

#: 极简配色：黑底白字 / 白底黑字 + 橙色作为唯一强调色
COLORS = {
    "bg": "#000000",          # 主背景：纯黑
    "panel": "#0d0d0d",       # 面板底色（接近黑）
    "panel2": "#ffffff",      # 反色面板：纯白
    "border": "#4a4a4a",      # 边框：中性灰
    "text": "#ffffff",        # 主文字：纯白
    "dim": "#a8a8a8",         # 次要文字：浅灰
    "accent": "#ff8c00",      # 强调色：橙色（唯一彩色）
    "good": "#ff8c00",        # 正向提示也用橙色（保持单色系统）
    "bad": "#ff8c00",         # 负向提示同样用橙色，靠文字区分
    "warn": "#ff8c00",
    "secret": "#ff8c00",
    "gold": "#ff8c00",
    "black": "#000000",
    "white": "#ffffff",
}

#: 字体优先使用宋体（中文点阵感强、简洁）
FONT_CANDIDATES = ("SimSun", "宋体", "NSimSun", "新宋体", "SimSun-ExtB")
MONO_CANDIDATES = ("NSimSun", "SimSun", "宋体", "Consolas", "Courier New")


if tk is not None:

    class ScrollPanel(tk.Toplevel):
        """通用弹窗：标题 + 可滚动文本 + 「确定」按钮（全程唯一交互形式）。"""

        def __init__(self, master, title="提示", width=760, height=560,
                 body_font=None, buttons=None, modal=True, colors=None):
            tk.Toplevel.__init__(self, master)
            self.colors = colors or COLORS
            self.title(title)
            self.configure(bg=self.colors["bg"])
            self.geometry("%dx%d" % (width, height))
            self.minsize(520, 360)
            self.result = None
            self._closed = False
            self._after_id = None

            # 顶部标题
            header = tk.Frame(self, bg=self.colors["panel"])
            header.pack(fill="x")
            tk.Label(header, text=title, bg=self.colors["panel"], fg=self.colors["accent"],
                     font=body_font or ("SimSun", 14, "bold"),
                     padx=16, pady=10, anchor="w").pack(fill="x")

            # 中部文本区（带滚动条）
            body = tk.Frame(self, bg=self.colors["bg"])
            body.pack(fill="both", expand=True, padx=12, pady=(10, 6))
            self.text = tk.Text(body, wrap="word", bg=self.colors["panel"],
                                fg=self.colors["text"], relief="flat",
                                insertbackground=self.colors["text"],
                                font=body_font or ("SimSun", 11),
                                padx=14, pady=12, spacing1=2, spacing3=4,
                                highlightthickness=1,
                                highlightbackground=self.colors["border"])
            scroll = tk.Scrollbar(body, command=self.text.yview)
            self.text.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            self.text.pack(side="left", fill="both", expand=True)
            self.text.configure(state="disabled")

            # 底部按钮区
            self.footer = tk.Frame(self, bg=self.colors["bg"])
            self.footer.pack(fill="x", padx=12, pady=(0, 12))
            for spec in (buttons or [("确定", "ok", None)]):
                label, key, command = spec
                self._make_button(self.footer, label, key, command)
            self._buttons = buttons or [("确定", "ok", None)]
            self._index = 0

            self.transient(master)
            if modal:
                self.grab_set()
            self.bind("<Return>", lambda e: self._activate(self._index))
            self.bind("<Escape>", lambda e: self._activate(self._default_index()))
            self.protocol("WM_DELETE_WINDOW", lambda: self._activate(self._default_index()))
            self.text.focus_set()

        # ------------------------------------------------------------------
        def _default_index(self):
            """默认按钮：优先「确定」，其次第一个非危险项。"""
            for i, (label, key, _cmd) in enumerate(self._buttons):
                if key in ("ok", "continue"):
                    return i
            return 0

        def _activate(self, index):
            if self._closed or not self._buttons:
                return
            index = max(0, min(index, len(self._buttons) - 1))
            label, key, command = self._buttons[index]
            self.result = key
            if callable(command):
                try:
                    keep = command(self)
                except Exception as exc:
                    print("弹窗回调异常：%s" % exc)
                    keep = False
                if keep:
                    return
            self.close()

        def _make_button(self, parent, label, key, command):
            """极简按钮：确认/继续=橙底黑字；取消/退出=白底黑字。"""
            if key in ("cancel", "quit", "close"):
                bg, fg = self.colors["white"], self.colors["black"]
                hbg, hfg = self.colors["accent"], self.colors["black"]
            else:
                bg, fg = self.colors["accent"], self.colors["black"]
                hbg, hfg = self.colors["white"], self.colors["black"]
            btn = tk.Button(parent, text=label, bg=bg, fg=fg,
                            activebackground=hbg, activeforeground=hfg,
                            relief="solid", bd=1, font=(FONT_CANDIDATES[0], 11),
                            padx=16, pady=8, cursor="hand2",
                            command=lambda k=key: self._activate_by_key(k))
            btn.pack(side="right", padx=(8, 0), pady=(4, 0))
            return btn

        def _activate_by_key(self, key):
            for i, (_label, k, _cmd) in enumerate(self._buttons):
                if k == key:
                    self._activate(i)
                    return

        # ------------------------------------------------------------------
        def set_text(self, text):
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text or "")
            self.text.configure(state="disabled")
            self.text.yview_moveto(0.0)

        def append_text(self, text):
            self.text.configure(state="normal")
            self.text.insert("end", text)
            self.text.configure(state="disabled")
            self.text.see("end")

        def tag_config(self, name, **kwargs):
            try:
                self.text.tag_configure(name, **kwargs)
            except Exception:
                pass

        def add_line(self, text, tag=None):
            self.text.configure(state="normal")
            if tag:
                self.text.insert("end", text + "\n", tag)
            else:
                self.text.insert("end", text + "\n")
            self.text.configure(state="disabled")
            self.text.see("end")

        def close(self):
            self._closed = True
            try:
                self.grab_release()
            except Exception:
                pass
            try:
                self.destroy()
            except Exception:
                pass

        @property
        def closed(self):
            return self._closed or not self.winfo_exists()


    class GameApp:
        """游戏主界面（唯一交互入口）。"""

        def __init__(self, base_dir, notes=None):
            self.base_dir = base_dir
            self.save_path = safe_join(base_dir, SAVE_FILE_NAME)
            self.log_path = safe_join(base_dir, LOG_FILE_NAME)
            self.startup_notes = list(notes or [])

            self.player = None
            self.sim = None
            self.log = None
            self.state = "idle"       # idle / event / action / dead
            self.locked = False       # 弹窗处理中
            self.hud_vars = {}
            self.start_bar = None     # 开局控件容器
            self.pending_card = None  # 未完成选择的事件卡
            self.death_panel_shown = False
            self.auto_save_warned = False
            self.last_auto_save_ok = None

            self.root = tk.Tk()
            self.root.title("%s v%s" % (APP_NAME, APP_VERSION))
            self.root.geometry("900x800")
            self.root.minsize(780, 680)
            self.root.configure(bg=COLORS["bg"])
            self.font_family = self._pick_font(FONT_CANDIDATES, "SimSun")
            self.mono_family = self._pick_font(MONO_CANDIDATES, "Consolas")
            self._build_styles()
            self._build_layout()
            self._bind_shortcuts()
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.show_start_screen()

        # ------------------------------------------------------------------
        # 界面基础
        # ------------------------------------------------------------------
        def _pick_font(self, candidates, fallback):
            """挑选系统里存在的字体，避免出现方块字。"""
            try:
                available = set(tkfont.families(self.root))
            except Exception:
                return fallback
            for name in candidates:
                if name in available:
                    return name
            return fallback

        def _build_styles(self):
            """字体规格：全部使用宋体；只靠字号与粗细区分层级。"""
            self.f_title = (self.font_family, 15, "bold")
            self.f_h2 = (self.font_family, 12, "bold")
            self.f_body = (self.font_family, 11)
            self.f_small = (self.font_family, 10)
            self.f_mono = (self.mono_family, 10)
            self.f_big = (self.font_family, 24, "bold")
            self.f_btn = (self.font_family, 11)

        def _build_layout(self):
            # 重要：底部区域（开局控件 / 游戏菜单）必须先用 side="bottom" 占位，
            # 否则中部的可伸缩文本区会把它们挤压成 0 高度（输入框会看不见）。
            self.bottom_panel = tk.Frame(self.root, bg=COLORS["bg"])
            self.bottom_panel.pack(side="bottom", fill="x")

            # 顶部标题栏
            header = tk.Frame(self.root, bg=COLORS["panel"])
            header.pack(side="top", fill="x")
            tk.Label(header, text="弹窗式文字人生模拟器", bg=COLORS["panel"],
                     fg=COLORS["accent"], font=self.f_title, padx=16, pady=10,
                     anchor="w").pack(side="left")
            self.date_var = tk.StringVar(value="尚未开始")
            tk.Label(header, textvariable=self.date_var, bg=COLORS["panel"],
                     fg=COLORS["text"], font=self.f_h2, padx=16).pack(side="right")

            # 属性面板
            stats = tk.Frame(self.root, bg=COLORS["bg"])
            stats.pack(side="top", fill="x", padx=14, pady=(12, 6))
            self.stat_labels = {}
            for col, (key, label) in enumerate((("health", "健康"), ("happy", "幸福"),
                                                ("money", "金钱"), ("temp", "体温"))):
                card = tk.Frame(stats, bg=COLORS["panel"], highlightthickness=1,
                                highlightbackground=COLORS["border"])
                card.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")
                stats.grid_columnconfigure(col, weight=1)
                tk.Label(card, text=label, bg=COLORS["panel"], fg=COLORS["dim"],
                         font=self.f_small).pack(anchor="w", padx=10, pady=(6, 0))
                var = tk.StringVar(value="--")
                value_label = tk.Label(card, textvariable=var, bg=COLORS["panel"],
                                       fg=COLORS["text"], font=self.f_h2)
                value_label.pack(anchor="w", padx=10)
                note_var = tk.StringVar(value="")
                tk.Label(card, textvariable=note_var, bg=COLORS["panel"],
                         fg=COLORS["dim"], font=self.f_small,
                         wraplength=170, justify="left").pack(anchor="w", padx=10, pady=(0, 8))
                self.stat_labels[key] = (var, value_label, note_var)

            # 状态行
            info = tk.Frame(self.root, bg=COLORS["bg"])
            info.pack(side="top", fill="x", padx=20, pady=(2, 0))
            self.status_var = tk.StringVar(value="请选择开局方式")
            tk.Label(info, textvariable=self.status_var, bg=COLORS["bg"], fg=COLORS["text"],
                     font=self.f_body, anchor="w", justify="left").pack(fill="x")
            self.substatus_var = tk.StringVar(value="")
            tk.Label(info, textvariable=self.substatus_var, bg=COLORS["bg"], fg=COLORS["dim"],
                     font=self.f_small, anchor="w", justify="left").pack(fill="x")
            # 阶段 / 体质 / 家境 行
            self.stage_var = tk.StringVar(value="")
            tk.Label(info, textvariable=self.stage_var, bg=COLORS["bg"], fg=COLORS["gold"],
                     font=self.f_small, anchor="w", justify="left").pack(fill="x")
            # 家庭 / 生育状态行
            self.family_var = tk.StringVar(value="")
            tk.Label(info, textvariable=self.family_var, bg=COLORS["bg"], fg="#ff9ecb",
                     font=self.f_small, anchor="w", justify="left").pack(fill="x")

            # 中部信息区（滚动文本，占据剩余全部空间）
            mid = tk.Frame(self.root, bg=COLORS["bg"])
            mid.pack(side="top", fill="both", expand=True, padx=14, pady=8)
            self.main_text = tk.Text(mid, wrap="word", bg=COLORS["panel"], fg=COLORS["text"],
                                     relief="flat", font=self.f_body, padx=14, pady=12,
                                     highlightthickness=1, highlightbackground=COLORS["border"],
                                     spacing1=2, spacing3=4, state="disabled")
            scroll = tk.Scrollbar(mid, command=self.main_text.yview)
            self.main_text.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            self.main_text.pack(side="left", fill="both", expand=True)
            self.main_text.tag_configure("h", foreground=COLORS["accent"],
                                         font=(self.font_family, 12, "bold"))
            self.main_text.tag_configure("good", foreground=COLORS["good"])
            self.main_text.tag_configure("bad", foreground=COLORS["bad"])
            self.main_text.tag_configure("warn", foreground=COLORS["warn"])
            self.main_text.tag_configure("secret", foreground=COLORS["secret"])
            self.main_text.tag_configure("dim", foreground=COLORS["dim"])
            self.main_text.tag_configure("mono", font=self.f_mono, foreground=COLORS["gold"])

            # 底部按钮区（放进 bottom_panel，保证永远有足够高度）
            footer = tk.Frame(self.bottom_panel, bg=COLORS["panel"])
            footer.pack(side="bottom", fill="x")
            self.footer = footer

            # ---- 第一行：推进 / 跳过这一天 ----
            row0 = tk.Frame(footer, bg=COLORS["panel"])
            row0.pack(fill="x", padx=14, pady=(10, 2))
            self.btn_roll = self._mk_button(row0, "推进一天（掷骰抽事件）", self.on_roll_day,
                                            color=COLORS["accent"], width=24)
            self.btn_roll.pack(side="left")
            self.btn_skip_day = self._mk_button(row0, "跳过这一天（什么也不做）",
                                                self.on_skip_day, color=COLORS["white"],
                                                width=24)
            self.btn_skip_day.pack(side="left", padx=(8, 0))
            self.ap_var = tk.StringVar(value="行动点 --/8")
            tk.Label(row0, textvariable=self.ap_var, bg=COLORS["panel"],
                     fg=COLORS["gold"], font=self.f_btn).pack(side="left", padx=(12, 0))

            # ---- 第二行：当天操作（一天最多 8 次）----
            row1 = tk.Frame(footer, bg=COLORS["panel"])
            row1.pack(fill="x", padx=14, pady=(2, 2))
            self.action_buttons = {}
            for key in ("rest", "work", "fun", "study", "social", "exercise",
                        "intimacy", "parenting"):
                btn = self._mk_button(row1, ACTION_LABELS[key],
                                      lambda k=key: self.on_action(k),
                                      color=COLORS["white"], width=9)
                btn.pack(side="left", padx=(0, 6))
                self.action_buttons[key] = btn
            self.btn_rest = self.action_buttons["rest"]
            self.btn_work = self.action_buttons["work"]
            self.btn_fun = self.action_buttons["fun"]
            tk.Label(row1, text="（每次操作消耗 1 点行动点，不推进日期）",
                     bg=COLORS["panel"], fg=COLORS["dim"],
                     font=self.f_small).pack(side="left", padx=(6, 0))

            # ---- 第三行：时间跳跃 ----
            row_skip = tk.Frame(footer, bg=COLORS["panel"])
            row_skip.pack(fill="x", padx=14, pady=(2, 2))
            tk.Label(row_skip, text="时间跳跃：跳过", bg=COLORS["panel"], fg=COLORS["text"],
                     font=self.f_small).pack(side="left")
            self.skip_months_var = tk.StringVar(value="1")
            tk.Entry(row_skip, textvariable=self.skip_months_var, width=5,
                     bg=COLORS["white"], fg=COLORS["black"], relief="flat",
                     insertbackground=COLORS["text"], font=self.f_small).pack(
                side="left", padx=(4, 2), ipady=3)
            tk.Label(row_skip, text="个月", bg=COLORS["panel"], fg=COLORS["text"],
                     font=self.f_small).pack(side="left")
            self._mk_button(row_skip, "按月跳过", self.on_skip_months,
                            color=COLORS["white"], width=9).pack(side="left", padx=(6, 12))
            self.skip_years_var = tk.StringVar(value="1")
            tk.Entry(row_skip, textvariable=self.skip_years_var, width=5,
                     bg=COLORS["white"], fg=COLORS["black"], relief="flat",
                     insertbackground=COLORS["text"], font=self.f_small).pack(
                side="left", padx=(4, 2), ipady=3)
            tk.Label(row_skip, text="年", bg=COLORS["panel"], fg=COLORS["text"],
                     font=self.f_small).pack(side="left")
            self._mk_button(row_skip, "按年跳过", self.on_skip_years,
                            color=COLORS["white"], width=9).pack(side="left", padx=(6, 0))
            tk.Label(row_skip, text="（跳过期间只做数值汇总，不生成逐日事件）",
                     bg=COLORS["panel"], fg=COLORS["dim"],
                     font=self.f_small).pack(side="left", padx=(10, 0))

            row2 = tk.Frame(footer, bg=COLORS["panel"])
            row2.pack(fill="x", padx=14, pady=(4, 12))
            for label, command in (("状态", self.on_status), ("治病", self.on_cure),
                                   ("日志", self.on_log), ("保存进度", self.on_save),
                                   ("读取进度", self.on_load), ("保存并退出", self.on_quit),
                                   ("帮助", self.on_help)):
                self._mk_button(row2, label, command, color=COLORS["white"],
                                width=10).pack(side="left", padx=(0, 6))

            self.set_actions_enabled(False)
            self.write_main("欢迎来到《弹窗式文字人生模拟器》。\n\n"
                            "请点击下方按钮开始新的人生，或读取已有存档继续。\n",
                            "h")

        def _mk_button(self, parent, text, command, color=None, width=None,
                       variant="dark"):
            """
            统一按钮样式（极简双色）：
                variant="dark"  -> 黑底白字（次要操作）
                variant="light" -> 白底黑字（主要操作）
                variant="orange"-> 橙底黑字（最强调操作）
            color 参数保留兼容：传入 COLORS 里的白/橙会自动映射到对应 variant。
            """
            if color in (COLORS["accent"], COLORS["gold"]):
                variant = "orange"
            elif color in (COLORS["panel2"], COLORS["white"]):
                variant = "light"
            if variant == "orange":
                bg, fg, hover_bg, hover_fg = COLORS["accent"], COLORS["black"], "#ffffff", COLORS["black"]
            elif variant == "light":
                bg, fg, hover_bg, hover_fg = COLORS["white"], COLORS["black"], COLORS["accent"], COLORS["black"]
            else:
                bg, fg, hover_bg, hover_fg = COLORS["panel"], COLORS["text"], COLORS["accent"], COLORS["black"]
            btn = tk.Button(parent, text=text, command=command,
                            bg=bg, fg=fg,
                            activebackground=hover_bg, activeforeground=hover_fg,
                            relief="solid", bd=1, highlightthickness=0,
                            font=self.f_btn, padx=10, pady=6,
                            cursor="hand2", disabledforeground=COLORS["dim"])
            if width:
                btn.configure(width=width)
            return btn

        def adjust_window_size(self):
            """
            按内容所需高度自动扩展窗口。
            原因：底部控制区（开局控件 / 游戏菜单）内容较多，
            若窗口高度小于"所需高度"，pack 会把底部区域裁掉（按钮会看不见）。
            """
            try:
                self.root.update_idletasks()
                need_h = self.root.winfo_reqheight()
                need_w = max(900, self.root.winfo_reqwidth())
                cur_h = self.root.winfo_height()
                cur_w = self.root.winfo_width()
                screen_h = self.root.winfo_screenheight()
                # 目标高度：至少 900，最多不超过屏幕可用高度的 95%
                target_h = min(max(900, need_h + 12), int(screen_h * 0.95))
                if cur_h < target_h - 4 or cur_w < need_w - 4:
                    x = self.root.winfo_rootx()
                    y = max(0, self.root.winfo_rooty())
                    self.root.geometry("%dx%d+%d+%d" % (
                        max(cur_w, need_w, 900), target_h, max(0, x), y))
                    self.root.update_idletasks()
            except Exception:
                pass

        def _bind_shortcuts(self):
            """快捷键：Ctrl+S 保存进度，Ctrl+Q 保存并退出，Esc 关闭最上层弹窗。"""
            def bind(seq, func):
                try:
                    self.root.bind_all(seq, func)
                except Exception:
                    pass

            def on_save_key(_event=None):
                self.on_save()
                return "break"

            def on_quit_key(_event=None):
                self.on_quit()
                return "break"

            def on_close_panel(_event=None):
                for win in self.root.winfo_children():
                    if isinstance(win, tk.Toplevel) and win.winfo_exists():
                        try:
                            win.event_generate("<Escape>")
                        except Exception:
                            try:
                                win.destroy()
                            except Exception:
                                pass
                return "break"

            bind("<Control-s>", on_save_key)
            bind("<Control-S>", on_save_key)
            bind("<Control-q>", on_quit_key)
            bind("<Control-Q>", on_quit_key)
            bind("<Escape>", on_close_panel)

        def write_main(self, text, tag=None):
            self.main_text.configure(state="normal")
            self.main_text.insert("end", text + ("" if text.endswith("\n") else "\n"), tag or ())
            self.main_text.configure(state="disabled")
            self.main_text.see("end")

        def clear_main(self):
            self.main_text.configure(state="normal")
            self.main_text.delete("1.0", "end")
            self.main_text.configure(state="disabled")

        # ------------------------------------------------------------------
        # 弹窗封装
        # ------------------------------------------------------------------
        def show_panel(self, title, text, buttons=None, width=780, height=580,
                       modal=True, on_open=None):
            """显示一个弹窗，返回弹窗对象。"""
            panel = ScrollPanel(self.root, title=title, width=width, height=height,
                                body_font=self.f_body, buttons=buttons, modal=modal,
                                colors=COLORS)
            panel.add_line(text)
            if on_open:
                try:
                    on_open(panel)
                except Exception as exc:
                    print("弹窗初始化异常：%s" % exc)
            return panel

        def alert(self, title, text, key="info", on_close=None):
            """友好提示弹窗（异常处理统一走这里，绝不崩溃）。"""
            buttons = [("确定", "ok", None)]
            return self.show_panel(title, text, buttons, width=620, height=380,
                                   on_open=on_close)

        def ask(self, title, text, buttons, width=780, height=580, on_open=None):
            """带多个选项按钮的弹窗（选择弹窗）。"""
            return self.show_panel(title, text, buttons, width=width, height=height,
                                   on_open=on_open)

        # ------------------------------------------------------------------
        # 开局 / 读取界面
        # ------------------------------------------------------------------
        def show_start_screen(self):
            """开局界面：全部在主窗口内完成（姓名、城市、开始/读取），无需额外弹窗。"""
            self.state = "idle"
            self.player = None
            self.sim = None
            self.set_actions_enabled(False)
            try:
                self.btn_roll.configure(state="disabled")
            except Exception:
                pass
            self.date_var.set("尚未开始")
            for key, (var, label, note_var) in self.stat_labels.items():
                var.set("--")
                label.configure(fg=COLORS["text"])
                note_var.set("")
            self.clear_main()
            self.write_main("═══ 开局设定 ═══", "h")
            self.write_main("数据目录：%s" % self.base_dir, "dim")
            self.write_main("存档文件：%s" % self.save_path, "dim")
            self.write_main("人生日志：%s" % self.log_path, "dim")
            if self.startup_notes:
                for note in self.startup_notes:
                    self.write_main("目录提示：%s" % note, "warn")
            self.write_main("")
            self.write_main("玩法提示：", "h")
            self.write_main("    1. 点「推进一天」掷骰抽事件，事件后可安排当天行动"
                            "（休息 / 工作 / 娱乐），时间推进 1 天。")
            self.write_main("    2. 健康归零即死亡；幸福长期低于 %d 会持续掉健康；"
                            "体温偏离 36.0~37.0 每日掉血。" % LOW_HAPPY_THRESHOLD)
            self.write_main("    3. 疾病按天结算：轻症可自愈，重症必须花钱治疗，"
                            "拖久了可能致命（健康跌破危险线会自动送医）。")
            self.write_main("    4. 骰子掷出 100 / 99 / 2 / 1 等极端点数会触发隐藏剧情。")
            self.write_main("")
            self.write_main("请在下方输入姓名并选择城市，然后点「开始新的人生」。", "warn")
            if save_exists(self.save_path):
                self.write_main("检测到已有存档：%s" % self.save_path, "good")
                self.write_main("可以点「读取存档」继续上一局人生。", "good")

            self.status_var.set("准备开始新的人生。")
            self.substatus_var.set("城市决定环境气候事件概率与体温波动，选择后永久生效。")
            self.refresh_start_controls()

        def refresh_start_controls(self):
            """构建 / 刷新开局控件（姓名输入框、城市单选、开始/读取按钮）。

            注意：这些控件放在窗口底部的 bottom_panel 里，并且用 side="bottom" 打包，
            它会排在游戏菜单（footer）上方，且不会被中部文本区挤压（曾经被压成 1px 不可见）。
            """
            if getattr(self, "start_bar", None) is not None:
                try:
                    self.start_bar.destroy()
                except Exception:
                    pass
            bar = tk.Frame(self.bottom_panel, bg=COLORS["panel"],
                           highlightthickness=1, highlightbackground=COLORS["accent"])
            bar.pack(side="bottom", fill="x")
            self.start_bar = bar
            # 开局时隐藏游戏菜单，避免布局过挤（进入游戏后再显示）
            if getattr(self, "footer", None) is not None:
                try:
                    self.footer.pack_forget()
                except Exception:
                    pass

            row1 = tk.Frame(bar, bg=COLORS["panel"])
            row1.pack(side="top", fill="x", padx=14, pady=(10, 4))
            tk.Label(row1, text="姓名：", bg=COLORS["panel"], fg=COLORS["text"],
                     font=self.f_body).pack(side="left")
            self.name_entry = tk.Entry(row1, bg=COLORS["white"], fg=COLORS["black"],
                                       insertbackground=COLORS["text"], relief="flat",
                                       font=self.f_body, width=18)
            self.name_entry.insert(0, "无名氏")
            self.name_entry.pack(side="left", padx=(4, 10), ipady=4)
            tk.Label(row1, text="城市：", bg=COLORS["panel"], fg=COLORS["text"],
                     font=self.f_body).pack(side="left")
            self.city_var = tk.StringVar(value="beijing")
            for city_id in CITY_ORDER:
                city = CITIES[city_id]
                tk.Radiobutton(row1, text="%s（%s）" % (city["name"], city["tag"]),
                               variable=self.city_var, value=city_id,
                               bg=COLORS["panel"], fg=COLORS["text"],
                               selectcolor=COLORS["white"],
                               activebackground=COLORS["panel"],
                               activeforeground=COLORS["accent"],
                               font=self.f_small, cursor="hand2").pack(side="left", padx=(0, 6))

            row2 = tk.Frame(bar, bg=COLORS["panel"])
            row2.pack(side="top", fill="x", padx=14, pady=(4, 6))
            self._mk_button(row2, "开始新的人生", self.start_new_game,
                            color=COLORS["accent"], width=16).pack(side="left")
            self._mk_button(row2, "读取存档", self.on_load,
                            color=COLORS["white"], width=12).pack(side="left", padx=(8, 0))
            self._mk_button(row2, "帮助", self.on_help,
                            color=COLORS["white"], width=8).pack(side="left", padx=(8, 0))
            self._mk_button(row2, "退出游戏", self.on_quit,
                            color=COLORS["white"], width=10).pack(side="left", padx=(8, 0))
            tk.Label(row2, text="（姓名最多 12 字；城市选择后永久生效）",
                     bg=COLORS["panel"], fg=COLORS["dim"],
                     font=self.f_small).pack(side="left", padx=(10, 0))
            try:
                self.name_entry.focus_set()
                self.name_entry.select_range(0, "end")
            except Exception:
                pass

        def hide_start_controls(self):
            """进入游戏：移除开局控件，显示游戏菜单。"""
            if getattr(self, "start_bar", None) is not None:
                try:
                    self.start_bar.destroy()
                except Exception:
                    pass
                self.start_bar = None
            if getattr(self, "footer", None) is not None:
                try:
                    self.footer.pack(side="bottom", fill="x")
                except Exception:
                    pass
            # 游戏菜单比开局控件更高，需要重新检查窗口是否放得下
            self.adjust_window_size()

        def start_new_game(self, dialog=None):
            """开始新的人生。"""
            try:
                name = (self.name_entry.get() or "").strip() if hasattr(self, "name_entry") else ""
                city = self.city_var.get() if hasattr(self, "city_var") else "beijing"
                name = (name or "无名氏")[:12]
                if save_exists(self.save_path):
                    panel = self.show_panel(
                        "开始新的人生",
                        "已有存档存在：\n%s\n\n开始新的人生不会删除该存档，"
                        "但之后的「保存进度」会覆盖它。\n\n确定要开始新的人生吗？" % self.save_path,
                        [("开始新的人生", "ok", None), ("取消", "cancel", None)],
                        width=620, height=400)
                    self.root.wait_window(panel)
                    if panel.result != "ok":
                        return
                self.player = Player(name=name, city=city)
                self.log = LifeLog(self.log_path, name, get_city(city)["name"])
                self.log.start(self.player)
                self.sim = Simulator(self.player, self.log, self.base_dir)
                self.death_panel_shown = False
                self.pending_card = None
                self.auto_save_warned = False
                self.hide_start_controls()
                self.state = "event"
                self.date_var.set(self.player.date_full)
                self.update_hud()
                self.clear_main()
                self.write_main("═══ 人生开始 ═══", "h")
                con_name, con_desc = constitution_tier(self.player.constitution)
                fam_name, fam_desc, fam_support = family_tier(self.player.family_wealth)
                self.write_main("%s，出生于%s（%s）。" % (
                    self.player.name, get_city(city)["name"], get_city(city)["tag"]))
                self.write_main("初始属性：健康 100 / 幸福 50 / 金钱 1000.00 / 体温 36.5℃", "good")
                self.write_main("")
                self.write_main("═══ 开局随机参数（固定，永久生效）═══", "h")
                self.write_main("体质：%.1f 分（%s）—— %s" % (
                    self.player.constitution, con_name, con_desc), "good" if self.player.constitution >= 60 else ("bad" if self.player.constitution < 40 else None))
                self.write_main("    患病易感倍率 %.2f 倍；婴幼儿期预计每年生病 %.2f 次" % (
                    constitution_susceptibility(self.player.constitution),
                    illness_per_year(1, self.player.constitution)))
                self.write_main("家境：%.1f 分（%s）—— %s" % (
                    self.player.family_wealth, fam_name, fam_desc), "good" if self.player.family_wealth >= 60 else ("bad" if self.player.family_wealth < 40 else None))
                self.write_main("    父母每月供养 %.2f；成年前（或大学毕业前）由家庭承担开销" % fam_support)
                self.write_main("")
                self.write_main("人生流程：学龄前 → 幼儿园 → 小学 → 初中 → 中考 → 高中 → 高考 "
                                "→ 大学(有概率不上) → 读研(有概率不上) → 工作 → 退休", "dim")
                self.write_main("每一天最多可以做 8 次操作（休息/工作/娱乐/学习/社交/锻炼），"
                                "也可以直接「跳过这一天」；事件不再天天发生。", "dim")
                self.write_main("")
                self.write_main("点「推进一天」，开始你的第一天人生吧。")
                self.set_status("新的人生已经开始，点击「推进一天」抽取今天的第一个事件。",
                                "提示：事件弹窗会显示骰子点数与属性变化，选择后自动结算。")
                self.refresh_action_points()
                self.btn_roll.configure(state="normal")
                try:
                    self.btn_skip_day.configure(state="normal")
                except Exception:
                    pass
            except Exception as exc:
                self.alert("开局失败", "创建新游戏时出现异常：\n%s\n\n%s" % (
                    exc, traceback.format_exc(limit=3)))

        def load_from_dialog(self, dialog=None):
            """兼容入口：从开局界面直接读取存档。"""
            self.do_load()

        # ------------------------------------------------------------------
        # HUD 刷新
        # ------------------------------------------------------------------
        def update_hud(self):
            if not self.player:
                return
            p = self.player
            self.date_var.set(p.date_full)
            values = {
                "health": "%.1f" % p.health,
                "happy": "%.1f" % p.happy,
                "money": "%.2f" % p.money,
                "temp": "%.2f ℃" % p.temp,
            }
            notes = {
                "health": "上限 100 · 归零即死亡" if p.health > 20 else "濒临死亡！",
                "happy": "低于 %d 会持续扣健康" % LOW_HAPPY_THRESHOLD,
                "money": "负债中" if p.money < 0 else "可治病 / 消费",
                "temp": "正常 36.0~37.0" if TEMP_NORMAL_LOW <= p.temp <= TEMP_NORMAL_HIGH
                        else "异常！每日扣健康",
            }
            colors = {
                "health": p.health_color(), "happy": p.happy_color(),
                "money": p.money_color(), "temp": p.temp_color(),
            }
            for key, (var, label, note_var) in self.stat_labels.items():
                var.set(values[key])
                label.configure(fg=colors[key])
                note_var.set(notes[key])
            # 阶段 / 体质 / 家境 / 行动点
            try:
                con_name, _con_desc = constitution_tier(p.constitution)
                fam_name, _fam_desc, _sup = family_tier(p.family_wealth)
                fam_tag = "（已破产）" if p.family_bankrupt else ""
                self.stage_var.set("阶段：%s　体质：%.0f(%s)　家境：%.0f(%s)%s" % (
                    stage_name(p.stage), p.constitution, con_name,
                    p.family_wealth, fam_name, fam_tag))
            except Exception:
                pass
            # 家庭 / 生育状态行
            try:
                bits = []
                if p.partner_name or p.married:
                    bits.append("伴侣：%s" % (p.partner_name or "已婚"))
                if p.pregnant:
                    bits.append("孕期：第 %d 个月（共 9 个月）" % max(
                        1, p.pregnancy_days // DAYS_PER_MONTH + 1))
                if p.child_list:
                    bits.append("子女 %d 人：%s" % (
                        len(p.child_list),
                        "、".join("%s(%d岁)" % (c.get("name", "孩子"), self.sim._child_age(c))
                                  for c in p.child_list[:3])))
                elif p.married or p.partner_name:
                    bits.append("子女：暂无")
                if p.married or p.partner_name:
                    bits.append("避孕：%s" % p.contraception)
                self.family_var.set(("　".join(bits)) if bits else "")
            except Exception:
                pass
            self.refresh_action_points()

        def set_status(self, text, sub=""):
            self.status_var.set(text)
            if sub is not None:
                self.substatus_var.set(sub)

        def set_substatus(self, text):
            """只更新副状态栏（用于自动存档等提示）。"""
            try:
                self.substatus_var.set(text)
            except Exception:
                pass

        def set_actions_enabled(self, enabled):
            state = "normal" if enabled else "disabled"
            for btn in (getattr(self, "action_buttons", {}) or {}).values():
                try:
                    btn.configure(state=state)
                except Exception:
                    pass

        def refresh_action_points(self):
            """
            刷新行动点显示，并按剩余行动点启用/禁用操作按钮。

            规则（重要）：
              * 当天只要还有行动点、且没有待处理事件，操作按钮就应该是**可点**的，
                可以连续点 8 次，中间不需要点「跳过这一天」；
              * 行动点耗尽后禁用操作按钮，并把「推进一天」按钮文字改成
                「推进到下一天」，引导玩家直接进入第二天。
            """
            p = self.player
            if p is None:
                self.ap_var.set("行动点 --/%d" % ACTION_POINTS_PER_DAY)
                return
            left = int(getattr(p, "action_points", 0))
            used = int(getattr(p, "actions_today", 0))
            pending = (self.sim is not None and self.sim.pending is not None)
            self.ap_var.set("行动点 %d/%d　今天已操作 %d 次" % (
                left, ACTION_POINTS_PER_DAY, used))
            # 还能行动的条件：有行动点 + 没有待处理事件 + 游戏进行中
            base_ok = (not p.dead) and (not pending) and self.pending_card is None
            for key, btn in (self.action_buttons or {}).items():
                cost = ACTION_COST.get(key, 1)
                can = base_ok and left >= cost
                try:
                    btn.configure(state="normal" if can else "disabled")
                    btn.configure(text=ACTION_LABELS[key])
                except Exception:
                    pass
            # 「推进一天」按钮：行动点用完时提示进入下一天
            try:
                if p.dead:
                    self.btn_roll.configure(text="人生已结束", state="disabled")
                elif pending or self.pending_card is not None:
                    self.btn_roll.configure(text="先处理今天的事件", state="normal")
                elif left >= ACTION_POINTS_PER_DAY:
                    self.btn_roll.configure(text="推进一天（掷骰抽事件）", state="normal")
                elif left > 0:
                    self.btn_roll.configure(
                        text="推进到下一天（还剩 %d 点行动点）" % left, state="normal")
                else:
                    self.btn_roll.configure(text="推进到下一天（行动点已用完）", state="normal")
                self.btn_skip_day.configure(
                    text="略过剩余行动点，直接到下一天", state="normal")
            except Exception:
                pass

        # ------------------------------------------------------------------
        # 核心流程：推进一天
        # ------------------------------------------------------------------
        def on_roll_day(self, *_):
            if self.locked:
                return
            if self.player is None:
                self.alert("尚未开始人生",
                           "还没有创建人物。\n\n请在下方输入姓名、选择城市，"
                           "然后点击「开始新的人生」；也可以点「读取存档」继续上一局。")
                self.set_status("请先在下方完成开局设定。")
                return
            if self.player.dead:
                self.show_death_panel()
                return
            # 注意：这里**不再**因为"今天已经行动过"而拦截。
            # 一天有 8 点行动点，点几次操作都行；行动点用完后
            # 直接点「推进一天」就进入第二天（不需要先点"跳过这一天"）。
            # 有未完成选择的事件卡时，不重复推进时间，直接重新打开该事件
            if self.sim is not None and self.sim.pending is not None:
                card = self.sim.pending.get("card")
                if card:
                    self.alert("事件尚未处理",
                               "你还有一个事件没有做出选择，时间不会继续推进。\n"
                               "请先在事件弹窗里选择一项处理方式。")
                    self.show_event_dialog(card)
                    return
            try:
                self.locked = True
                card = self.sim.step_roll()
                self.update_hud()
                if card.get("tone") == "dead":
                    self.locked = False
                    self.handle_death(card.get("report"))
                    return
                if card.get("tone") == "event":
                    self.state = "event"
                    self.refresh_action_points()
                    self.show_event_dialog(card)
                else:
                    # 平静的一天：直接在主窗口提示，不弹模态框，方便立刻连续操作
                    self.state = "action"
                    self.clear_main()
                    self.write_main("═══ %s ═══" % self.sim.player.date_full, "h")
                    self.write_main(card.get("text", "今天什么也没有发生。"))
                    self.write_main("")
                    self.write_main("　→ 今天有 %d 点行动点，可以连续点击下面的操作按钮"
                                    "（休息 / 工作 / 娱乐 / 学习 / 社交 / 锻炼 / 亲密 / 陪伴）。"
                                    % ACTION_POINTS_PER_DAY, "warn")
                    self.set_status("今天什么也没有发生，可以安排行动（行动点 %d/%d）。" % (
                        int(self.player.action_points), ACTION_POINTS_PER_DAY),
                        "同一天可以连续操作，行动点用完后点「推进到下一天」。")
                    self.refresh_action_points()
                self.auto_save()
                self.locked = False
            except Exception as exc:
                self.locked = False
                self.alert("运行时异常",
                           "处理「推进一天」时出现异常，游戏已自动保护现场：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def show_event_dialog(self, card):
            """事件弹窗：显示事件描述 + 骰子 + 选项按钮。"""
            secret = card.get("secret_reason")
            header = []
            if secret:
                header.append("◆ %s" % secret)
            header.append("【%s】%s" % (card["category"], card["event_name"]))
            body = "\n".join(header) + "\n\n" + card["desc"]
            if card.get("roll_lines"):
                body += "\n\n—— 今日骰子 ——\n" + "\n".join(card["roll_lines"])
            if card.get("settlement_lines"):
                body += "\n\n—— 今日其他结算 ——\n" + "\n".join(
                    "    " + ln for ln in card["settlement_lines"])
            body += "\n\n请做出你的选择："

            buttons = []
            for choice in card["choices"]:
                label = choice["label"]
                if choice.get("detail"):
                    label = "%s（%s）" % (label, choice["detail"])
                buttons.append((label, "choice_%d" % choice["index"], None))
            buttons.append(("稍后再说", "cancel", None))

            def on_open(panel):
                panel.tag_config("secret", foreground=COLORS["secret"],
                                 font=(self.font_family, 12, "bold"))
                panel.tag_config("mono", font=self.f_mono, foreground=COLORS["gold"])

            panel = self.show_panel("事件：%s" % card["event_name"], body, buttons,
                                    width=820, height=620, on_open=on_open)
            # 捕获选择结果
            self.root.wait_window(panel)
            result = panel.result
            if result in (None, "cancel", "close"):
                # 未选择：保留事件，允许再次点击推进时重新弹出
                self.set_status("你还没有做出选择，事件仍在等待处理。",
                                "再次点击「推进一天」可以重新打开这个事件。")
                self.pending_card = card
                return
            index = int(str(result).split("_")[-1])
            self.pending_card = None
            self.handle_choice(card, index)

        def handle_choice(self, card, index):
            """处理选项结果并展示结算弹窗。"""
            try:
                self.locked = True
                result = self.sim.resolve_choice(index)
                self.update_hud()
                if result.get("tone") == "warn":
                    self.locked = False
                    self.alert("无法选择该选项", result.get("text", ""))
                    # 重新弹出事件让玩家改选
                    self.show_event_dialog(card)
                    return
                self.show_result_dialog(result)
                if self.player.dead:
                    self.locked = False
                    self.handle_death(self.sim.last_report)
                    return
                self.state = "action"
                left = int(getattr(self.player, "action_points", 0))
                self.set_status("事件已结算，可以安排今天的行动（行动点 %d/%d）。" % (
                    left, ACTION_POINTS_PER_DAY),
                    "同一天可连续操作；行动点用完后直接点「推进到下一天」。")
                self.refresh_action_points()
                self.auto_save()
                self.locked = False
                if result.get("followup"):
                    # 连锁事件：立即弹出后续事件
                    follow_ev = EVENTS.get(result["followup"])
                    if follow_ev:
                        self.queue_followup(follow_ev)
            except Exception as exc:
                self.locked = False
                self.alert("运行时异常", "结算选择时出现异常：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def queue_followup(self, event):
            """把连锁事件包装成普通事件卡继续交互。"""
            try:
                report = DailyReport(self.player)
                report.event_name = event["name"]
                desc = self.sim.dice.pick(event["descs"], "事件描述")[0]
                self.player.remember_event(event["name"], event["category"], desc)
                card = {
                    "tone": "event", "event_id": event["id"], "event_name": event["name"],
                    "category": event["category"], "special": event["special"],
                    "desc": desc, "secret_reason": "事件连锁：上一步的结果引发了新的变故。",
                    "roll_lines": self.sim.dice.today_lines(), "settlement_lines": [],
                    "choices": [],
                }
                for idx, choice in enumerate(event["choices"]):
                    hints = describe_effects(choice.get("outcomes", [{}])[0].get("effects", {}))
                    card["choices"].append({
                        "index": idx, "label": choice["label"],
                        "hint": choice.get("hint", ""), "detail": "、".join(hints),
                        "need_money": choice.get("need_money", 0),
                        "need_disease": choice.get("need_disease", False),
                        "roll": choice.get("roll", "d6"),
                    })
                self.sim.pending = {"event": event, "card": card, "report": report}
                self.show_event_dialog(card)
            except Exception as exc:
                self.alert("连锁事件异常", "处理连锁事件时出错：%s" % exc)

        def show_result_dialog(self, result):
            """结算弹窗：显示结果描述与属性变化。"""
            lines = ["【%s】" % result.get("event_name", "事件")]
            lines.append("")
            lines.append(result.get("outcome_desc", ""))
            dice_lines = result.get("dice_lines") or []
            if dice_lines:
                lines.append("")
                lines.append("—— 骰子判定 ——")
                for ln in dice_lines:
                    lines.append("    " + ln)
            if result.get("extra_lines"):
                lines.append("")
                for ln in result["extra_lines"]:
                    if ln:
                        lines.append("    · %s" % ln)
            delta = result.get("delta") or {}
            lines.append("")
            lines.append("—— 属性变化 ——")
            lines.append("    健康 %s    幸福 %s" % (
                fmt_signed(delta.get("health", 0), 1), fmt_signed(delta.get("happy", 0), 1)))
            lines.append("    金钱 %s    体温 %s" % (
                fmt_signed(delta.get("money", 0), 2), fmt_signed(delta.get("temp", 0), 2)))
            p = self.player
            lines.append("")
            lines.append("—— 当前状态 ——")
            lines.append("    健康 %.1f / 幸福 %.1f / 金钱 %.2f / 体温 %.2f℃" % (
                p.health, p.happy, p.money, p.temp))
            lines.append("    状态：%s    疾病：%s" % (p.status_text, p.disease_names()))
            report = result.get("report")
            if report is not None and report.lines:
                lines.append("")
                lines.append("—— 今日结算明细 ——")
                for ln in report.lines:
                    lines.append("    %s" % ln)

            title = "结算：%s" % result.get("event_name", "事件")
            if result.get("special"):
                title = "隐藏剧情结算"
            self.show_panel(title, "\n".join(lines), [("确定", "ok", None)],
                            width=800, height=620)

        # ------------------------------------------------------------------
        # 当天操作（一天最多 8 次，不推进日期） / 跳过这一天 / 时间跳跃
        # ------------------------------------------------------------------
        def on_action(self, key):
            """在当天执行一次操作：消耗行动点，**不推进日期**，可以连续点。"""
            if self.locked or self.player is None:
                return
            if self.player.dead:
                self.show_death_panel()
                return
            # 只有在"还没开始今天 / 有未处理事件 / 有未选择的事件卡"时才拦
            if self.sim is not None and self.sim.pending is not None:
                self.alert("事件尚未处理",
                           "今天的事件还没有做出选择，请先在事件弹窗里选择处理方式。")
                return
            if self.pending_card is not None:
                card = self.pending_card
                self.alert("事件尚未处理", "你还有一个事件没有做出选择。")
                self.show_event_dialog(card)
                return
            if self.state == "idle":
                self.alert("尚未开始人生",
                           "请先创建人物或读取存档，再安排当天行动。")
                return
            try:
                self.locked = True
                # ---- 「夫妻亲密」：先让玩家选择避孕方式 ----
                if key == "intimacy":
                    self.locked = False
                    self._do_intimacy_flow()
                    return
                result = self.sim.apply_daily_action(key)
                if result.get("tone") == "warn":
                    self.locked = False
                    self.update_hud()
                    self.alert("无法执行该操作", result.get("text", ""))
                    return
                self.update_hud()
                # ---- 结果直接写进主窗口（不再弹模态对话框，避免挡住下一次点击）----
                self.clear_main()
                self.write_main("═══ %s ═══　行动点 %d/%d" % (
                    self.player.date_full, int(self.player.action_points),
                    ACTION_POINTS_PER_DAY), "h")
                self.write_main("今天是第 %d 次操作：【%s】" % (
                    int(self.player.actions_today), result.get("title", "行动")), "h")
                for ln in (result.get("settlement_lines") or []):
                    tag = None
                    if any(w in ln for w in ("死亡", "过低", "过高", "发作", "恶化")):
                        tag = "bad"
                    elif any(w in ln for w in ("痊愈", "休息", "收入", "自愈", "学习", "社交")):
                        tag = "good"
                    self.write_main("    " + ln, tag)
                if result.get("dice_lines"):
                    self.write_main("")
                    self.write_main("—— 骰子 ——", "dim")
                    for ln in result["dice_lines"]:
                        self.write_main("    " + ln, "mono")
                left = int(self.player.action_points)
                if left > 0:
                    tip = ("还可以继续点下面的操作按钮（今天还能操作 %d 次）；"
                           "行动点用完后直接点「推进到下一天」。" % left)
                else:
                    tip = "今天的行动点已经用完，点「推进到下一天」抽取新的事件。"
                self.write_main("")
                self.write_main("　→ " + tip, "warn")
                self.set_status("第 %d 次操作完成（未推进日期）。行动点 %d/%d。" % (
                    int(self.player.actions_today), left, ACTION_POINTS_PER_DAY), tip)
                self.refresh_action_points()
                self.auto_save()
                self.locked = False
                if self.player.dead:
                    self.handle_death(self.sim.last_report)
            except Exception as exc:
                self.locked = False
                self.alert("运行时异常", "执行行动时出现异常：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def _do_intimacy_flow(self):
            """
            「夫妻亲密」完整流程：
              1) 检查是否成年/有伴侣/不在孕期/今天是否已做过
              2) 让玩家选择避孕方式（避孕套/安全期/短效药/不避孕）
              3) 执行亲密：提升幸福 + 按概率受孕
            """
            p = self.player
            ok, why = self.sim.can_be_intimate()
            if not ok:
                self.alert("暂时不行", why)
                return
            rate_rows = []
            for name, success, desc in CONTRACEPTION_OPTIONS:
                current = "（当前使用）" if name == p.contraception else ""
                rate_rows.append("%-10s 避孕成功率 %-5s %s %s" % (
                    name, pct_text(success) if success > 0 else "0%", desc, current))
            body = ("与伴侣的亲密时光可以提升幸福度，也可能迎来新生命。\n\n"
                    "当前状况：\n"
                    "    年龄 %d 岁　体质 %.0f 分　健康 %.1f　幸福 %.1f\n"
                    "    伴侣：%s　　子女：%d 人\n"
                    "    本次未避孕时的受孕概率约为 %.1f%%\n\n"
                    "请选择避孕方式：\n%s\n\n"
                    "（生育上限年龄 %d 岁；孩子越多，再次受孕概率越低）"
                    % (p.age, p.constitution, p.health, p.happy,
                       p.partner_name or "配偶", len(p.child_list),
                       conception_rate(p.age) * 100,
                       "\n".join("    " + r for r in rate_rows),
                       CONCEPTION_MAX_AGE_FEMALE))
            buttons = [("%s（%s）" % (name, pct_text(success) if success > 0 else "不避孕"),
                        "contra_%s" % name, None)
                       for name, success, _desc in CONTRACEPTION_OPTIONS]
            buttons.append(("算了，改天", "cancel", None))
            panel = self.show_panel("夫妻亲密", body, buttons, width=760, height=620)
            self.root.wait_window(panel)
            result = panel.result
            if not result or result == "cancel" or not str(result).startswith("contra_"):
                return
            choice_name = str(result)[len("contra_"):]
            try:
                self.locked = True
                r = self.sim.do_intimacy(choice_name)
                self.update_hud()
                if r.get("tone") == "warn":
                    self.locked = False
                    self.alert("暂时不行", r.get("text", ""))
                    return
                lines = r.get("settlement_lines") or []
                head = "【夫妻亲密】避孕方式：%s\n\n" % choice_name
                if r.get("conceived"):
                    head = "【喜讯】你们要当父母了！\n\n"
                body2 = head + "\n".join(lines)
                self.clear_main()
                self.write_main("═══ %s ═══" % self.player.date_full, "h")
                self.write_main(head.strip(), "good" if r.get("conceived") else "h")
                for ln in lines:
                    self.write_main("    " + ln)
                self.set_status("亲密时光结束。行动点 %d/%d。" % (
                    int(p.action_points), ACTION_POINTS_PER_DAY),
                    "怀孕后可在状态面板查看孕期进度；孕期需要 9 个月。")
                self.show_panel("夫妻亲密结果", body2, [("确定", "ok", None)],
                                width=740, height=560)
                self.refresh_action_points()
                self.auto_save()
                self.locked = False
            except Exception as exc:
                self.locked = False
                self.alert("运行时异常", "执行亲密操作时出现异常：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def on_skip_day(self, *_):
            """
            「略过剩余行动点，直接到下一天」：
            当天还有行动点时直接进入第二天（不消耗剩余点数）。
            这是可选操作；行动点用完后直接点「推进到下一天」即可。
            """
            if self.locked or self.player is None:
                return
            if self.player.dead:
                self.show_death_panel()
                return
            if self.sim.pending is not None:
                self.alert("事件尚未处理",
                           "今天还有一个事件没有做出选择，请先在事件弹窗里选择处理方式。")
                return
            left = int(getattr(self.player, "action_points", 0))
            try:
                self.locked = True
                result = self.sim.skip_day()
                self.update_hud()
                self.state = "event"
                if result.get("tone") == "dead":
                    self.locked = False
                    self.refresh_action_points()
                    self.handle_death(self.sim.last_report)
                    return
                lines = result.get("settlement_lines") or []
                self.clear_main()
                self.write_main("═══ %s ═══" % self.player.date_full, "h")
                self.write_main("已略过剩余的 %d 点行动点，时间来到新的一天。" % left, "dim")
                for ln in lines:
                    self.write_main("    " + ln)
                self.write_main("")
                self.write_main("　→ 新的一天行动点已重置为 %d，点「推进一天」抽取今天的事件。"
                                % ACTION_POINTS_PER_DAY, "warn")
                self.set_status("已进入 %s。" % self.player.date_full,
                                "行动点已重置为 %d。" % ACTION_POINTS_PER_DAY)
                self.refresh_action_points()
                self.auto_save()
                self.locked = False
            except Exception as exc:
                self.locked = False
                self.alert("运行时异常", "略过当天时出现异常：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def on_skip_months(self, *_):
            self._do_time_skip("months")

        def on_skip_years(self, *_):
            self._do_time_skip("years")

        def _do_time_skip(self, unit):
            """按月 / 按年跳过：读取输入框，做范围校验后执行。"""
            if self.locked or self.player is None:
                return
            if self.player.dead:
                self.show_death_panel()
                return
            if self.sim.pending is not None:
                self.alert("事件尚未处理",
                           "今天还有一个事件没有做出选择，请先处理完再跳跃时间。")
                return
            var = self.skip_months_var if unit == "months" else self.skip_years_var
            raw = (var.get() or "").strip()
            try:
                amount = int(float(raw))
            except Exception:
                self.alert("输入无效",
                           "「%s」不是有效的数字：%r\n\n请输入 1 以上的整数。"
                           % ("月数" if unit == "months" else "年数", raw))
                return
            if amount <= 0:
                self.alert("输入无效", "跳过的时长必须大于 0，当前输入为 %s。" % amount)
                return
            limit = SKIP_MAX_MONTHS if unit == "months" else SKIP_MAX_YEARS
            if amount > limit:
                self.alert("超出上限",
                           "一次最多跳过 %d %s（你输入了 %d）。\n已自动按上限处理；"
                           "如需跳过更长时间，可以重复操作。"
                           % (limit, "个月" if unit == "months" else "年", amount))
                amount = limit
                var.set(str(amount))
            # 确认
            panel = self.show_panel(
                "时间跳跃确认",
                "即将跳过 %d %s。\n\n"
                "跳过期间的处理方式：\n"
                "    · 按天推进日期，逐月结算工资与生活支出（含父母供养）\n"
                "    · 疾病按天结算（可能自愈、恶化或自动送医）\n"
                "    · 到年龄节点自动推进人生阶段（升学 / 毕业 / 退休）\n"
                "    · 但**不会**生成跳过期间的逐日事件（不占用你的选择）\n\n"
                "当前：%s（%d 岁）\n预计跳到：%s" % (
                    amount, "个月" if unit == "months" else "年",
                    self.player.date_full, self.player.age,
                    self._estimate_skip_target(amount, unit)),
                [("确定跳过", "ok", None), ("取消", "cancel", None)],
                width=680, height=520)
            self.root.wait_window(panel)
            if panel.result != "ok":
                return
            try:
                self.locked = True
                if unit == "months":
                    result = self.sim.skip_time(months=amount)
                else:
                    result = self.sim.skip_time(years=amount)
                self.update_hud()
                self.state = "event"
                self.refresh_action_points()
                if result.get("tone") == "dead":
                    self.locked = False
                    self.handle_death(self.sim.last_report)
                    return
                lines = result.get("settlement_lines") or []
                body = "【时间跳跃：%d %s】\n\n" % (
                    amount, "个月" if unit == "months" else "年")
                body += "\n".join(lines[-40:])
                self.clear_main()
                self.write_main("═══ 时间跳跃 ═══", "h")
                self.write_main("跳过 %d %s，现在是 %s（%d 岁，%s阶段）" % (
                    amount, "个月" if unit == "months" else "年",
                    self.player.date_full, self.player.age, stage_name(self.player.stage)))
                for ln in lines[-30:]:
                    self.write_main("    " + ln)
                self.set_status("时间跳跃完成，现在是 %s。" % self.player.date_full,
                                "行动点已重置，可以继续操作或「推进一天」。")
                self.show_panel("时间跳跃结果", body, [("确定", "ok", None)],
                                width=780, height=620)
                self.auto_save()
                self.locked = False
            except Exception as exc:
                self.locked = False
                self.alert("运行时异常", "时间跳跃时出现异常：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def _estimate_skip_target(self, amount, unit):
            """估算跳过后的日期文本（仅用于确认弹窗展示）。"""
            p = self.player
            months = amount if unit == "months" else amount * MONTHS_PER_YEAR
            total = p.month - 1 + months
            year = p.year + total // MONTHS_PER_YEAR
            month = total % MONTHS_PER_YEAR + 1
            days = amount * DAYS_PER_MONTH if unit == "months" else amount * DAYS_PER_YEAR
            age = p.age + days // DAYS_PER_YEAR
            return "%d 年 %d 月 %d 日（约 %d 岁）" % (year, month, p.day, age)

        # ------------------------------------------------------------------
        # 菜单功能
        # ------------------------------------------------------------------
        def on_status(self, *_):
            if self.player is None:
                self.alert("尚未开始", "还没有开始游戏。请先创建人物或读取存档。")
                return
            text = self.sim.status_panel()
            self.show_panel("当前状态", text, [("确定", "ok", None)],
                            width=720, height=620)

        def on_cure(self, *_):
            if self.player is None:
                self.alert("尚未开始", "还没有开始游戏。")
                return
            p = self.player
            if not p.diseases:
                self.alert("无需治疗", "你目前没有任何疾病，身体状况良好。\n\n"
                                       "疾病：无\n健康：%.1f" % p.health)
                return
            lines = ["当前疾病：", ""]
            buttons = []
            for d in p.diseases:
                lines.append("    · %s（%s）剩余 %d 天" % (d["name"], d["kind"], d["days"]))
                lines.append("        每日健康 -%.1f / 幸福 -%d，治愈费 %.2f" % (
                    d["hp_per_day"], d["happy_per_day"], d["cure_cost"]))
                affordable = p.money >= d["cure_cost"]
                label = "%s治疗%s（%.2f）" % ("" if affordable else "[金钱不足] ", d["name"], d["cure_cost"])
                buttons.append((label, "cure_%s" % d["id"], None))
            lines.append("")
            lines.append("当前金钱：%.2f" % p.money)
            if p.money < min(d["cure_cost"] for d in p.diseases):
                lines.append("提示：金钱不足，建议先「工作赚钱」或选择硬扛（有风险）。", )
            buttons.append(("取消", "cancel", None))

            panel = self.show_panel("花钱治病", "\n".join(lines), buttons,
                                    width=740, height=520)
            self.root.wait_window(panel)
            result = panel.result
            if not result or not str(result).startswith("cure_"):
                return
            disease_id = str(result)[5:]
            ok, msg, cost = self.sim.try_cure(disease_id)
            self.update_hud()
            if ok:
                self.alert("治疗成功", msg)
                self.write_main("【治疗】%s" % msg, "good")
            else:
                self.alert("治疗失败", msg)

        def on_log(self, *_):
            if self.player is None:
                self.alert("尚未开始", "还没有开始游戏。")
                return
            text = "═══ 人生日志（最近记录）═══\n\n" + self.sim.diary_panel(80)
            text += "\n\n完整日志文件：\n%s" % self.log_path
            if self.player.milestones:
                text += "\n\n═══ 生平大事记 ═══\n"
                for item in self.player.milestones[-40:]:
                    text += "  · %s  %s\n" % (item.get("date", ""), item.get("text", ""))
            text += "\n\n═══ 已触发事件（最近 40 条）═══\n"
            for item in self.player.event_history[-40:]:
                text += "  · %s｜%s｜%s\n" % (item.get("date", ""), item.get("name", ""),
                                              item.get("summary", ""))
            self.show_panel("人生日志", text, [("确定", "ok", None)],
                            width=820, height=640)

        def auto_save(self):
            """
            自动存档：每天结束后静默保存一次，即使玩家直接关窗口也不会丢进度。
            失败只提示一次，不打断游戏。
            """
            if self.player is None or self.player.dead:
                return
            ok, msg = self.do_save(verbose=False)
            self.last_auto_save_ok = ok
            if ok:
                self.set_substatus("已自动存档：%s（Ctrl+S 手动保存，Ctrl+Q 保存并退出）"
                                   % os.path.basename(self.save_path))
            elif not getattr(self, "auto_save_warned", False):
                self.auto_save_warned = True
                self.write_main("【提示】自动存档失败：%s（可点「保存并退出」重试）" % msg, "warn")

        def on_save(self, *_):
            if self.player is None:
                self.alert("尚未开始", "还没有开始游戏，无法保存。\n\n"
                                       "请先点「开始新的人生」，或「读取存档」继续上一局。")
                return
            self.do_save(verbose=True)

        def do_save(self, verbose=False):
            try:
                ok, msg = save_game(self.save_path, self.player, self.log)
            except Exception as exc:
                ok, msg = False, "保存存档时出现异常：%s" % exc
            if verbose:
                self.alert("保存进度" if ok else "保存失败", msg)
            if ok:
                self.write_main("【存档】%s" % msg.replace("\n", " "), "good")
            return ok, msg

        def on_load(self, *_):
            self.do_load(verbose=True)

        def do_load(self, verbose=False):
            if self.player is not None and not self.player.dead:
                # 询问是否覆盖当前进度
                panel = self.show_panel(
                    "读取进度",
                    "读取存档会覆盖当前正在进行的这一局人生。\n\n"
                    "当前：%s（%s）\n存档：%s\n\n确定要读取吗？" % (
                        self.player.date_full, self.player.name, self.save_path),
                    [("确定读取", "ok", None), ("取消", "cancel", None)],
                    width=620, height=380)
                self.root.wait_window(panel)
                if panel.result != "ok":
                    return
            try:
                player, msg = load_game(self.save_path, rng=random.Random())
                if player is None:
                    self.alert("读取失败", msg)
                    return
                self.player = player
                self.log = LifeLog(self.log_path, player.name, get_city(player.city)["name"])
                self.sim = Simulator(self.player, self.log, self.base_dir)
                self.death_panel_shown = False
                self.pending_card = None
                self.hide_start_controls()
                self.state = "event"
                self.update_hud()
                self.clear_main()
                self.write_main("═══ 读取存档成功 ═══", "h")
                self.write_main(msg)
                self.write_main("")
                self.write_main(self.sim.status_panel())
                self.set_status("已读取存档，继续 %s 的人生。" % self.player.date_full,
                                "点击「推进一天」继续游戏。")
                self.set_actions_enabled(False)
                if verbose:
                    self.alert("读取成功", msg)
                if self.player.dead:
                    self.handle_death(None)
            except Exception as exc:
                self.alert("读取失败", "读档过程中出现异常：\n%s\n\n%s"
                           % (exc, traceback.format_exc(limit=4)))

        def on_help(self, *_):
            text = []
            text.append("═══ 玩法说明 ═══")
            text.append("")
            text.append("1. 时间：每天可推进一次；30 天 = 1 个月，12 个月 = 1 年，开局 0 岁。")
            text.append("2. 每日流程：点「推进一天」→ 掷骰抽事件 → 事件弹窗做选择 → "
                        "结算弹窗查看变化 → 选择当日行动（休息 / 工作 / 娱乐）。")
            text.append("3. 骰子：d100 判定事件大类与结果，d4/d6/d10/d20 判定效果强度；")
            text.append("   掷出 100 / 99 / 2 / 1 等极端点数会触发隐藏特殊剧情。")
            text.append("4. 属性边界：健康 0~100（归零死亡）；幸福 0~100（长期低于 20 掉血）；")
            text.append("   金钱无上下限（可负债）；体温正常 36.0~37.0（过高/过低每日掉血）。")
            text.append("5. 疾病：轻症可自愈，重症必须花钱治疗；重症拖延可能导致死亡。")
            text.append("6. 结算：每月初自动结算工资与生活支出；生日触发特殊事件。")
            text.append("7. 存档：save.json；日志：life_log.txt（死亡时自动追加人生总结）。")
            text.append("")
            text.append("═══ 城市气候 ═══")
            for city_id in CITY_ORDER:
                city = CITIES[city_id]
                text.append("  · %s（%s）：%s" % (city["name"], city["tag"], city["desc"]))
            text.append("")
            text.append("═══ 疾病速查 ═══")
            text.append(disease_table_text())
            text.append("")
            text.append("（帮助面板底部另有「完整疾病表」按钮，可查看全部 %d 种疾病）"
                        % len(COMMON_DISEASE_KEYS))
            text.append("")
            text.append("═══ 行动点（同一天可以连续操作）═══")
            text.append("  * 每个游戏内的一天有 8 点行动点，每点可做 1 次操作，")
            text.append("    也就是说**同一天可以连续点 8 次**：休息/工作/娱乐/学习/社交/锻炼。")
            text.append("  * 操作**不会推进日期**，可以随便连着点，中途不需要点跳过。")
            text.append("  * 行动点用完后，按钮会变灰，此时直接点「推进到下一天」")
            text.append("    就会抽取新一天的事件并重置行动点（不需要点「略过」）。")
            text.append("  * 「略过剩余行动点，直接到下一天」是可选操作：")
            text.append("    当天还剩点数但你不想用了，可以点它提前进入第二天。")
            text.append("  * 同一天重复做同一件事收益递减（第 2 次 85%，第 3 次 72%…最低 40%）。")
            text.append("")
            text.append("═══ 家庭与生育 ═══")
            text.append("  1. 16 岁后可恋爱，22 岁后可结婚；结婚后每天可进行「夫妻亲密」（消耗 1 点行动点，每天最多 1 次）。")
            text.append("  2. 亲密会提升幸福度，并可能受孕（可选择避孕方式：安全期 55%、"
                        "避孕套 92%、短效避孕药 98%）。")
            text.append("  3. 受孕概率随年龄变化：20~25 岁约 20~22%，35 岁 14%，40 岁 8%，"
                        "45 岁以上基本不会怀孕。")
            text.append("  4. 孕期 270 天（9 个月），期间每月有孕期反应，并有流产风险；"
                        "分娩存在并发症风险（年龄越大越高）。")
            text.append("  5. 孩子出生后会继承父母体质，每年成长都会有反馈；"
                        "养育开销按年龄递增，可用「陪伴孩子」提升幸福。")
            text.append("")
            text.append("═══ 文件位置 ═══")
            text.append("  数据目录：%s" % self.base_dir)
            text.append("  存档文件：%s" % self.save_path)
            text.append("  日志文件：%s" % self.log_path)
            panel = self.show_panel("帮助 / 玩法说明", "\n".join(text),
                                    [("完整疾病表", "diseases", None), ("确定", "ok", None)],
                                    width=820, height=660)
            self.root.wait_window(panel)
            if panel.result == "diseases":
                self.on_disease_table()

        def on_disease_table(self, *_):
            """展示全部疾病（按分类）。"""
            text = ["═══ 完整疾病表（共 %d 种常见疾病）═══" % len(COMMON_DISEASE_KEYS), ""]
            text.append(disease_table_text(full=True))
            text.append("说明：每日健康扣除已乘以全局系数 %.2f；"
                        "体质越好，每日扣血越少、病程越短。" % DISEASE_HEALTH_IMPACT)
            self.show_panel("完整疾病表", "\n".join(text), [("确定", "ok", None)],
                            width=900, height=700)

        def on_quit(self, *_):
            """
            退出游戏：任何时刻都可以选择「保存并退出」。
              * 正在游戏 -> 询问是否保存（默认推荐保存）
              * 已死亡   -> 直接退出
              * 未开始   -> 直接退出
            任何异常都会被捕获，保证窗口一定能正常关闭。
            """
            try:
                if self.player is not None and not self.player.dead:
                    saved_note = ""
                    if save_exists(self.save_path):
                        try:
                            mtime = datetime.fromtimestamp(
                                os.path.getmtime(self.save_path)).strftime("%Y-%m-%d %H:%M:%S")
                            saved_note = "\n已有存档时间：%s" % mtime
                        except Exception:
                            saved_note = ""
                    panel = self.show_panel(
                        "退出游戏",
                        "退出前要保存当前进度吗？\n\n"
                        "当前人生：%s（%s）\n"
                        "当前时间：%s\n"
                        "存档位置：%s%s\n\n"
                        "选择「保存并退出」可以随时关闭游戏，下次用「读取存档」继续。"
                        % (self.player.name, self.player.life_stage,
                           self.player.date_full, self.save_path, saved_note),
                        [("保存并退出", "save_quit", None), ("直接退出", "quit", None),
                         ("取消", "cancel", None)], width=660, height=460)
                    self.root.wait_window(panel)
                    choice = panel.result
                    if choice == "cancel" or not choice:
                        return
                    if choice == "save_quit":
                        ok, msg = self.do_save(verbose=False)
                        if not ok:
                            # 保存失败时明确告知，并让玩家决定是否仍要退出
                            fail = self.show_panel(
                                "保存失败",
                                "%s\n\n可能是目录不可写或磁盘权限问题。\n"
                                "你仍然可以直接退出（本局进度会丢失）。" % msg,
                                [("直接退出", "quit", None), ("取消", "cancel", None)],
                                width=620, height=380)
                            self.root.wait_window(fail)
                            if fail.result != "quit":
                                return
            except Exception as exc:
                print("退出流程异常（已忽略）：%s" % exc)
            try:
                self.root.destroy()
            except Exception:
                pass

        def on_close(self):
            """点击窗口右上角 × 时同样提供保存并退出。"""
            self.on_quit()

        # ------------------------------------------------------------------
        # 死亡与人生总结
        # ------------------------------------------------------------------
        def handle_death(self, report=None):
            # 同一局人生只弹一次死亡总结面板
            if getattr(self, "death_panel_shown", False) and self.state == "dead":
                return
            self.death_panel_shown = True
            self.state = "dead"
            self.set_actions_enabled(False)
            try:
                self.btn_roll.configure(state="disabled")
            except Exception:
                pass
            summary = ""
            try:
                summary = self.sim.finish_life()
            except Exception as exc:
                summary = "（生成人生总结时出现异常：%s）" % exc
            self.update_hud()
            self.clear_main()
            self.write_main("═══ 人生落幕 ═══", "h")
            self.write_main("享年 %d 岁，%s" % (self.player.age, self.player.death_reason), "bad")
            self.write_main("")
            self.write_main(summary or self.sim.status_panel())
            self.set_status("人生已经结束，享年 %d 岁。" % self.player.age,
                            "可以选择重新开始或退出游戏。")
            self.show_death_panel(summary)

        def show_death_panel(self, summary=None):
            p = self.player
            if p is None:
                return
            if summary is None:
                try:
                    summary = self.sim.finish_life()
                except Exception:
                    summary = ""
            text = []
            text.append("── 人生落幕 ──")
            text.append("")
            text.append("姓名：%s        城市：%s" % (p.name, get_city(p.city)["name"]))
            text.append("享年：%d 岁（%s）" % (p.age, p.life_stage))
            text.append("离世：%s" % (p.death_reason or "自然衰老"))
            text.append("")
            text.append("最终属性：健康 %.1f / 幸福 %.1f / 金钱 %.2f / 体温 %.2f℃" % (
                p.health, p.happy, p.money, p.temp))
            text.append("身价估算：%.2f" % p.net_worth())
            text.append("")
            text.append(summary or "（人生总结已写入日志文件：%s）" % self.log_path)
            buttons = [("重新开始", "restart", None), ("保存并退出", "save_quit", None),
                       ("退出游戏", "quit", None)]
            panel = self.show_panel("人生总结", "\n".join(text), buttons,
                                    width=820, height=640)
            self.root.wait_window(panel)
            if panel.result == "restart":
                self.show_start_screen()
            elif panel.result == "save_quit":
                self.do_save(verbose=False)
                try:
                    self.root.destroy()
                except Exception:
                    pass
            elif panel.result == "quit":
                self.root.destroy()

        # ------------------------------------------------------------------
        def run(self):
            self.root.mainloop()


# ==============================================================================
# 14. 自检模块（--selftest）：无需界面即可验证核心逻辑
# ==============================================================================

def make_console_safe():
    """
    控制台兼容处理：
      1. Windows 默认控制台编码可能是 GBK，直接 print 特殊符号会抛
         UnicodeEncodeError；这里把标准输出/错误切到 UTF-8（失败则替换字符）。
      2. 用 --windowed 打包的 exe 没有控制台，sys.stdout/stderr 可能是 None，
         此时换成空对象，避免 print 触发 "AttributeError: 'NoneType'"。
    """
    if sys.stdout is None or sys.stderr is None:
        class _NullStream(object):
            def write(self, *_a, **_k):
                return 0

            def flush(self):
                pass

            def reconfigure(self, *_a, **_k):
                pass

            def isatty(self):
                return False

            def fileno(self):
                raise OSError("no console")
        if sys.stdout is None:
            sys.stdout = _NullStream()
        if sys.stderr is None:
            sys.stderr = _NullStream()
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def run_selftest(base_dir=None, days=2000, verbose=True):
    """
    无界面自检：
        * 检测数据目录与文件读写
        * 用多个随机种子跑完整人生，验证数值边界、存档兼容与日志输出
    返回退出码（0 表示通过）。
    """
    out = []
    top_dir, notes = resolve_base_dir() if base_dir is None else (base_dir, [])
    work_dir = os.path.join(top_dir, "_selftest")
    if not _try_makedirs(work_dir):
        work_dir = top_dir
    out.append("自检数据目录：%s" % work_dir)
    for note in notes:
        out.append("目录提示：%s" % note)

    failures = []
    save_path = os.path.join(work_dir, SAVE_FILE_NAME)
    log_path = os.path.join(work_dir, LOG_FILE_NAME)
    for path in (save_path, log_path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    for seed in (1, 7, 42, 2024):
        rng = random.Random(seed)
        player = Player(name="测试者%d" % seed, city=CITY_ORDER[seed % len(CITY_ORDER)], rng=rng)
        log = LifeLog(log_path, player.name, get_city(player.city)["name"])
        log.start(player)
        sim = Simulator(player, log, work_dir, seed=seed)
        steps = 0
        guard = 0
        money_by_age = {}
        category_ages = {}          # 记录各大类事件第一次出现的年龄（用于年龄合理性校验）
        while not player.dead and steps < days:
            guard += 1
            if guard > days * 4 + 50:
                failures.append("seed=%s 循环保护触发（状态机可能卡住）" % seed)
                break
            # ---- 1) 推进一天：抽事件 ----
            card = sim.step_roll()
            if card.get("tone") == "dead":
                break
            if card.get("tone") == "event":
                category_ages.setdefault(card.get("category", "?"), player.age)
                # 模拟玩家点击一个合法选项（越界或金钱不足时自动改选）
                choices = card.get("choices") or []
                idx = sim.dice.roll(len(choices) or 1, 1, 0, "自检选择").value - 1 if choices else 0
                res = sim.resolve_choice(max(0, min(idx, len(choices) - 1)))
                if res.get("tone") == "warn":
                    res = sim.resolve_choice(0)
                if player.dead:
                    break
            # ---- 2) 安排当天行动 ----
            action = ("rest", "work", "fun")[steps % 3]
            result = sim.apply_daily_action(action)
            steps += 1
            money_by_age[player.age] = max(money_by_age.get(player.age, 0.0), player.money)

            # ---- 数值边界校验 ----
            if not (0 <= player.health <= 100):
                failures.append("seed=%s 健康越界：%s" % (seed, player.health))
            if not (0 <= player.happy <= 100):
                failures.append("seed=%s 幸福越界：%s" % (seed, player.happy))
            if not (TEMP_HARD_LOW <= player.temp <= TEMP_HARD_HIGH):
                failures.append("seed=%s 体温越界：%s" % (seed, player.temp))
            if player.age > AGE_MAX_LIMIT + 1:
                failures.append("seed=%s 年龄异常：%s" % (seed, player.age))
            if player.age < 16 and player.employed:
                failures.append("seed=%s 未成年人却处于在职状态" % seed)
            if result.get("tone") == "dead":
                break

        # ---- 阶段与事件大类的合理性校验（工作类不应出现在 16 岁之前）----
        for category, age in category_ages.items():
            if category in ("隐藏", "综合", "?"):
                continue
            if category == "工作" and age < 16:
                failures.append("seed=%s %d 岁触发了工作类事件" % (seed, age))
                continue
            # 用"该年龄的标准阶段"规则做严格校验
            std_stage = stage_of_age(age)
            if category not in categories_for_stage(std_stage, age):
                failures.append("seed=%s %d 岁（%s 阶段）触发了不该出现的「%s」类事件"
                                % (seed, age, stage_name(std_stage), category))

        # ---- 经济合理性校验：儿童不应暴富 ----
        child_wealth = max([v for k, v in money_by_age.items() if k < 16] or [0.0])
        if child_wealth > 150000:
            failures.append("seed=%s 未成年阶段金钱异常偏高：%.2f" % (seed, child_wealth))

        # ---- 存盘 / 读档一致性 ----
        ok, msg = save_game(save_path, player, log)
        if not ok:
            failures.append("seed=%s 保存失败：%s" % (seed, msg))
        else:
            loaded, lmsg = load_game(save_path, rng=random.Random(seed))
            if loaded is None:
                failures.append("seed=%s 读档失败：%s" % (seed, lmsg))
            else:
                if abs(loaded.health - player.health) > 0.01:
                    failures.append("seed=%s 读档健康不一致" % seed)
                if abs(loaded.money - player.money) > 0.01:
                    failures.append("seed=%s 读档金钱不一致" % seed)
                if loaded.age != player.age or loaded.month != player.month:
                    failures.append("seed=%s 读档时间不一致" % seed)
                if len(loaded.diseases) != len(player.diseases):
                    failures.append("seed=%s 读档疾病数量不一致" % seed)
        survived = not player.dead
        if survived:
            player.dead = True
            player.death_reason = "自检强制结束（活到了 %d 岁）" % player.age
        sim.finish_life()
        out.append("seed=%-5s %s：%d 岁 · %s · 度过 %d 天 · 健康 %.1f / 幸福 %.1f / 金钱 %.2f · 事件 %d 个" % (
            seed, "存活" if survived else "死亡", player.age, player.life_stage,
            player.total_days, player.health, player.happy, player.money,
            len(player.event_history)))
        out.append("          事件大类首次出现年龄：%s" % (
            "，".join("%s@%d岁" % (k, v) for k, v in sorted(category_ages.items())) or "无"))

    # ---- 存档损坏容错测试 ----
    broken = os.path.join(work_dir, "broken_save.json")
    try:
        with open(broken, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是合法的 JSON ")
        bad, bad_msg = load_game(broken, rng=random.Random(1))
        if bad is not None:
            failures.append("损坏存档未被正确识别")
        else:
            out.append("损坏存档容错：正常（提示：%s）" % bad_msg.splitlines()[0])
    except Exception as exc:
        failures.append("损坏存档测试异常：%s" % exc)

    # ---- 日志文件检查 ----
    if os.path.isfile(log_path):
        size = os.path.getsize(log_path)
        out.append("life_log.txt 已生成：%d 字节" % size)
        if size < 500:
            failures.append("日志文件内容过少（%d 字节）" % size)
    else:
        failures.append("未生成 life_log.txt")

    # ---- 事件库完整性检查 ----
    categories = {}
    for eid in EVENT_ORDER:
        ev = EVENTS[eid]
        categories[ev["category"]] = categories.get(ev["category"], 0) + 1
        for choice in ev["choices"]:
            if not choice.get("outcomes"):
                failures.append("事件 %s 的选项缺少结果区间" % eid)
            for outcome in choice["outcomes"]:
                lo, hi = outcome["range"]
                if lo > hi:
                    failures.append("事件 %s 结果区间非法：%s" % (eid, outcome["range"]))
    out.append("事件库：共 %d 个可抽取事件 %s" % (len(EVENT_ORDER), categories))
    if len(EVENT_ORDER) < 30:
        failures.append("事件数量不足：%d" % len(EVENT_ORDER))

    # ---- 骰子极端点数测试 ----
    hidden_hits = 0
    for value in (1, 2, 99, 100):
        res = DiceResult(100, value)
        table = DiceSystem.HIDDEN_TABLE[100]
        if value in table:
            hidden_hits += 1
    if hidden_hits != 4:
        failures.append("隐藏特殊点数表不完整")
    out.append("隐藏特殊点数：d100 的 1 / 2 / 99 / 100 均已配置特殊剧情")

    # ---- 清理自检产物 ----
    for path in (save_path, broken):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    if verbose:
        print("\n".join(out))
        print("")
    if failures:
        print("自检失败，共 %d 项：" % len(failures))
        for item in failures:
            print("  [X] %s" % item)
        return 1
    if verbose:
        print("[OK] 自检全部通过：数值边界、存档读写、损坏容错、日志输出、事件库结构均正常。")
    return 0


# ==============================================================================
# 15. 程序入口
# ==============================================================================

BANNER = """
================================================================================
                    Life Simulator  (Chuang-Kou-Shi Ren-Sheng Mo-Ni-Qi)
================================================================================
 How to play : pick a city -> click "Advance 1 day" -> roll the dice for an event
               -> choose an option -> then spend up to 8 actions that same day
 Dice        : d10000 decides whether an event happens, d100 the category,
               d4/d6/d10/d20 the effect strength; extreme rolls unlock secrets
 Life        : health 0 = death, low happiness drains health, body temp matters
 Save file   : save.json        Life log : life_log.txt
 NOTE        : this console is only a launcher. All gameplay happens in the GUI
               window. You may close this black window after the game starts.
================================================================================
"""


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    make_console_safe()
    # ---- 便携模式开关：--portable 存档放程序同目录；--no-portable 强制用默认目录 ----
    force_portable = None
    if "--portable" in argv:
        force_portable = True
    elif "--no-portable" in argv:
        force_portable = False
    base_dir, notes = resolve_base_dir(force_portable=force_portable)
    # 让模组发现机制知道数据目录（mods 子目录会被自动扫描）
    globals()["__LIFESIM_BASE_DIR__"] = base_dir
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass

    if "--selftest" in argv:
        print(BANNER)
        print("数据目录：%s\n" % base_dir)
        return run_selftest(base_dir)

    if "--base-dir" in argv:
        idx = argv.index("--base-dir")
        if idx + 1 < len(argv):
            base_dir = argv[idx + 1]
            globals()["__LIFESIM_BASE_DIR__"] = base_dir
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                pass

    # ---- 自动加载模组（mods 目录 / LIFESIM_MODS 环境变量）----
    mod_notes = []
    try:
        mod_count, mod_notes = discover_mods()
    except Exception as exc:
        mod_count = 0
        mod_notes = ["模组加载失败：%s" % exc]

    # ---- 若指定 --make-mod，则生成模组模板后退出 ----
    if "--make-mod" in argv:
        idx = argv.index("--make-mod")
        mod_id = argv[idx + 1] if idx + 1 < len(argv) and not argv[idx + 1].startswith("-") else "my_novel"
        target = os.path.join(base_dir, "mods", "%s.py" % mod_id)
        ok, msg = write_mod_template(target, mod_id=mod_id,
                                     mod_name="我的名著模组（%s）" % mod_id)
        print(msg)
        return 0 if ok else 1

    # 控制台只用 ASCII 输出：中文 Windows 控制台默认是 GBK 代码页，
    # 直接打印中文会变成乱码；而真正的游戏内容都在图形窗口里。
    portable_now = (os.path.abspath(base_dir) == os.path.abspath(portable_dir()))
    print(BANNER)
    print("  Data dir   : %s" % base_dir)
    print("  Mode       : %s" % ("PORTABLE (saves stay in this folder)"
                                 if portable_now else "DEFAULT"))
    print("  Save file  : %s" % safe_join(base_dir, SAVE_FILE_NAME))
    print("  Life log   : %s" % safe_join(base_dir, LOG_FILE_NAME))
    for note in notes:
        # 说明信息里可能含中文路径，转成 ascii 安全形式避免乱码
        try:
            print("  Note       : %s" % note.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    print("")
    if mod_count:
        print("  Mods loaded: %d" % mod_count)
    for note in mod_notes:
        try:
            print("  Mod note   : %s" % note.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass

    if tk is None:
        print("\n[错误] 当前 Python 环境缺少 tkinter，无法启动弹窗界面。")
        print("       错误详情：%s" % _TK_IMPORT_ERROR)
        print("       解决办法：安装带 tkinter 的 Python（官方安装包默认包含），")
        print("       或在 VS Code 中选择包含 tkinter 的解释器。")
        try:
            input("按回车键退出……")
        except Exception:
            pass
        return 2

    try:
        app = GameApp(base_dir, notes)
    except Exception as exc:
        print("\n[错误] 界面初始化失败：%s" % exc)
        traceback.print_exc()
        try:
            input("按回车键退出……")
        except Exception:
            pass
        return 3
    app.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已退出游戏。")
    except Exception as _fatal:
        print("\n[致命错误] %s" % _fatal)
        traceback.print_exc()
        try:
            input("按回车键退出……")
        except Exception:
            pass

