

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
