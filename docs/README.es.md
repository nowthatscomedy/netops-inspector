# NetOps Inspector (Español)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector es una herramienta CLI para inspección y respaldo de dispositivos de red multi-vendor.
Lee inventarios desde Excel, se conecta por SSH/Telnet y genera archivos de resultados.

## Funciones principales

- Arquitectura multi-vendor (`vendors/`)
- Modos de ejecución: inspección / respaldo / inspección+respaldo
- Ejecución por lotes de comandos personalizados (TXT/Excel)
- Validación de entrada Excel (campos obligatorios, IP duplicada, compatibilidad vendor/OS)
- Control de reintentos, timeout y concurrencia
- Dashboard TUI en tiempo real
- Logs de sesión por dispositivo
- Extensión con `custom_rules.yaml`
- UI multilingüe (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## Inicio rápido

```bash
pip install -r requirements.txt
python main.py
```

## i18n

Códigos de idioma soportados:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

Archivos de traducción:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`
