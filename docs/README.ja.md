# NetOps Inspector (日本語)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector は、マルチベンダーのネットワーク機器を点検・バックアップするための CLI ツールです。
Excel の機器一覧を読み込み、SSH/Telnet で接続し、結果を Excel に出力します。

## 主な機能

- マルチベンダー構成 (`vendors/`)
- 点検 / バックアップ / 点検+バックアップ
- TXT/Excel のカスタムコマンド一括実行
- 入力 Excel の検証（必須列、重複 IP、vendor/OS 整合）
- 再試行、タイムアウト、並列数の設定
- リアルタイム TUI ダッシュボード
- 機器ごとのセッションログ
- `custom_rules.yaml` による拡張
- 多言語 UI (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## クイックスタート

```bash
pip install -r requirements.txt
python main.py
```

## i18n

サポート言語コード:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

ロケールファイル:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`
