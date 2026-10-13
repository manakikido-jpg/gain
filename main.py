"""Windows microphone boost with selectable virtual cable output."""
from collections import deque
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import sounddevice as sd

from audio import amplify


class MicrophoneBoost:
    def __init__(self, root):
        self.root = root
        root.title("マイクブースト — Discord")
        root.geometry("600x440")
        self.streams = []
        self.lock = threading.Lock()
        self.chunks = deque()
        self.offset = 0
        self.level = 0.0
        self.gain_db = 12.0
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
        self.gain_label = ttk.Label(panel, text="増幅：+12 dB")
        self.gain_label.pack(anchor="w")
        ttk.Scale(panel, from_=0, to=36, value=12, command=self.set_gain).pack(fill="x")
        ttk.Label(panel, text="出力レベル（リミッター適用後）").pack(anchor="w", pady=(12, 4))
        self.meter = ttk.Progressbar(panel, maximum=100)
        self.meter.pack(fill="x")
        self.button = ttk.Button(panel, text="開始", command=self.toggle)
        self.button.pack(pady=12)
        self.status = ttk.Label(panel, text="停止中")
        self.status.pack()
        ttk.Label(panel, text="Discordの入力は CABLE Output に設定してください。\nスピーカーへの出力はハウリングの原因になるため、ヘッドホンを使ってください。",
                  wraplength=550).pack(pady=10)
        if self.inputs:
            self.source.current(0)
        for label in self.outputs:
            if "cable input" in label.lower():
                self.destination.set(label)
                break
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_timer = root.after(100, self.refresh)

    def set_gain(self, value):
        self.gain_db = round(float(value), 1)
        self.gain_label.config(text=f"増幅：+{self.gain_db:g} dB")

    def capture(self, data, frames, timing, status):
        boosted = amplify(data[:, :1], self.gain_db)
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
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    MicrophoneBoost(root)
    root.mainloop()
