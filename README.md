# Huawei LTE Extended (SMS Reader)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom component for [Home Assistant](https://www.home-assistant.io/) that extends the built-in [Huawei LTE](https://www.home-assistant.io/integrations/huawei_lte/) integration with SMS reading, new message events, and message management.

## Features

- **Unread SMS sensor** — displays unread message count with recent messages in attributes
- **New SMS event** — fires `huawei_lte_extended_sms_received` when a new message arrives, usable as an automation trigger
- **Services** — read inbox, delete messages, mark as read, send SMS
- **Diagnostics** — sensitive SMS data (phone numbers, message content) is automatically redacted
- **Suspended router support** — services gracefully skip when the base integration is suspended

## Requirements

- Home Assistant with the built-in **Huawei LTE** integration already configured
- A Huawei LTE router/modem with SMS capabilities (e.g. B315, B525, B535, E5186, B618, etc.)

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** > three-dot menu > **Custom repositories**
3. Add `https://github.com/william-aqn/huawei_lte_extended` as **Integration**
4. Search for "Huawei LTE Extended" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/huawei_lte_extended` folder to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for "Huawei LTE Extended"
3. Select your Huawei LTE router from the dropdown
4. Set the SMS polling interval (default: 60 seconds)

## Sensor

### Unread SMS (`sensor.{name}_unread_sms`)

| Property | Description |
|----------|-------------|
| State | Number of unread SMS messages |
| `total_count` | Total number of messages in inbox |
| `messages` | List of up to 10 recent messages |

Each message in the `messages` attribute contains:

| Field | Description |
|-------|-------------|
| `index` | Message index (used for delete/mark_read) |
| `phone` | Sender phone number |
| `content` | Message text |
| `date` | Date and time received |
| `read` | `true` / `false` |

## Event: `huawei_lte_extended_sms_received`

Fired when a new SMS is detected. Event data:

```yaml
phone: "+1234567890"
content: "Your verification code is 1234"
date: "2025-03-29 10:15:00"
index: 40001
entry_id: "abcdef1234567890"
```

### Automation examples

**Forward every SMS to your phone:**

```yaml
automation:
  - alias: "Notify on new SMS"
    trigger:
      - platform: event
        event_type: huawei_lte_extended_sms_received
    action:
      - service: notify.mobile_app_phone
        data:
          title: "SMS from {{ trigger.event.data.phone }}"
          message: "{{ trigger.event.data.content }}"
```

**Extract verification code and send to Telegram:**

```yaml
automation:
  - alias: "Catch verification code from SMS"
    trigger:
      - platform: event
        event_type: huawei_lte_extended_sms_received
    condition:
      - condition: template
        value_template: >
          {{ trigger.event.data.content | regex_search('[Кк]од|[Cc]ode|[Пп]ароль') }}
    action:
      - service: notify.telegram
        data:
          title: "Verification code"
          message: >
            From: {{ trigger.event.data.phone }}
            Code: {{ trigger.event.data.content | regex_findall('[0-9]{4,8}') | first | default('see full text') }}
            Full text: {{ trigger.event.data.content }}
```

**Auto-delete spam SMS by keyword:**

```yaml
automation:
  - alias: "Auto-delete spam SMS"
    trigger:
      - platform: event
        event_type: huawei_lte_extended_sms_received
    condition:
      - condition: template
        value_template: >
          {{ trigger.event.data.content | regex_search('[Кк]редит|[Зз]айм|[Вв]ыигр|casino|lottery') }}
    action:
      - service: huawei_lte_extended.delete_sms
        data:
          entry_id: "{{ trigger.event.data.entry_id }}"
          index: "{{ trigger.event.data.index }}"
```

## Services

### `huawei_lte_extended.get_sms_list`

Fetch SMS inbox with pagination. Returns response data.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `entry_id` | yes | — | Config entry ID |
| `page` | no | 1 | Page number |
| `count` | no | 20 | Messages per page |

### `huawei_lte_extended.delete_sms`

Delete a message by index.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | yes | Config entry ID |
| `index` | yes | Message index |

### `huawei_lte_extended.mark_read`

Mark a message as read.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | yes | Config entry ID |
| `index` | yes | Message index |

### `huawei_lte_extended.send_sms`

Send an SMS message via the router.

| Field | Required | Description |
|-------|----------|-------------|
| `entry_id` | yes | Config entry ID |
| `phone` | yes | Recipient phone number (e.g. `+79001234567`) |
| `message` | yes | Text of the SMS message |

## Dashboard: Send SMS card

Create two helpers in **Settings > Devices & Services > Helpers**:

- `input_text.sms_phone` — Phone number (max length: 20)
- `input_text.sms_message` — Message text (max length: 255)

Then add this card to your dashboard:

```yaml
type: entities
title: Send SMS
entities:
  - entity: input_text.sms_phone
    name: Phone number
  - entity: input_text.sms_message
    name: Message
  - type: button
    name: Send
    icon: mdi:send
    tap_action:
      action: perform-action
      perform_action: huawei_lte_extended.send_sms
      data:
        entry_id: YOUR_ENTRY_ID
        phone: "{{ states('input_text.sms_phone') }}"
        message: "{{ states('input_text.sms_message') }}"
```

> Replace `YOUR_ENTRY_ID` with your config entry ID (find it in **Settings > Devices & Services > Huawei LTE Extended** — click configure, the entry ID is in the URL).

## How it works

The component reuses the connection from the built-in Huawei LTE integration — no duplicate sessions or extra credentials needed. It periodically calls the router's SMS API (`get_sms_list`) and compares message indices to detect new arrivals. On the first poll after startup, existing messages are indexed silently (no events fired) to avoid a flood of notifications.

## License

MIT
