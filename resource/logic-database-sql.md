
```sql
Project MeetFlow {
  database_type: "Logical schema"
  Note: "Zoom-like video meetings service. Logical DB schema without physical sharding."
}

Table users {
  id uuid [pk]
  email varchar [unique, not null]
  password_hash varchar [not null]
  name varchar
  created_at datetime
}

Table user_sessions {
  session_id varchar [pk]
  user_id uuid [not null]
  expires_at datetime
  created_at datetime
}

Table meetings {
  id uuid [pk]
  owner_id uuid [not null]
  home_dc varchar
  topic varchar
  scheduled_start datetime
  duration_minutes integer
  status varchar
  created_at datetime
}

Table meeting_participants {
  meeting_id uuid [pk, not null]
  user_id uuid [pk, not null]
  role varchar
  is_online boolean
  last_joined_at datetime
  last_left_at datetime
  join_count integer
  total_online_seconds bigint
}

Table meeting_invite_links {
  id uuid [pk]
  meeting_id uuid [not null]
  created_by_user_id uuid [not null]
  token varchar [unique, not null]
  created_at datetime
  expires_at datetime
  revoked boolean
}

Table user_meetings {
  user_id uuid [pk, not null]
  meeting_id uuid [pk, not null]
  topic varchar
  scheduled_start datetime
  status varchar
  role varchar
}

Table meetings_runtime {
  meeting_id uuid [pk, not null]
  status varchar
  participants_online_count integer
  participants_total_count integer
  sfu_pool varchar
  updated_at datetime
}

Table chat_messages {
  id uuid [pk]
  meeting_id uuid [not null]
  user_id uuid [not null]
  message_seq integer
  body text
  created_at datetime
}

Table recordings {
  id uuid [pk]
  meeting_id uuid [not null]
  storage_url varchar
  size_bytes bigint
  duration_seconds integer
  status varchar
  created_at datetime
}

Table recording_upload_buffer {
  chunk_id uuid [pk]
  recording_id uuid [not null]
  chunk_number bigint
  size_bytes bigint
  checksum varchar
  status varchar
  expires_at datetime
}

Ref: users.id < meetings.owner_id
Ref: users.id < user_sessions.user_id
Ref: users.id < meeting_invite_links.created_by_user_id
Ref: users.id < chat_messages.user_id
Ref: users.id < user_meetings.user_id
Ref: users.id < meeting_participants.user_id

Ref: meetings.id < meeting_participants.meeting_id
Ref: meetings.id < meeting_invite_links.meeting_id
Ref: meetings.id - meetings_runtime.meeting_id
Ref: meetings.id < recordings.meeting_id
Ref: meetings.id < chat_messages.meeting_id
Ref: meetings.id < user_meetings.meeting_id

Ref: recordings.id < recording_upload_buffer.recording_id
```