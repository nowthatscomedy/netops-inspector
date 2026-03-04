# NetOps Inspector (日本語)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector は、マルチベンダーのネットワーク機器の点検と設定バックアップを行う CLI ツールです。
Excel/CSV/JSON の機器インベントリを読み込み、SSH/Telnet で接続し、点検コマンドを実行して出力を解析し、結果ファイル（Excel/JSON/CSV）を作成します。

## 主な機能

- マルチベンダー構成（`vendors/` モジュール）
- 点検 / バックアップ / 点検+バックアップ 実行モード
- 事前チェック（preflight）モード（インベントリ/資格情報参照/TCP到達性チェック）
- TXT または Excel のカスタムコマンド一括実行
- インベントリ入力検証（必須項目、重複 IP、vendor/OS 互換性）
- ネットワーク I/O のリトライ・タイムアウト制御
- 実行中のリアルタイム端末ダッシュボード
- 機器ごとのセッションログ
- 列エイリアス/順序を設定可能な結果ファイル（Excel/JSON/CSV）生成
- `custom_rules.yaml` によるユーザー定義の解析・コマンド拡張
- 多言語 UI/メッセージ対応（`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`）

## 対応ベンダー（現在のモジュール）

- `alcatel-lucent`
- `aruba`
- `axgate`
- `cisco`
- `dayou`
- `handreamnet`
- `juniper`
- `nexg`
- `piolink`
- `ruckus`
- `ubiquoss`

対応 OS 値は、各ベンダーモジュールと `vendors/__init__.py` のコマンドマップに依存します。

## 要件

- Python 3.10+
- 対象機器へのネットワーク到達性
- `requirements.txt` の依存パッケージ

インストール:

```bash
pip install -r requirements.txt
```

## クイックスタート

実行:

```bash
python main.py
```

メインメニュー:

1. 点検/バックアップ開始
2. カスタムコマンドファイル実行
3. 設定変更
4. Netmiko `device_type` 一覧表示
5. 事前チェック実行
6. 終了

## インベントリ入力スキーマ

サポートするインベントリ形式:

- Excel: `.xlsx`, `.xls`, `.xlsm`
- CSV: `.csv`
- JSON: `.json`
  - リスト形式: `[{"ip":"...","vendor":"..."}]`
  - ラップ形式: `{"devices":[{"ip":"...","vendor":"..."}]}`

サンプルファイル:

- `examples/inventory/devices.csv`
- `examples/inventory/devices.json`
- `examples/inventory/devices_wrapped.json`

必須列:

- `ip`
- `vendor`
- `os`
- `connection_type`（`ssh` または `telnet`）
- `port`
- `password`

任意列:

- `username`
- `enable_password`

資格情報参照構文（任意）:

- `username`, `password`, `enable_password` に `env:環境変数名` を指定可能
- 例: `password: env:NETOPS_DEVICE_PASSWORD`
- 参照先の環境変数が未設定/空の場合、そのデバイスは安全に失敗扱い

例:

| ip | vendor | os | connection_type | port | username | password | enable_password |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 192.168.1.10 | cisco | ios | ssh | 22 | admin | ****** | ****** |
| 192.168.1.20 | ruckus | icx | ssh | 22 | super | ****** | |

## 設定（`settings.yaml`）

ファイルが存在しない場合、アプリディレクトリに自動生成されます。

主なキー:

- `console_log_level`: `CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG`
- `max_retries`: 接続最大リトライ回数
- `timeout`: 接続タイムアウト（秒）
- `max_workers`: 並列ワーカー数
- `inspection_excludes`: ベンダー/OS ごとの解析除外マップ
- `output_plugin`: `excel_results` | `json_results` | `csv_results`

点検出力キー:

- `column_aliases`: 点検列名の正規化
- `inspection_column_order_global`
- `inspection_column_order_by_profile`

i18n キー:

- `language`
- `fallback_language`
- `input_column_aliases`

例:

```yaml
language: en
fallback_language: en
console_log_level: WARNING
max_retries: 3
timeout: 10
max_workers: 10

input_column_aliases:
  "ip address": ip
  "vendor name": vendor
  "connection type": connection_type

column_aliases:
  "host name": Hostname
  "cpu usage": CPU Usage

output_plugin: excel_results
```

## i18n

現在受け付ける言語コード:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

同梱されている翻訳ファイル:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`

未対応の言語コードは `en` に正規化されます。
翻訳キーが見つからない場合は `fallback_language` を経由して英語へフォールバックします。

## 多言語 README

- Korean: `docs/README.ko.md`
- Japanese: `docs/README.ja.md`
- Spanish: `docs/README.es.md`
- Portuguese (Brazil): `docs/README.pt-BR.md`
- Simplified Chinese: `docs/README.zh-CN.md`

## アーキテクチャ草案

- プラグインプラットフォーム草案: `docs/plugin-platform-draft.md`

## カスタムルール（`custom_rules.yaml`）

Python コードを変更せずにコマンド/パーサーを拡張できます。

トップレベルセクション:

- `inspection_commands`
- `backup_commands`
- `parsing_rules`
- `connection_overrides`
- `handler_overrides`

テンプレートファイル:

- `custom_rules.example.yaml`

## 出力

生成パス（タイムスタンプ付き）:

- 点検結果: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- カスタムコマンド結果: `results/command_results_YYYYMMDD_HHMMSS.xlsx`
- 事前チェック結果: `results/preflight_results_YYYYMMDD_HHMMSS.xlsx`
- `output_plugin` 選択時の JSON/CSV 出力:
  - `results/*_YYYYMMDD_HHMMSS.json`
  - `results/*_YYYYMMDD_HHMMSS.csv`
- バックアップファイル: `backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- 実行ログ: `logs/netops_inspector_YYYYMMDD_HHMMSS.log`
- セッションログ: `session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

## テスト

```bash
python -m pytest
```

## ビルド（Windows）

使用方法:

```bat
build.bat
```

## セキュリティ注意事項

- ソースコードに認証情報をハードコードしないでください。
- 実行時認証情報は環境変数または安全なシークレット配布を推奨します。
- エクスポートしたログと結果ファイルは機密運用データとして扱ってください。

## ライセンス

MIT License
