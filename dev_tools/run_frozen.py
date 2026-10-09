# -*- coding: utf-8 -*-
"""
PyInstaller 打包入口（把游戏封装成免安装 exe 用的引导脚本）。

为什么需要这个文件：
    游戏本体是单文件 LifeSimulator.py（用 importlib 动态加载，便于"单文件运行"）。
    PyInstaller 的静态分析看不到动态加载，所以这里用**显式 import** 把主模块
    纳入依赖分析，再把同一个模块对象注册进 sys.modules，保证：

      * 打包时能收集到 tkinter / 全部代码
      * 运行时 everything 都用同一个模块对象
        （否则会出现"两份模块实例"，模组系统与全局注册表会分裂）
      * 模组文件里写 `from LifeSimulator import LifeMod` 依然可用

用法（一般不用手动跑，用 dev_tools/build_exe.py 即可）：
    pyinstaller --onefile --windowed --name LifeSimulator run_frozen.py
"""

import importlib
import importlib.util
import os
import sys

MODULE_NAME = "LifeSimulator"


def _load_main_module():
    """
    加载游戏主模块，返回模块对象。
    优先用常规 import（PyInstaller 能静态分析）；
    找不到时退化为"从脚本同目录按文件路径加载"（直接跑源码的情形）。
    """
    # 1) 常规导入（打包后走这条，PyInstaller 已经把它收进包里）
    try:
        module = importlib.import_module(MODULE_NAME)
        return module
    except Exception:
        pass

    # 2) 源码方式：按文件路径加载
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, MODULE_NAME + ".py"),
                 os.path.join(here, "..", MODULE_NAME + ".py")):
        cand = os.path.abspath(cand)
        if os.path.isfile(cand):
            spec = importlib.util.spec_from_file_location(MODULE_NAME, cand)
            module = importlib.util.module_from_spec(spec)
            sys.modules[MODULE_NAME] = module
            spec.loader.exec_module(module)
            return module
    raise SystemExit("找不到 %s.py，请把它与 run_frozen.py 放在同一目录。" % MODULE_NAME)


def main():
    module = _load_main_module()
    # 注册别名，供模组系统与 `from LifeSimulator import ...` 使用
    for alias in (MODULE_NAME, "lifesimulator"):
        sys.modules.setdefault(alias, module)
    sys.modules.setdefault("__main__", module)
    # 交给主程序处理命令行（--portable / --selftest / --make-mod ...）
    return module.main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
