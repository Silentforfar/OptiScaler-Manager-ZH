"""OptiScaler 安装管理器 —— 图形界面。"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import gamesets
import installer
import scanner
import store

UI_FONT = "Microsoft YaHei UI"
BG = "#f1f5f9"
CARD = "#ffffff"
FG = "#0f172a"
MUTED = "#64748b"
ACCENT = "#2563eb"
OK_COLOR = "#15803d"
WARN_COLOR = "#b45309"
ERR_COLOR = "#b91c1c"


def resolve_payload():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(base, "payload"),
                 os.path.join(os.path.dirname(base), "payload")):
        if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "OptiScaler.dll")):
            return cand
    return None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OptiScaler 安装管理器")
        self.geometry("1140x800")
        self.minsize(1000, 700)
        self.configure(bg=BG)
        self.payload = resolve_payload()
        self.q = queue.Queue()
        self.busy = False
        self.scan_results = []
        self.exe_choices = []
        self._init_style()
        self._build()
        self.after(80, self._pump)
        self.refresh_installed()
        if not self.payload:
            self.log("未找到 payload 目录，安装功能不可用。请把程序放在完整的分发包内运行。", "err")

    # ---------- 样式 ----------
    def _init_style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", font=(UI_FONT, 10), background=BG, foreground=FG)
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Card.TLabel", background=CARD, foreground=FG)
        s.configure("Title.TLabel", background=BG, foreground=FG,
                    font=(UI_FONT, 16, "bold"))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=(UI_FONT, 9))
        s.configure("Hint.TLabel", background=CARD, foreground=MUTED, font=(UI_FONT, 9))
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", font=(UI_FONT, 10), padding=(18, 9),
                    background=BG, foreground=MUTED)
        s.map("TNotebook.Tab", background=[("selected", CARD)],
              foreground=[("selected", ACCENT)])
        s.configure("TButton", font=(UI_FONT, 10), padding=(12, 6))
        s.configure("Accent.TButton", font=(UI_FONT, 11, "bold"), padding=(14, 9),
                    background=ACCENT, foreground="#ffffff", bordercolor=ACCENT,
                    lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=ACCENT)
        s.map("Accent.TButton",
              background=[("disabled", "#cbd5e1"), ("pressed", "#1d4ed8"),
                          ("active", "#3b82f6"), ("!disabled", ACCENT)],
              foreground=[("disabled", "#f1f5f9"), ("!disabled", "#ffffff")],
              lightcolor=[("disabled", "#cbd5e1"), ("!disabled", ACCENT)],
              darkcolor=[("disabled", "#cbd5e1"), ("!disabled", ACCENT)],
              bordercolor=[("disabled", "#cbd5e1"), ("!disabled", ACCENT)],
              focuscolor=[("!disabled", ACCENT)])
        s.configure("Treeview", font=(UI_FONT, 9), rowheight=30,
                    background=CARD, fieldbackground=CARD, foreground=FG, borderwidth=0)
        s.configure("Treeview.Heading", font=(UI_FONT, 9, "bold"),
                    background="#e2e8f0", foreground=FG, padding=(6, 6))
        s.map("Treeview", background=[("selected", "#dbeafe")],
              foreground=[("selected", FG)])
        s.configure("TCombobox", padding=(6, 4))
        s.configure("TProgressbar", background=ACCENT, troughcolor="#e2e8f0")

    # ---------- 布局 ----------
    def _build(self):
        head = ttk.Frame(self, padding=(20, 16, 20, 8))
        head.pack(fill="x")
        ttk.Label(head, text="OptiScaler 安装管理器", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  中文版 %s  ·  DLSS 神经渲染 + 40 系 4X 多帧生成" % installer.VERSION,
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=20)
        self.page_installed = ttk.Frame(self.nb, padding=12)
        self.page_install = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.page_installed, text="已安装")
        self.nb.add(self.page_install, text="安装新游戏")
        self._build_installed()
        self._build_install()

        bottom = ttk.Frame(self, padding=(20, 8, 20, 14))
        bottom.pack(fill="both")
        bar = ttk.Frame(bottom)
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="就绪", style="Sub.TLabel")
        self.status.pack(side="left")
        self.prog = ttk.Progressbar(bar, mode="determinate", length=260)
        self.prog.pack(side="right")
        self.logbox = ScrolledText(bottom, height=5, font=("Consolas", 9),
                                   bg="#0f172a", fg="#cbd5e1", insertbackground="#cbd5e1",
                                   relief="flat", borderwidth=0, padx=10, pady=8)
        self.logbox.pack(fill="both", expand=True, pady=(8, 0))
        self.logbox.configure(state="disabled")

    def _build_installed(self):
        f = self.page_installed
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="刷新", command=self.refresh_installed).pack(side="left")
        ttk.Button(bar, text="卸载所选", command=self.do_uninstall).pack(side="left", padx=6)
        ttk.Button(bar, text="打开游戏目录", command=self.open_selected_dir).pack(side="left", padx=6)
        ttk.Button(bar, text="校验完整性", command=self.do_verify).pack(side="left", padx=6)
        ttk.Button(bar, text="游戏设置", command=self.open_game_settings).pack(side="left", padx=6)

        wrap = ttk.Frame(f, style="Card.TFrame")
        wrap.pack(fill="both", expand=True)
        cols = ("name", "dir", "proxy", "version", "time", "state")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        heads = {"name": ("游戏", 190), "dir": ("安装目录", 380), "proxy": ("代理文件", 110),
                 "version": ("版本", 90), "time": ("安装时间", 150), "state": ("状态", 100)}
        for c, (t, w) in heads.items():
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c in ("name", "dir") else "center")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("missing", foreground=ERR_COLOR)
        self.tree.tag_configure("ok", foreground=OK_COLOR)

        hint = ttk.Frame(f, style="Card.TFrame", padding=12)
        hint.pack(fill="x", pady=(10, 0))
        ttk.Label(hint, style="Hint.TLabel", wraplength=1040, justify="left",
                  text="卸载只删除本工具装入的文件，并把安装时备份过的原文件原样放回；"
                       "游戏本身的文件不会被删改。若游戏目录被移动或删除，可在此移除失效记录。").pack(anchor="w")

    def _build_install(self):
        f = self.page_install
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 10))
        self.btn_scan = ttk.Button(bar, text="扫描游戏平台", command=self.do_scan)
        self.btn_scan.pack(side="left")
        ttk.Button(bar, text="手动选择游戏目录", command=self.do_pick_dir).pack(side="left", padx=6)
        self.scan_info = ttk.Label(bar, text="", style="Sub.TLabel")
        self.scan_info.pack(side="left", padx=12)

        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True)
        cols = ("name", "src", "dir")
        self.tree_scan = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, (t, w) in {"name": ("游戏", 210), "src": ("来源", 70), "dir": ("路径", 300)}.items():
            self.tree_scan.heading(c, text=t)
            self.tree_scan.column(c, width=w, anchor="w" if c != "src" else "center")
        sb2 = ttk.Scrollbar(left, orient="vertical", command=self.tree_scan.yview)
        self.tree_scan.configure(yscrollcommand=sb2.set)
        self.tree_scan.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.tree_scan.bind("<<TreeviewSelect>>", self.on_pick_game)

        right = ttk.Frame(body, style="Card.TFrame", padding=16, width=350)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        # 底部按钮先占位，避免内容变高时被挤扁
        self.btn_install = ttk.Button(right, text="安装到该目录", style="Accent.TButton",
                                      command=self.do_install)
        self.btn_install.pack(side="bottom", fill="x")
        ttk.Separator(right).pack(side="bottom", fill="x", pady=(12, 10))

        ttk.Label(right, text="安装设置", style="Card.TLabel",
                  font=(UI_FONT, 11, "bold")).pack(anchor="w")
        ttk.Separator(right).pack(fill="x", pady=(8, 4))

        def field(label):
            ttk.Label(right, text=label, style="Hint.TLabel").pack(anchor="w", pady=(7, 1))

        field("游戏名称")
        self.var_name = tk.StringVar()
        ttk.Entry(right, textvariable=self.var_name).pack(fill="x")

        field("安装目录")
        self.var_dir = tk.StringVar()
        row = ttk.Frame(right, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.var_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="打开", width=5,
                   command=lambda: self._open(self.var_dir.get())).pack(side="left", padx=(4, 0))

        field("游戏主程序（注入目标）")
        self.var_exe = tk.StringVar()
        self.cb_exe = ttk.Combobox(right, textvariable=self.var_exe, state="readonly")
        self.cb_exe.pack(fill="x")
        self.cb_exe.bind("<<ComboboxSelected>>", self.on_exe_change)
        ttk.Label(right, style="Hint.TLabel", wraplength=320, justify="left",
                  text="要选真正跑游戏的那个 exe。启动器 / HQ 类游戏请选具体模式的 exe。"
                  ).pack(anchor="w", pady=(3, 0))

        field("代理文件名")
        self.var_proxy = tk.StringVar(value=installer.PROXIES[0][1])
        ttk.Combobox(right, textvariable=self.var_proxy,
                     values=[p[1] for p in installer.PROXIES],
                     state="readonly").pack(fill="x")

        ttk.Label(right, style="Hint.TLabel", wraplength=320, justify="left",
                  text="装入：主程序（改名为上面的代理文件）、AMD/NVIDIA/XeSS 运行库、"
                       "40 系 MFG 解锁插件、中文 ini 与说明。").pack(anchor="w", pady=(12, 0))

    # ---------- 工具 ----------
    def log(self, msg, kind="info"):
        color = {"err": "#fca5a5", "ok": "#86efac", "warn": "#fcd34d"}.get(kind, "#cbd5e1")
        self.logbox.configure(state="normal")
        self.logbox.insert("end", msg + "\n", kind)
        self.logbox.tag_config(kind, foreground=color)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def set_status(self, text):
        self.status.configure(text=text)

    def _open(self, path):
        if path and os.path.isdir(path):
            try:
                os.startfile(path)
            except OSError as e:
                messagebox.showerror("打不开", str(e))
        else:
            messagebox.showwarning("提示", "目录不存在")

    def _pump(self):
        try:
            while True:
                fn = self.q.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.after(80, self._pump)

    def _run(self, fn, *args):
        if self.busy:
            return
        self.busy = True
        self.prog.configure(value=0, maximum=100)
        self.set_status("处理中…")

        def worker():
            try:
                fn(*args)
            except Exception as e:
                self.q.put(lambda: self.log("出错：%s" % e, "err"))
                self.q.put(lambda: messagebox.showerror("出错了", str(e)))
            finally:
                self.q.put(self._done)

        threading.Thread(target=worker, daemon=True).start()

    def _done(self):
        self.busy = False
        self.set_status("就绪")
        self.prog.configure(value=0)
        try:
            self.btn_install.configure(text="安装到该目录", state="normal")
        except tk.TclError:
            pass

    # ---------- 已安装 ----------
    def refresh_installed(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        data = store.load_store()
        missing = []
        for it in data["items"]:
            gdir = it.get("game_dir", "")
            m = store.read_manifest(gdir) if os.path.isdir(gdir) else None
            if not os.path.isdir(gdir):
                state, tag = "目录已丢失", "missing"
                missing.append(it)
            elif not m:
                state, tag = "记录异常", "missing"
            else:
                key = os.path.join(gdir, it.get("proxy", "dxgi.dll"))
                state = "已安装" if os.path.exists(key) else "文件缺失"
                tag = "ok" if os.path.exists(key) else "missing"
            self.tree.insert("", "end", values=(
                it.get("game_name", "?"), gdir, it.get("proxy", ""),
                it.get("version", ""), it.get("installed_at", ""), state), tags=(tag,))
        self.set_status("共 %d 项安装记录" % len(data["items"]))

    def _selected_item(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "先在列表里选一个")
            return None
        vals = self.tree.item(sel[0], "values")
        return {"game_name": vals[0], "game_dir": vals[1]}

    def open_selected_dir(self):
        it = self._selected_item()
        if it:
            self._open(it["game_dir"])

    def do_verify(self):
        it = self._selected_item()
        if not it:
            return

        def job():
            self.q.put(lambda: self.set_status("正在校验…"))
            ok, issues = installer.verify(it["game_dir"])
            if ok:
                self.q.put(lambda: self.log("校验通过：%s" % it["game_name"], "ok"))
                self.q.put(lambda: messagebox.showinfo("校验", "文件完整，没有发现问题。"))
            else:
                for s in issues[:12]:
                    self.q.put(lambda s=s: self.log("  " + s, "warn"))
                self.q.put(lambda: messagebox.showwarning(
                    "校验", "发现 %d 处异常，详见日志。\n常见原因：手动改过 ini，或游戏更新覆盖过文件。"
                            % len(issues)))
        self._run(job)

    def do_uninstall(self):
        it = self._selected_item()
        if not it:
            return
        gdir = it["game_dir"]
        if not os.path.isdir(gdir):
            if messagebox.askyesno("移除记录", "游戏目录已不存在，只移除这条安装记录？"):
                store.remove_item(gdir)
                self.log("已移除失效记录：%s" % it["game_name"], "warn")
                self.refresh_installed()
            return
        if not messagebox.askyesno(
                "确认卸载",
                "将从以下目录卸载 OptiScaler：\n\n%s\n\n"
                "只删除本工具装入的文件，并还原安装时备份的原文件。\n游戏本体不受影响。" % gdir):
            return

        def job():
            res = installer.uninstall(
                gdir,
                progress=lambda d, t, n: self.q.put(
                    lambda d=d, t=t, n=n: (self.prog.configure(value=d * 100 / max(t, 1)),
                                           self.set_status("卸载 %s" % n))),
                log=lambda m: self.q.put(lambda m=m: self.log(m)))
            self.q.put(self.refresh_installed)
            self.q.put(lambda: messagebox.showinfo(
                "卸载完成", "已删除 %d 个文件，还原 %d 个备份。" % (res["removed"], res["restored"])))
        self._run(job)

    # ---------- 游戏设置 ----------
    def open_game_settings(self):
        it = self._selected_item()
        if not it:
            return
        path, items = gamesets.read_cod_panel()
        if not path or not items:
            messagebox.showinfo(
                "暂不支持",
                "目前只能读取 Call of Duty 系列的游戏设置。\n\n"
                "其它游戏的画质配置格式各不相同（多半是二进制或加密的），"
                "没法用同一套逻辑安全地改。")
            return

        win = tk.Toplevel(self)
        win.title("游戏设置 — %s" % it["game_name"])
        win.geometry("680x580")
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()

        head = ttk.Frame(win, padding=(18, 16, 18, 6))
        head.pack(fill="x")
        ttk.Label(head, text="游戏内设置", font=(UI_FONT, 13, "bold")).pack(anchor="w")
        ttk.Label(head, text=path, style="Hint.TLabel", wraplength=620).pack(anchor="w", pady=(4, 0))
        ttk.Label(head, text="改完要重启游戏才生效；保存前会自动备份原文件。",
                  style="Hint.TLabel").pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(win, padding=(18, 8))
        body.pack(fill="both", expand=True)
        pairs = []
        for r, item in enumerate(items):
            ttk.Label(body, text=item["label"]).grid(row=r, column=0, sticky="w", pady=7)
            if item["kind"] == "bool":
                cur = "true" if str(item["value"]).strip().lower() == "true" else "false"
                var = tk.StringVar(value=cur)
                w = ttk.Combobox(body, textvariable=var, values=["true", "false"],
                                 state="readonly", width=24)
            else:
                var = tk.StringVar(value=item["value"])
            if item["kind"] == "bool":
                pass
            elif item["kind"] == "choice" and item["options"]:
                w = ttk.Combobox(body, textvariable=var, values=item["options"],
                                 state="readonly", width=24)
            else:
                w = ttk.Entry(body, textvariable=var, width=26)
            w.grid(row=r, column=1, sticky="w", padx=(14, 8))
            ttk.Label(body, text="@" + item["profile"], style="Hint.TLabel"
                      ).grid(row=r, column=2, sticky="w")
            pairs.append((item, var))

        foot = ttk.Frame(win, padding=(18, 6, 18, 16))
        foot.pack(fill="x")

        def _val(item, var):
            v = var.get()
            if item["kind"] == "bool":
                return "true" if v else "false"
            return str(v)

        def do_save():
            changed = [(i, _val(i, v)) for i, v in pairs
                       if _val(i, v) != str(i["value"]).strip()]
            if not changed:
                win.destroy()
                return
            names = "\n".join("  · %s = %s" % (i["label"], v.get()) for i, v in changed)
            if not messagebox.askyesno("确认修改", "要修改这些项吗？\n\n%s" % names, parent=win):
                return
            try:
                bk = gamesets.backup(path)
                for i, v in changed:
                    gamesets.set_value(path, i["key"], i["profile"], v)
            except Exception as e:
                messagebox.showerror("保存失败", str(e), parent=win)
                return
            self.log("游戏设置已保存 %d 项（备份 %s）" % (len(changed), os.path.basename(bk)), "ok")
            messagebox.showinfo("已保存", "重启游戏后生效。", parent=win)
            win.destroy()

        ttk.Button(foot, text="取消", command=win.destroy).pack(side="right")
        ttk.Button(foot, text="保存修改", style="Accent.TButton",
                   command=do_save).pack(side="right", padx=(0, 8))

    # ---------- 安装 ----------
    def do_scan(self):
        if not self.payload:
            messagebox.showerror("缺少文件", "找不到 payload 目录，无法安装。")
            return

        def job():
            self.q.put(lambda: self.log("开始扫描游戏平台…"))
            items = scanner.scan_all(log=lambda m: self.q.put(lambda m=m: self.log("  " + m)))
            self.scan_results = items
            self.q.put(lambda: self._fill_scan(items))
        self._run(job)

    def _fill_scan(self, items):
        for i in self.tree_scan.get_children():
            self.tree_scan.delete(i)
        for it in items:
            self.tree_scan.insert("", "end", values=(it["name"], it["source"],
                                                     it.get("root") or it["dir"]))
        self.scan_info.configure(text="找到 %d 个" % len(items) if items else "没找到，试着手动选择目录")
        self.log("扫描结束，共 %d 个游戏目录" % len(items), "ok")

    def _fill_exe_choices(self, root):
        """列出该目录下所有候选 exe，让用户确认注入目标。"""
        try:
            cands = scanner.list_executables(root)
        except OSError as e:
            self.log("读取目录失败：%s" % e, "err")
            cands = []
        self.exe_choices = cands
        labels = []
        for c in cands:
            sub = os.path.dirname(c["rel"])
            where = sub if sub else "根目录"
            mb = c["size"] // (1024 * 1024)
            tag = ("  · " + c["tag"]) if c["tag"] else ""
            labels.append("%s  %s · %dMB%s" % (c["name"], where, mb, tag))
        self.cb_exe["values"] = labels
        if labels:
            self.cb_exe.current(0)
            self.on_exe_change()
        else:
            self.var_exe.set("")
            self.var_dir.set(root)
            self.log("该目录下没有找到可用的 exe", "warn")

    def on_exe_change(self, _evt=None):
        i = self.cb_exe.current()
        if 0 <= i < len(self.exe_choices):
            c = self.exe_choices[i]
            self.var_dir.set(c["dir"])
            self.log("注入目标：%s（%s）" % (c["rel"], c["tag"] or "普通程序"), "ok")
            if len(self.exe_choices) > 1:
                self.log("  上面是默认推荐。如果不是你实际要玩的模式，请在右侧下拉里切换",
                         "warn")

    def on_pick_game(self, _evt=None):
        sel = self.tree_scan.selection()
        if not sel:
            return
        name, src, path = self.tree_scan.item(sel[0], "values")
        self.var_name.set(name)
        self._fill_exe_choices(path)

    def do_pick_dir(self):
        p = filedialog.askdirectory(title="选择游戏目录（里面要有游戏 .exe）")
        if not p:
            return
        p = os.path.normpath(p)
        name = os.path.basename(p.rstrip("\\/")) or "未命名游戏"

        item = {"name": name, "dir": p, "root": p, "exe": "", "source": "手动"}
        self.scan_results = [x for x in self.scan_results
                             if os.path.normcase(x.get("root") or x["dir"]) != os.path.normcase(p)]
        self.scan_results.insert(0, item)

        iid = self.tree_scan.insert("", 0, values=(name, "手动", p))
        self.tree_scan.selection_set(iid)
        self.tree_scan.focus(iid)
        self.tree_scan.see(iid)
        self.var_name.set(name)
        self._fill_exe_choices(p)
        self.scan_info.configure(text="已手动加入 1 个目录")
        n = len(self.exe_choices)
        self.log("在该目录下找到 %d 个候选程序，请在右侧确认注入目标" % n,
                 "ok" if n else "warn")

    def do_install(self):
        if not self.payload:
            messagebox.showerror("缺少文件", "找不到 payload 目录。")
            return
        i = self.cb_exe.current()
        if not (0 <= i < len(self.exe_choices)):
            messagebox.showwarning("提示", "先在「游戏主程序」里选一个注入目标")
            return
        choice = self.exe_choices[i]
        gdir = choice["dir"]
        exe = choice["name"]
        name = self.var_name.get().strip() or (os.path.basename(gdir) or "未命名游戏")
        proxy = self.var_proxy.get().split()[0]
        ok, msg = installer.check_target(gdir)
        if not ok:
            messagebox.showerror("无法安装", msg)
            return

        conflicts = installer.detect_conflicts(gdir, proxy)
        if conflicts:
            lines = []
            for c in conflicts:
                size = ("%.1f MB" % (c["size"] / 1048576)) if c["size"] else "—"
                what = c["product"] or c["company"] or "未知来源"
                tag = "会被本次安装覆盖（先备份）" if c["replaces_target"] else "同时存在，可能互相冲突"
                lines.append("  · %s   %s   %s\n      %s" % (c["name"], size, what, tag))
            if not messagebox.askyesno(
                    "检测到已有注入器",
                    "这个目录里已经装了别的东西：\n\n%s\n\n"
                    "同一个目录里同时存在两个注入器，游戏很可能直接打不开。\n"
                    "建议先把旧的改名成 .disabled 再装。\n\n"
                    "仍然继续安装？" % "\n".join(lines)):
                return
            self.log("检测到 %d 个已有注入器，用户选择继续" % len(conflicts), "warn")
        elif not messagebox.askyesno("确认安装",
                                     "游戏：%s\n注入目标：%s\n安装目录：%s\n代理文件：%s\n\n开始安装？"
                                     % (name, choice["rel"], gdir, proxy)):
            return

        self.btn_install.configure(text="正在安装…", state="disabled")

        def job():
            self.q.put(lambda: self.log("开始安装到 %s" % gdir))
            installer.install(
                self.payload, gdir, proxy, name, exe,
                progress=lambda d, t, n: self.q.put(
                    lambda d=d, t=t, n=n: (self.prog.configure(value=d * 100 / max(t, 1)),
                                           self.set_status("复制 %s" % n))),
                log=lambda m: self.q.put(lambda m=m: self.log("  " + m)))
            self.q.put(self.refresh_installed)
            self.q.put(lambda: messagebox.showinfo(
                "安装完成", "已装好。\n\n下一步：\n"
                          "1. 进游戏，在画面设置里开 DLSS\n"
                          "2. 按 Insert 打开叠加层（中文）\n"
                          "3. 需要 40 系多帧生成的话，进游戏后按 Backspace 打开 MFG 解锁器菜单"))
        self._run(job)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
