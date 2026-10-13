# Windowsにブロックされる場合

## 配布方法の変更

Windows用のポータブル版をGitHub Actionsで作成します。ZIPを展開し、`MicBoost.exe` をダブルクリックする構成です。Pythonのインストールや `Setup.bat` は不要です。VB-CABLEは別途必要です。

GitHubリポジトリの **Actions → Windows tests and executable → 最新の成功した実行 → Artifacts → MicBoost-Windows** から取得します。ArtifactsのダウンロードにはGitHubへのログインが必要な場合があります。テストやビルドが失敗している場合は、その実行から使える配布物を取得できません。

ZIPは「すべて展開」してください。`MicBoost.exe` と `_internal` フォルダーを同じ場所に保ちます。exeだけを取り出すと動きません。登録後はフォルダーを移動しないでください。

**これはbatを使わない配布方法への変更です。スマートアプリコントロールによるブロックを解消できたという意味ではありません。現在の自動ビルドは未署名です。** exeや同梱DLLがブロックされる可能性があります。警告が出た場合は表示を確認し、保護機能を無効化して進めないでください。

## 配布者が必要な対策

信頼されたコード署名証明書やMicrosoftの署名サービスを使ったAuthenticode署名が必要な場合があります。スマートアプリコントロールとMicrosoft Defender SmartScreenは別の判定であり、署名してもすべての警告が消える保証はありません。

このプロジェクトにはコード署名証明書・署名サービスの認証情報がありません。証明書の購入や本人確認、秘密鍵の安全な管理などは別途必要です。秘密鍵やパスワードはGitHub・ソースコード・チャットに貼らないでください。

既にWindowsの現在ユーザーの証明書ストアに、信頼されたコード署名証明書と利用可能な秘密鍵がある場合は、公式Windows SDKのSignToolと `scripts/Sign-Windows.ps1` で署名できます。証明書の拇印を引数で指定します。スクリプトは同梱のexe・dll・pydも対象にし、既に署名が有効なファイルはその署名を維持します。

```powershell
python -m PyInstaller --noconfirm --onedir --windowed --name MicBoost main.py
.\scripts\Sign-Windows.ps1 -CertificateThumbprint "証明書の拇印"
```

これは配布者向けで、一般の利用者が行う手順ではありません。自己署名証明書を作って信頼させる方法や実行ポリシーの緩和は対策として採用していません。署名スクリプトは現環境ではWindows・証明書がなく未実行です。

署名後のファイルでWindows実機の起動、自動起動、マイク→VB-CABLE→Discordまでを再確認してください。
