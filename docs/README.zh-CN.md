# NetOps Inspector (简体中文)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector 是一款用于多厂商网络设备巡检与配置备份的 CLI 工具。
它从 Excel 设备清单读取数据，通过 SSH/Telnet 连接设备，执行巡检命令，解析输出并生成结果工作簿。

## 核心功能

- 多厂商架构（`vendors/` 模块）
- 巡检 / 备份 / 巡检+备份 执行模式
- 支持从 TXT 或 Excel 批量执行自定义命令
- Excel 输入校验（必填字段、重复 IP、vendor/OS 兼容性）
- 网络 I/O 的重试与超时控制
- 执行期间实时终端仪表盘
- 按设备生成会话日志文件
- 支持列别名/列顺序配置的结果工作簿生成
- 通过 `custom_rules.yaml` 扩展用户自定义解析与命令
- i18n UI/消息支持（`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`）

## 支持的厂商（当前模块）

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

支持的 OS 取值取决于各厂商模块以及 `vendors/__init__.py` 中的命令映射。

## 环境要求

- Python 3.10+
- 能够访问目标设备的网络连通性
- `requirements.txt` 中的依赖

安装：

```bash
pip install -r requirements.txt
```

## 快速开始

运行：

```bash
python main.py
```

主菜单：

1. 开始巡检/备份
2. 运行自定义命令文件
3. 修改设置
4. 显示 Netmiko `device_type` 列表
5. 退出

## Excel 输入结构

必填列：

- `ip`
- `vendor`
- `os`
- `connection_type`（`ssh` 或 `telnet`）
- `port`
- `password`

可选列：

- `username`
- `enable_password`

示例：

| ip | vendor | os | connection_type | port | username | password | enable_password |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 192.168.1.10 | cisco | ios | ssh | 22 | admin | ****** | ****** |
| 192.168.1.20 | ruckus | icx | ssh | 22 | super | ****** | |

## 设置（`settings.yaml`）

文件缺失时会在应用目录中自动创建。

常用键：

- `console_log_level`: `CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG`
- `max_retries`: 最大连接重试次数
- `timeout`: 连接超时（秒）
- `max_workers`: 并行 worker 数
- `inspection_excludes`: 按 vendor/OS 的解析排除映射

巡检输出相关键：

- `column_aliases`: 规范化巡检列名
- `inspection_column_order_global`
- `inspection_column_order_by_profile`

i18n 相关键：

- `language`
- `fallback_language`
- `input_column_aliases`

示例：

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
```

## i18n

当前接受的语言代码：

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

当前内置的翻译文件：

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`

不支持的语言代码会被规范化为 `en`。
如果缺少所选 locale 文件或翻译键，将回退到 `fallback_language`，再回退到英文。

## 多语言 README

- Korean: `docs/README.ko.md`
- Japanese: `docs/README.ja.md`
- Spanish: `docs/README.es.md`
- Portuguese (Brazil): `docs/README.pt-BR.md`
- Simplified Chinese: `docs/README.zh-CN.md`

## 自定义规则（`custom_rules.yaml`）

无需修改 Python 代码即可扩展命令和解析器。

顶层章节：

- `inspection_commands`
- `backup_commands`
- `parsing_rules`
- `connection_overrides`
- `handler_overrides`

模板文件：

- `custom_rules.example.yaml`

## 输出

生成路径（带时间戳）：

- 巡检结果：`results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- 自定义命令结果：`results/command_results_YYYYMMDD_HHMMSS.xlsx`
- 备份文件：`backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- 运行日志：`logs/netops_inspector_YYYYMMDD_HHMMSS.log`
- 会话日志：`session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

## 测试

```bash
python -m pytest
```

## 构建（Windows）

使用：

```bat
build.bat
```

脚本要求仓库根目录存在 `NetOpsInspector.spec`。

## 安全说明

- 不要在源码中硬编码凭据。
- 运行时凭据建议使用环境变量或安全的密钥下发方式。
- 导出的日志与结果文件应按敏感运维数据处理。

## 许可证

MIT License
