# Inventory Examples

This directory contains inventory examples for all currently supported inventory formats.

- `devices.csv`: CSV rows
- `devices.json`: JSON list of device objects
- `devices_wrapped.json`: JSON object with top-level `devices`

Field requirements are the same across formats.

Credential values support plain text and environment references:

- Plain text: `password: my-password`
- Env reference: `password: env:NETOPS_DEVICE_PASSWORD`
