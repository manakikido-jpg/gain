# マイクブースト for Discord

WindowsでUSBマイク入力を0〜36 dB増幅し、選択した音声出力へ送るアプリです。
出力メーター、リミッター、低域フィルター、ノイズゲート、コンプレッサーを備えます。
設定の保存とWindowsログイン時の自動起動・増幅開始に対応します。
ノイズゲートは無言時の小さな音を抑える機能です。常に重なるノイズの完全除去やマイクへの電源供給は行いません。
FDUCE-SL40XとNCGGY-2025-USB-XLR-2Mを想定していますが、実機での動作は未検証です。

**初めて使う方は [Windows・Discordの設定ガイド](WINDOWS_GUIDE.md) を順番に進めてください。**
Pythonから起動する場合は `Setup.bat` で初回準備、`Start.bat` で起動できます。
batがブロックされる場合とexe配布・署名については [Windowsのセキュリティ対策](WINDOWS_SECURITY.md) を参照してください。

## Windowsでの準備

1. Python 3.11以降を公式サイトからインストールします（Tkinterを含む通常のWindows版）。
2. [VB-CABLE公式サイト](https://vb-audio.com/Cable/)から仮想オーディオケーブルをインストールし、Windowsを再起動します。ドライバー導入には管理者権限が必要です。
3. このフォルダーでPowerShellを開き、次を実行します。

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Discordへの接続

1. Windowsのマイクへのアクセスと「デスクトップ アプリにマイクへのアクセスを許可する」を有効にします。
2. アプリの入力にUSB-XLR変換ケーブルの録音デバイスを選びます。表示名は環境によって異なります。
3. アプリの出力に **CABLE Input** を選択して「開始」を押します。
4. Discordの「音声・ビデオ」で入力デバイスを **CABLE Output** にします。Discordの出力は普段のヘッドホンにします。
5. 最初は+12 dBでDiscordのマイクテストを行い、聞きやすい音量まで調整します。Discordの自動ゲイン調整が増幅を打ち消す場合はオフにして比較してください。

音声の流れ：マイク → 本アプリ → CABLE Input → CABLE Output → Discord。
通話中は本アプリを起動したままにします。仮想ケーブルだけでは増幅しません。
リミッターは出力の過大振幅を抑えますが、録音時点の音割れは修復できません。
大きな増幅ではノイズも増えます。スピーカーへの出力やDiscordの入力モニターはハウリングに注意してください。

開始できない場合はWindowsのサウンド設定でマイクと仮想ケーブルを48,000 Hzに合わせ、排他使用を解除します。
デバイスを接続し直した後はアプリを再起動してください。

## exeを作る（Windows上で実行）

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name MicBoost main.py
```

`dist\MicBoost\MicBoost.exe` を起動します。同梱の `_internal` フォルダーも必要です。VB-CABLEドライバーは別途必要です。未署名のexeがWindowsにブロックされる可能性は残ります。
Linux上でWindows用exeを作る手順ではありません。

## 検証

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

処理のテストと、Windows実機での入出力・Discordのマイクテストは別です。
