# NetOps Inspector (简体中文)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector 是一个用于多厂商网络设备巡检与备份的 CLI 工具。
它可读取 Excel 设备清单，通过 SSH/Telnet 连接设备，执行命令并输出结果工作簿。

## 核心功能

- 多厂商架构（`vendors/`）
- 巡检 / 备份 / 巡检+备份
- 支持 TXT/Excel 批量执行自定义命令
- 输入 Excel 校验（必填字段、重复 IP、vendor/OS 兼容性）
- 重试、超时、并发控制
- 实时 TUI 仪表盘
- 按设备保存会话日志
- 通过 `custom_rules.yaml` 扩展
- 多语言 UI（`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`）

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

## i18n

支持的语言代码：

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

翻译文件：

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`
