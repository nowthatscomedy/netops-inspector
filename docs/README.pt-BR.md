# NetOps Inspector (Português - Brasil)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector é uma ferramenta CLI para inspeção e backup de dispositivos de rede multi-vendor.
Ela lê inventários em Excel, conecta via SSH/Telnet e gera planilhas de resultado.

## Recursos principais

- Arquitetura multi-vendor (`vendors/`)
- Modos: inspeção / backup / inspeção+backup
- Execução em lote de comandos personalizados (TXT/Excel)
- Validação de entrada Excel (campos obrigatórios, IP duplicado, compatibilidade vendor/OS)
- Controle de retry, timeout e concorrência
- Dashboard TUI em tempo real
- Logs de sessão por dispositivo
- Extensão via `custom_rules.yaml`
- UI multilíngue (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## Início rápido

```bash
pip install -r requirements.txt
python main.py
```

## i18n

Códigos suportados:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

Arquivos de tradução:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`
