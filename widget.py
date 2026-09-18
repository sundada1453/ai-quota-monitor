#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Quota Monitor Floating Widget
Linux XFCE4 / X11 Always-on-top Floating Window
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
import collector

class AIQuotaWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Quota Monitor")
        
        # 基础窗口属性
        self.root.overrideredirect(True) # 去除原生系统边框
        self.root.attributes("-topmost", True) # 始终置顶
        
        # 配色定义 (Dark Theme)
        self.bg_color = "#18181b"       # 深灰底色
        self.card_bg = "#27272a"        # 卡片内底色
        self.fg_primary = "#f4f4f5"     # 白色文字
        self.fg_muted = "#a1a1aa"       # 灰色辅助文字
        self.border_color = "#3f3f46"   # 细边框
        
        self.root.configure(bg=self.border_color)
        
        # 窗口大小与位置
        self.config = collector.load_config()
        self.initial_x = self.config.get("ui", {}).get("initial_x", 1020)
        self.initial_y = self.config.get("ui", {}).get("initial_y", 45)
        
        # 模式: 'card' (卡片详细) 或 'mini' (极简胶囊)
        self.mode = "card"
        self.width_card = 265
        self.height_card = 162
        self.width_mini = 280
        self.height_mini = 34
        
        self.root.geometry(f"{self.width_card}x{self.height_card}+{self.initial_x}+{self.initial_y}")
        
        # 拖拽变量
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # 数据缓存
        self.snapshot = None
        self.is_fetching = False
        
        # 构建 UI
        self.setup_ui()
        self.setup_events()
        
        # 启动定时刷新循环
        self.refresh_interval_ms = int(self.config.get("ui", {}).get("refresh_seconds", 10) * 1000)
        self.trigger_refresh()
        
    def setup_ui(self):
        # 核心容器
        self.main_frame = tk.Frame(self.root, bg=self.bg_color, padx=10, pady=8)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # --- 详细卡片视图 ---
        self.card_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        
        # 头部 (标题与状态)
        header_frame = tk.Frame(self.card_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 6))
        
        lbl_title = tk.Label(header_frame, text="AI 套餐用量监控", font=("DejaVu Sans", 9, "bold"), 
                             bg=self.bg_color, fg=self.fg_primary)
        lbl_title.pack(side=tk.LEFT)
        
        self.lbl_status = tk.Label(header_frame, text="● 实时", font=("DejaVu Sans", 8), 
                                   bg=self.bg_color, fg="#10b981")
        self.lbl_status.pack(side=tk.RIGHT)
        
        # 1. Grok 周用量行
        grok_frame = tk.Frame(self.card_frame, bg=self.bg_color)
        grok_frame.pack(fill=tk.X, pady=(1, 1))
        
        lbl_grok_icon = tk.Label(grok_frame, text="⚡ Grok 周", font=("DejaVu Sans", 8, "bold"), 
                                 bg=self.bg_color, fg="#60a5fa")
        lbl_grok_icon.pack(side=tk.LEFT)
        
        self.lbl_grok_val = tk.Label(grok_frame, text="-- / --", font=("DejaVu Sans", 8), 
                                     bg=self.bg_color, fg=self.fg_primary)
        self.lbl_grok_val.pack(side=tk.RIGHT)
        
        # Grok 进度条容器
        self.canvas_grok = tk.Canvas(self.card_frame, height=5, bg=self.card_bg, highlightthickness=0)
        self.canvas_grok.pack(fill=tk.X, pady=(1, 5))
        
        # 2. Antigravity 5H 用量行
        agy_5h_frame = tk.Frame(self.card_frame, bg=self.bg_color)
        agy_5h_frame.pack(fill=tk.X, pady=(1, 1))
        
        lbl_agy_5h_icon = tk.Label(agy_5h_frame, text="🤖 AGY 5h", font=("DejaVu Sans", 8, "bold"), 
                                   bg=self.bg_color, fg="#34d399")
        lbl_agy_5h_icon.pack(side=tk.LEFT)
        
        self.lbl_agy_5h_val = tk.Label(agy_5h_frame, text="-- / --", font=("DejaVu Sans", 8), 
                                       bg=self.bg_color, fg=self.fg_primary)
        self.lbl_agy_5h_val.pack(side=tk.RIGHT)
        
        # AGY 5H 进度条容器
        self.canvas_agy_5h = tk.Canvas(self.card_frame, height=5, bg=self.card_bg, highlightthickness=0)
        self.canvas_agy_5h.pack(fill=tk.X, pady=(1, 5))

        # 3. Antigravity 周用量行
        agy_w_frame = tk.Frame(self.card_frame, bg=self.bg_color)
        agy_w_frame.pack(fill=tk.X, pady=(1, 1))
        
        lbl_agy_w_icon = tk.Label(agy_w_frame, text="🤖 AGY 周", font=("DejaVu Sans", 8, "bold"), 
                                  bg=self.bg_color, fg="#a78bfa")
        lbl_agy_w_icon.pack(side=tk.LEFT)
        
        self.lbl_agy_w_val = tk.Label(agy_w_frame, text="-- / --", font=("DejaVu Sans", 8), 
                                      bg=self.bg_color, fg=self.fg_primary)
        self.lbl_agy_w_val.pack(side=tk.RIGHT)
        
        # AGY 周 进度条容器
        self.canvas_agy_w = tk.Canvas(self.card_frame, height=5, bg=self.card_bg, highlightthickness=0)
        self.canvas_agy_w.pack(fill=tk.X, pady=(1, 2))
        
        # 底部提示小字
        self.lbl_footer = tk.Label(self.card_frame, text="双击折叠 | 右键菜单", font=("DejaVu Sans", 7), 
                                   bg=self.bg_color, fg=self.fg_muted)
        self.lbl_footer.pack(fill=tk.X, pady=(3, 0))

        # --- 极简胶囊视图 (默认隐藏) ---
        self.mini_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.lbl_mini = tk.Label(self.mini_frame, text="⚡ Grok: -- | 🤖 AGY: --", 
                                 font=("DejaVu Sans", 8, "bold"), bg=self.bg_color, fg=self.fg_primary)
        self.lbl_mini.pack(expand=True, fill=tk.BOTH)
        
        # 默认展示卡片模式
        self.card_frame.pack(fill=tk.BOTH, expand=True)

    def setup_events(self):
        # 鼠标拖动支持 (绑定所有控件，拖拽任意位置均可平滑移动)
        for w in [self.root, self.main_frame, self.card_frame, self.mini_frame]:
            self.bind_drag(w)
            
        # 双击切换模式
        self.main_frame.bind("<Double-Button-1>", self.toggle_mode)
        self.card_frame.bind("<Double-Button-1>", self.toggle_mode)
        self.mini_frame.bind("<Double-Button-1>", self.toggle_mode)
        
        # 右键上下文菜单
        self.menu = tk.Menu(self.root, tearoff=0, bg=self.card_bg, fg=self.fg_primary, 
                            activebackground="#3b82f6", activeforeground="#ffffff")
        self.menu.add_command(label="🔄 立即刷新", command=self.trigger_refresh)
        self.menu.add_command(label="🔲 切换精简/卡片", command=self.toggle_mode)
        self.menu.add_separator()
        self.menu.add_command(label="❌ 退出监控", command=self.root.destroy)
        
        self.root.bind("<Button-3>", self.show_context_menu)

    def bind_drag(self, widget):
        widget.bind("<Button-1>", self.on_drag_start)
        widget.bind("<B1-Motion>", self.on_drag_motion)
        for child in widget.winfo_children():
            self.bind_drag(child)

    def on_drag_start(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag_motion(self, event):
        deltax = event.x - self.drag_start_x
        deltay = event.y - self.drag_start_y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def toggle_mode(self, event=None):
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        if self.mode == "card":
            self.mode = "mini"
            self.card_frame.pack_forget()
            self.mini_frame.pack(fill=tk.BOTH, expand=True)
            self.root.geometry(f"{self.width_mini}x{self.height_mini}+{cur_x}+{cur_y}")
        else:
            self.mode = "card"
            self.mini_frame.pack_forget()
            self.card_frame.pack(fill=tk.BOTH, expand=True)
            self.root.geometry(f"{self.width_card}x{self.height_card}+{cur_x}+{cur_y}")
        self.update_display()

    def show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def trigger_refresh(self):
        if self.is_fetching:
            return
        self.is_fetching = True
        self.lbl_status.config(text="● 刷新中", fg="#f59e0b")
        threading.Thread(target=self._async_fetch, daemon=True).start()

    def _async_fetch(self):
        try:
            data = collector.get_full_snapshot()
            self.snapshot = data
        except Exception as e:
            print("Fetch error:", e)
        finally:
            self.is_fetching = False
            self.root.after(0, self.update_display)
            # 调度下次自动刷新
            self.root.after(self.refresh_interval_ms, self.trigger_refresh)

    def update_display(self):
        if not self.snapshot:
            return

        grok = self.snapshot.get("grok", {})
        agy = self.snapshot.get("antigravity", {})
        
        # 1. Grok 数据展示 (优先展示与 Orca 完全一致的官方真实周配额)
        g_has_real = grok.get("has_real_quota", False)
        g_used = grok.get("used_pct", grok.get("percentage", 0.0))
        g_cd = grok.get("reset_time_str", "--:--")
        g_cost = grok.get("total_cost_usd", 0.0)
        
        if g_has_real:
            self.lbl_grok_val.config(text=f"已用 {g_used:.0f}% | ⏳{g_cd}")
        else:
            g_cnt = grok.get("requests_count", 0)
            g_limit = grok.get("quota_limit", 150)
            self.lbl_grok_val.config(text=f"{g_cnt}/{g_limit} ({g_used:.0f}%) | ${g_cost:.2f}")
        
        # 2. AGY 5h 数据展示
        a_5h = agy.get("five_hour", {})
        a_5h_rem = a_5h.get("remaining_pct", 100.0)
        a_5h_used = a_5h.get("used_pct", max(0.0, 100.0 - a_5h_rem))
        a_5h_cd = a_5h.get("reset_time_str", "--:--")
        
        self.lbl_agy_5h_val.config(text=f"余 {a_5h_rem:.0f}% | ⏳{a_5h_cd}")
        
        # 3. AGY 周额度数据展示
        a_w = agy.get("weekly", {})
        a_w_rem = a_w.get("remaining_pct", 100.0)
        a_w_used = a_w.get("used_pct", max(0.0, 100.0 - a_w_rem))
        a_w_cd = a_w.get("reset_time_str", "--:--")
        
        self.lbl_agy_w_val.config(text=f"余 {a_w_rem:.0f}% | ⏳{a_w_cd}")
        
        # 4. 绘制进度条 (展示已用比例)
        self.draw_progressbar(self.canvas_grok, g_used, "#3b82f6")
        self.draw_progressbar(self.canvas_agy_5h, a_5h_used, "#10b981")
        self.draw_progressbar(self.canvas_agy_w, a_w_used, "#8b5cf6")
        
        # 5. 极简胶囊文字更新
        if g_has_real:
            self.lbl_mini.config(text=f"⚡Grok: 已用{g_used:.0f}% | 🤖5h: 余{a_5h_rem:.0f}% | 周: 余{a_w_rem:.0f}%")
        else:
            self.lbl_mini.config(text=f"⚡Grok: {g_used:.0f}% | 🤖5h: 余{a_5h_rem:.0f}% | 周: 余{a_w_rem:.0f}%")
        
        self.lbl_status.config(text="● 实时", fg="#10b981")

    def draw_progressbar(self, canvas, percentage, base_color):
        canvas.delete("all")
        w = canvas.winfo_width()
        if w <= 1:
            w = 238
        h = 5
        # 背景
        canvas.create_rectangle(0, 0, w, h, fill=self.card_bg, width=0)
        # 前景颜色动态调整
        fill_col = base_color
        if percentage >= 90:
            fill_col = "#ef4444" # 红色
        elif percentage >= 75:
            fill_col = "#f59e0b" # 橙色
            
        progress_w = int(w * (min(100.0, max(0.0, percentage)) / 100.0))
        if progress_w > 0:
            canvas.create_rectangle(0, 0, progress_w, h, fill=fill_col, width=0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # 指定当前显示端口 (如果在容器内 headless，则挂载 DISPLAY)
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":1"
    app = AIQuotaWidget()
    app.run()
