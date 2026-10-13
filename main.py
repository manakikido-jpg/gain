"""Windows microphone boost with selectable virtual cable output."""
from collections import deque
import threading
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import sounddevice as sd

from audio import VoiceProcessor
import preferences


class MicrophoneBoost:
    def __init__(self, root):
        self.root = root
        root.title("マイクブースト — Discord")
        root.geometry("620x670")
        self.settings_ready = False
        self.saved = preferences.load_preferences()
        self.auto_timer = None
        self.streams = []
        self.lock = threading.Lock()
        self.chunks = deque()
        self.offset = 0
        self.level = 0.0
        self.gain_db = float(self.saved.get('gain_db', 12))
        self.processor = VoiceProcessor()
        self.audio_options = self.saved.get('audio', {
            'low_cut': False, 'noise_gate': False, 'compressor': False, 'gate_db': -55})
        self.audio_warning = False
        self.output_started = False
        self.failure = ""
        self.devices = sd.query_devices()
        apis = sd.query_hostapis()
        self.inputs = {f"{i}: {d['name']} ({apis[d['hostapi']]['name']})": i
                       for i, d in enumerate(self.devices) if d['max_input_channels']}
        self.outputs = {f"{i}: {d['name']} ({apis[d['hostapi']]['name']})": i
                        for i, d in enumerate(self.devices) if d['max_output_channels']}
        panel = ttk.Frame(root, padding=20)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="入力：USB-XLRマイクを選択").pack(anchor="w")
        self.source = ttk.Combobox(panel, values=list(self.inputs), state="readonly", width=75)
        self.source.pack(fill="x", pady=(4, 12))
        ttk.Label(panel, text="出力：仮想ケーブルの CABLE Input を選択").pack(anchor="w")
        self.destination = ttk.Combobox(panel, values=list(self.outputs), state="readonly", width=75)
        self.destination.pack(fill="x", pady=(4, 12))
        self.gain_label = ttk.Label(panel, text=f"増幅：+{self.gain_db:g} dB")
        self.gain_label.pack(anchor="w")
        ttk.Scale(panel, from_=0, to=36, value=self.gain_db, command=self.set_gain).pack(fill="x")
        ttk.Label(panel, text="出力レベル（リミッター適用後）").pack(anchor="w", pady=(12, 4))
        self.meter = ttk.Progressbar(panel, maximum=100)
        self.meter.pack(fill="x")
        self.button = ttk.Button(panel, text="開始", command=self.toggle)
        self.button.pack(pady=12)
        self.status = ttk.Label(panel, text="停止中")
        self.status.pack()
        self.auto_start = tk.BooleanVar(value=self.saved.get('auto_start', False))
        ttk.Checkbutton(panel, text="Windowsログイン時に起動して増幅を開始",
                        variable=self.auto_start, command=self.change_autostart).pack(pady=8)
        ttk.Label(panel, text="設定は自動保存されます。自動開始はCABLE Inputへの出力のみです。",
                  wraplength=550).pack()
        self.effect_vars = {}
        for key, label in [('low_cut', '低いゴロゴロ音を抑える（80 Hz）'),
                           ('noise_gate', '話していない間のノイズを抑える'),
                           ('compressor', '声の大小を整える（コンプレッサー）')]:
            variable = tk.BooleanVar(value=self.audio_options.get(key, False))
            self.effect_vars[key] = variable
            ttk.Checkbutton(panel, text=label, variable=variable,
                            command=self.update_effects).pack(anchor='w')
        self.gate_label = ttk.Label(panel, text=f"ノイズゲートの境界：{self.audio_options['gate_db']:g} dB")
        self.gate_label.pack(anchor='w')
        ttk.Scale(panel, from_=-70, to=-25, value=self.audio_options['gate_db'],
                  command=self.set_gate).pack(fill='x')
        ttk.Label(panel, text='境界を右に動かすほど小さい音を抑えます。声が途切れたら左へ。',
                  wraplength=550).pack(anchor='w')
        ttk.Label(panel, text="Discordの入力は CABLE Output に設定してください。\nスピーカーへの出力はハウリングの原因になるため、ヘッドホンを使ってください。",
                  wraplength=550).pack(pady=10)
        if self.inputs:
            self.source.current(0)
        for label in self.outputs:
            if "cable input" in label.lower():
                self.destination.set(label)
                break
        for widget, labels, key in ((self.source, self.inputs, 'input'),
                                     (self.destination, self.outputs, 'output')):
            if self.saved.get(key):
                widget.set(preferences.find_device(labels, self.saved[key]))
            widget.bind('<<ComboboxSelected>>', lambda event: self.persist_settings())
        self.settings_ready = True
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_timer = root.after(100, self.refresh)
        if self.auto_start.get():
            self.auto_timer = root.after(800, self.begin_automatically)

    def persist_settings(self):
        if not self.settings_ready:
            return
        try:
            preferences.save_preferences({
                'gain_db': self.gain_db,
                'input': preferences.device_identity(self.source.get()),
                'output': preferences.device_identity(self.destination.get()),
                'auto_start': self.auto_start.get(),
                'audio': self.audio_options,
            })
        except OSError as error:
            self.failure = f"設定を保存できません：{error}"

    def change_autostart(self):
        enabled = self.auto_start.get()
        if enabled and (not self.source.get() or 'cable input' not in self.destination.get().lower()):
            self.auto_start.set(False)
            messagebox.showerror('自動起動の設定', '入力マイクと出力CABLE Inputを先に選んでください。')
            return
        try:
            preferences.register_login(enabled)
        except OSError as error:
            self.auto_start.set(not enabled)
            messagebox.showerror('自動起動を設定できません', str(error))
            return
        self.persist_settings()

    def begin_automatically(self):
        self.auto_timer = None
        if self.streams:
            return
        if (not self.source.get() or not self.destination.get()
                or 'cable input' not in self.destination.get().lower()):
            self.failure = '前回のマイク・CABLE Inputが見つかりません。選択して開始してください。'
            return
        self.toggle()
        if self.streams and '--login' in sys.argv:
            self.root.iconify()

    def set_gain(self, value):
        self.gain_db = round(float(value), 1)
        self.gain_label.config(text=f"増幅：+{self.gain_db:g} dB")
        self.persist_settings()

    def update_effects(self):
        self.audio_options = dict(self.audio_options, **{
            key: variable.get() for key, variable in self.effect_vars.items()})
        self.persist_settings()

    def set_gate(self, value):
        self.audio_options = dict(self.audio_options, gate_db=round(float(value), 1))
        self.gate_label.config(text=f"ノイズゲートの境界：{self.audio_options['gate_db']:g} dB")
        self.persist_settings()

    def capture(self, data, frames, timing, status):
        boosted = self.processor.process(data[:, :1], self.gain_db, **self.audio_options)
        self.level = float(np.max(np.abs(boosted))) if frames else 0
        if status:
            self.audio_warning = True
        with self.lock:
            if len(self.chunks) >= 8:
                self.chunks.popleft()
                self.offset = 0
                self.audio_warning = True
            self.chunks.append(boosted)

    def playback(self, data, frames, timing, status):
        data.fill(0)
        if status:
            self.audio_warning = True
        with self.lock:
            written = 0
            while written < frames and self.chunks:
                chunk = self.chunks[0]
                count = min(frames - written, len(chunk) - self.offset)
                data[written:written + count] = chunk[self.offset:self.offset + count]
                written += count
                self.offset += count
                if self.offset == len(chunk):
                    self.chunks.popleft()
                    self.offset = 0
            if written:
                self.output_started = True
            if written < frames and self.output_started:
                self.audio_warning = True

    def toggle(self):
        if self.auto_timer is not None:
            self.root.after_cancel(self.auto_timer)
            self.auto_timer = None
        if self.streams:
            self.stop()
            return
        if self.source.get() not in self.inputs or self.destination.get() not in self.outputs:
            messagebox.showerror("デバイス未選択", "入力マイクと出力先を選択してください。")
            return
        destination = self.destination.get()
        if "cable input" not in destination.lower():
            if not messagebox.askyesno("出力先の確認", "仮想ケーブル以外への出力です。\nスピーカーではハウリングする可能性があります。開始しますか？"):
                return
        self.audio_warning = False
        self.output_started = False
        self.failure = ""
        self.processor = VoiceProcessor()
        try:
            rate = 48000
            source_id = self.inputs[self.source.get()]
            destination_id = self.outputs[destination]
            sd.check_input_settings(device=source_id, channels=1, dtype="float32", samplerate=rate)
            channels = min(2, self.devices[destination_id]['max_output_channels'])
            sd.check_output_settings(device=destination_id, channels=channels, dtype="float32", samplerate=rate)
            self.streams.append(sd.InputStream(
                device=source_id, channels=1, samplerate=rate,
                blocksize=480, dtype="float32", callback=self.capture))
            self.streams.append(sd.OutputStream(
                device=destination_id, channels=channels, samplerate=rate,
                blocksize=480, dtype="float32", callback=self.playback))
            for stream in self.streams:
                stream.start()
            self.source.config(state="disabled")
            self.destination.config(state="disabled")
            self.button.config(text="停止")
            self.persist_settings()
        except Exception as error:
            self.stop()
            messagebox.showerror("開始できません", f"{error}\n\nWindowsで両デバイスを48,000 Hzに設定し、他のアプリの排他使用を解除してください。")

    def stop(self):
        for stream in reversed(self.streams):
            try:
                stream.stop()
            except Exception as error:
                self.failure = f"停止時のエラー：{error}"
            finally:
                try:
                    stream.close()
                except Exception as error:
                    self.failure = f"デバイス解放時のエラー：{error}"
        self.streams.clear()
        with self.lock:
            self.chunks.clear()
            self.offset = 0
        self.level = 0
        self.source.config(state="readonly")
        self.destination.config(state="readonly")
        self.button.config(text="開始")

    def refresh(self):
        if self.streams and not all(stream.active for stream in self.streams):
            self.stop()
            self.failure = "音声デバイスが停止しました。接続を確認し、開始し直してください。"
        self.meter['value'] = self.level * 100
        self.status.config(text=self.failure or (
            ("動作中 — 音声遅延・欠落を検出" if self.audio_warning else "動作中")
            if self.streams else "停止中"))
        self.refresh_timer = self.root.after(100, self.refresh)

    def close(self):
        self.root.after_cancel(self.refresh_timer)
        if self.auto_timer is not None:
            self.root.after_cancel(self.auto_timer)
        self.persist_settings()
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    MicrophoneBoost(root)
    root.mainloop()
