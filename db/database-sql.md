```sql
Project discord_zoom_calls_mvp {
  database_type: "PostgreSQL"
  Note: '''
  Логическая схема БД для Discord/Zoom-подобного сервиса звонков (WebRTC + SFU).
  Фокус: auth, community/rooms, messaging, recordings, realtime state.
  Бинарные данные записей хранятся в object storage, в БД лежат только метаданные.
  '''
}

Table users {
  id uuid [pk, not null]
  email varchar(128) [not null, unique]
  phone_number varchar(32) [unique]
  display_name varchar(128) [not null]
  password_hash varchar(255) [not null]
  created_at timestamp [not null]
  updated_at timestamp [not null]

  Note: 'Пользователи и учетные данные'

  Indexes {
    email [name: 'idx_users_email', unique]
    phone_number [name: 'idx_users_phone', unique]
  }
}

Table sessions {
  token varchar(128) [pk, not null]
  user_id uuid [not null]
  device_id varchar(128) [not null]
  user_agent varchar(255)
  ip_address varchar(64)
  created_at timestamp [not null]
  expires_at timestamp [not null]

  Note: 'Активные пользовательские сессии'

  Indexes {
    user_id [name: 'idx_sessions_user_id']
    expires_at [name: 'idx_sessions_expires_at']
  }
}

Table servers {
  id uuid [pk, not null]
  owner_id uuid [not null]
  title varchar(255) [not null]
  description varchar(1024)
  created_at timestamp [not null]
  updated_at timestamp [not null]

  Note: 'Сообщества (Discord-like servers)'

  Indexes {
    owner_id [name: 'idx_servers_owner_id']
    updated_at [name: 'idx_servers_updated_at']
  }
}

Table rooms {
  id uuid [pk, not null]
  server_id uuid [not null]
  room_type varchar(32) [not null, note: 'voice | video | text']
  title varchar(255) [not null]
  created_by uuid [not null]
  created_at timestamp [not null]
  updated_at timestamp [not null]

  Note: 'Комнаты/каналы внутри сообщества'

  Indexes {
    server_id [name: 'idx_rooms_server_id']
    (server_id, room_type) [name: 'idx_rooms_server_type']
    updated_at [name: 'idx_rooms_updated_at']
  }
}

Table room_participants {
  room_id uuid [not null]
  user_id uuid [not null]
  role varchar(32) [not null, note: 'owner | admin | member']
  is_muted boolean [not null, default: false]
  is_video_enabled boolean [not null, default: true]
  joined_at timestamp [not null]
  left_at timestamp
  updated_at timestamp [not null]

  Note: 'Состав и состояние участников в комнате'

  Indexes {
    (room_id, user_id) [pk]
    user_id [name: 'idx_room_participants_user_id']
    (room_id, role) [name: 'idx_room_participants_role']
  }
}

Table messages {
  id uuid [pk, not null]
  room_id uuid [not null]
  sender_id uuid [not null]
  seq_no bigint [not null]
  body text [not null]
  created_at timestamp [not null]
  edited_at timestamp

  Note: 'Текстовые сообщения комнат'

  Indexes {
    (room_id, seq_no) [name: 'uq_messages_room_seq', unique]
    (room_id, created_at) [name: 'idx_messages_room_created_at']
    sender_id [name: 'idx_messages_sender_id']
  }
}

Table message_reactions {
  id uuid [pk, not null]
  message_id uuid [not null]
  user_id uuid [not null]
  emoji varchar(16) [not null]
  created_at timestamp [not null]

  Note: 'Реакции на сообщения'

  Indexes {
    (message_id, user_id, emoji) [name: 'uq_message_reactions_m_u_e', unique]
    message_id [name: 'idx_message_reactions_message_id']
  }
}

Table recordings {
  id uuid [pk, not null]
  room_id uuid [not null]
  created_by uuid [not null]
  object_key varchar(512) [not null, unique]
  size_bytes bigint [not null]
  duration_seconds integer [not null]
  created_at timestamp [not null]

  Note: 'Метаданные записей звонков, бинарные файлы лежат в S3'

  Indexes {
    room_id [name: 'idx_recordings_room_id']
    (room_id, created_at) [name: 'idx_recordings_room_created_at']
  }
}

Table analytics_events {
  id uuid [pk, not null]
  room_id uuid
  user_id uuid
  event_type varchar(64) [not null]
  payload json
  event_time timestamp [not null]

  Note: 'Технические и продуктовые события (append-only)'

  Indexes {
    event_time [name: 'idx_analytics_events_event_time']
    event_type [name: 'idx_analytics_events_event_type']
    room_id [name: 'idx_analytics_events_room_id']
  }
}

Table presence {
  user_id uuid [not null]
  device_id varchar(128) [not null]
  status varchar(32) [not null, note: 'online | offline | away']
  last_seen_at timestamp [not null]
  updated_at timestamp [not null]

  Note: 'Состояние присутствия пользователя'

  Indexes {
    (user_id, device_id) [pk]
  }
}

Ref: sessions.user_id > users.id

Ref: servers.owner_id > users.id

Ref: rooms.server_id > servers.id
Ref: rooms.created_by > users.id

Ref: room_participants.room_id > rooms.id
Ref: room_participants.user_id > users.id

Ref: messages.room_id > rooms.id
Ref: messages.sender_id > users.id

Ref: message_reactions.message_id > messages.id
Ref: message_reactions.user_id > users.id

Ref: recordings.room_id > rooms.id
Ref: recordings.created_by > users.id

Ref: analytics_events.room_id > rooms.id
Ref: analytics_events.user_id > users.id

Ref: presence.user_id > users.id
```
