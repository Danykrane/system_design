```sql
Project MeetFlow_Physical {
  database_type: "PostgreSQL + Citus / Redis Cluster / ScyllaDB / S3-compatible Object Storage"
  Note: "Physical schema. Cross-storage refs are logical; hot-path JOIN is not used."
}

Table auth_pg.users {
  id uuid [pk]
  email varchar [unique, not null]
  password_hash varchar [not null]
  name varchar
  created_at datetime

  indexes {
    id [name: "pk_users_id"]
    email [unique, name: "ux_users_email"]
    created_at [name: "idx_users_created_at"]
  }
}

Table session_redis.user_sessions {
  session_id varchar [pk]
  user_id uuid [not null]
  expires_at datetime
  created_at datetime

  indexes {
    session_id [name: "key_session_id"]
    user_id [name: "idx_sessions_user_id"]
    expires_at [name: "ttl_sessions_expires_at"]
  }
}

Table meeting_pg.meetings {
  id uuid [pk]
  owner_id uuid [not null]
  home_dc varchar
  topic varchar
  scheduled_start datetime
  duration_minutes integer
  status varchar
  created_at datetime

  indexes {
    id [name: "pk_meetings_id"]
    (owner_id, scheduled_start) [name: "idx_meetings_owner_start"]
    (home_dc, status) [name: "idx_meetings_home_status"]
    (status, created_at) [name: "idx_meetings_status_created"]
  }
}

Table meeting_scylla.meeting_participants {
  meeting_id uuid [not null]
  bucket smallint [not null]
  user_id uuid [not null]
  role varchar
  is_online boolean
  last_joined_at datetime
  last_left_at datetime
  join_count integer
  total_online_seconds bigint

  indexes {
    (meeting_id, bucket, user_id) [pk, name: "pk_participants_meeting_bucket_user"]
    (user_id, last_joined_at) [name: "idx_participants_user_joined"]
  }
}

Table meeting_pg.meeting_invite_links {
  id uuid [pk]
  meeting_id uuid [not null]
  created_by_user_id uuid [not null]
  token varchar [unique, not null]
  token_hash bigint [not null]
  created_at datetime
  expires_at datetime
  revoked boolean

  indexes {
    token [unique, name: "ux_invite_token"]
    token_hash [name: "idx_invite_token_hash"]
    expires_at [name: "idx_invite_expires_at"]
    (meeting_id, created_at) [name: "idx_invite_meeting_created"]
  }
}

Table meeting_scylla.user_meetings {
  user_id uuid [not null]
  scheduled_start datetime [not null]
  meeting_id uuid [not null]
  topic varchar
  status varchar
  role varchar

  indexes {
    (user_id, scheduled_start, meeting_id) [pk, name: "pk_user_meetings_user_start_meeting"]
    (meeting_id, user_id) [name: "idx_user_meetings_meeting_user"]
  }
}

Table runtime_redis.meetings_runtime {
  meeting_id uuid [pk]
  status varchar
  participants_online_count integer
  participants_total_count integer
  sfu_pool varchar
  updated_at datetime

  indexes {
    meeting_id [name: "key_runtime_meeting_id"]
    updated_at [name: "idx_runtime_updated_at"]
  }
}

Table chat_scylla.chat_messages {
  id uuid [unique, not null]
  meeting_id uuid [not null]
  bucket smallint [not null]
  message_seq integer [not null]
  user_id uuid [not null]
  body text
  created_at datetime

  indexes {
    (meeting_id, bucket, message_seq) [pk, name: "pk_chat_meeting_bucket_seq"]
    id [unique, name: "ux_chat_message_id"]
    (user_id, created_at) [name: "idx_chat_user_created"]
  }
}

Table recording_pg.recordings {
  id uuid [pk]
  meeting_id uuid [not null]
  storage_bucket varchar
  storage_key varchar
  storage_url varchar
  size_bytes bigint
  duration_seconds integer
  status varchar
  created_at datetime

  indexes {
    id [name: "pk_recordings_id"]
    (meeting_id, created_at) [name: "idx_recordings_meeting_created"]
    (status, created_at) [name: "idx_recordings_status_created"]
    storage_key [name: "idx_recordings_storage_key"]
  }
}

Table recording_obj.recording_upload_buffer {
  chunk_id uuid [pk]
  recording_id uuid [not null]
  chunk_number bigint [not null]
  storage_key varchar [not null]
  size_bytes bigint
  checksum varchar
  status varchar
  expires_at datetime

  indexes {
    chunk_id [name: "pk_recording_chunk"]
    (recording_id, chunk_number) [unique, name: "ux_recording_chunk_number"]
    (recording_id, status) [name: "idx_recording_chunks_status"]
    expires_at [name: "ttl_recording_chunks_expires"]
  }
}

Ref: auth_pg.users.id < meeting_pg.meetings.owner_id
Ref: auth_pg.users.id < session_redis.user_sessions.user_id
Ref: auth_pg.users.id < meeting_pg.meeting_invite_links.created_by_user_id
Ref: auth_pg.users.id < meeting_scylla.meeting_participants.user_id
Ref: auth_pg.users.id < meeting_scylla.user_meetings.user_id
Ref: auth_pg.users.id < chat_scylla.chat_messages.user_id

Ref: meeting_pg.meetings.id < meeting_scylla.meeting_participants.meeting_id
Ref: meeting_pg.meetings.id < meeting_pg.meeting_invite_links.meeting_id
Ref: meeting_pg.meetings.id - runtime_redis.meetings_runtime.meeting_id
Ref: meeting_pg.meetings.id < meeting_scylla.user_meetings.meeting_id
Ref: meeting_pg.meetings.id < chat_scylla.chat_messages.meeting_id
Ref: meeting_pg.meetings.id < recording_pg.recordings.meeting_id

Ref: recording_pg.recordings.id < recording_obj.recording_upload_buffer.recording_id
```