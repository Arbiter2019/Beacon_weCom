export type Employee = {
  userid: string;
  name: string;
  avatar?: string;
  department?: string;
  scope_status: 'enabled' | 'disabled';
  conversation_count: number;
};

export type DirectoryEmployee = Employee;

export type Conversation = {
  conversation_type: 'student' | 'customer_chat';
  external_userid?: string | null;
  chat_id?: string | null;
  display_name: string;
  wechat_name?: string | null;
  avatar?: string | null;
  summary?: string | null;
  last_message_time?: string | null;
  last_viewed_at?: string | null;
  sort_basis: 'last_viewed' | 'last_message';
  member_count?: number | null;
  owner_name?: string | null;
  observer_role?: string | null;
};

export type Message = {
  message_id: number;
  msgid: string;
  msg_type: string;
  is_supported: boolean;
  sender: {
    id: string;
    type: string;
    display_name?: string | null;
    avatar?: string | null;
  };
  content: {
    text?: string | null;
    link?: { title?: string | null; url?: string | null; description?: string | null } | null;
    attachment?: Attachment | null;
  };
  msg_time: string;
  is_recalled: boolean;
  recalled_at?: string | null;
};

export type MessagePage = {
  items: Message[];
  next_cursor?: string | null;
};

export type ConversationPage = {
  items: Conversation[];
  next_cursor?: string | null;
};

export type Attachment = {
  attachment_id: number;
  type: string;
  download_status: string;
  url?: string | null;
  download_error?: string | null;
};
