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
NATURAL_DEATH_BASE_RATE = 0.004  # 起始年龄（45 岁）的年度自然死亡概率
NATURAL_DEATH_GROWTH = 1.0625   # 死亡率年增长系数（45~85 岁，由多种子实验标定）
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
ACTION_COST = {"rest": 1, "work": 1, "fun": 1, "study": 1, "social": 1, "exercise": 1}
ACTION_LABELS = {
    "rest": "休息恢复", "work": "工作赚钱", "fun": "娱乐消费",
    "study": "学习充电", "social": "社交联络", "exercise": "锻炼身体",
}
#: 同一天内重复做同一件事的收益衰减（第 2 次 85%，第 3 次 70%……最低 40%）
ACTION_REPEAT_DECAY = 0.85
ACTION_REPEAT_FLOOR = 0.40

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
# 2. 路径工具：自动检测并创建数据目录
# ==============================================================================

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


def resolve_base_dir():
    """
    解析游戏数据目录：
        1. 优先使用环境变量 LIFESIM_HOME（方便测试 / 多开）
        2. 否则使用 D:\\desktop\\LifeSimulator
        3. 若目标盘符不存在或不可写，依次退化为
           <用户主目录>\\LifeSimulator  ->  源码所在目录\\data
    返回 (目录, 说明信息列表)。
    """
    notes = []
    env_dir = os.environ.get(ENV_BASE_DIR_KEY, "").strip()
    candidates = []
    if env_dir:
        candidates.append(env_dir)
        notes.append("检测到环境变量 %s，使用目录：%s" % (ENV_BASE_DIR_KEY, env_dir))
    candidates.append(DEFAULT_BASE_DIR)

    home = os.path.expanduser("~") or "."
    candidates.append(os.path.join(home, FALLBACK_DIR_NAME))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

    for path in candidates:
        parent = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(parent) and not _try_makedirs(parent):
            notes.append("无法创建上级目录：%s（跳过）" % parent)
            continue
        if not _try_makedirs(path):
            notes.append("无法创建数据目录：%s（跳过）" % path)
            continue
        if not _dir_writable(path):
            notes.append("数据目录不可写：%s（跳过）" % path)
            continue
        if path != DEFAULT_BASE_DIR:
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
