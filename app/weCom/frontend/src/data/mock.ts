import type { Conversation, Employee, Message } from '../api/types';

export const employees: Employee[] = [
  {
    userid: 'wang_teacher',
    name: '小王老师',
    department: '初中部',
    scope_status: 'enabled',
    conversation_count: 2
  },
  {
    userid: 'li_teacher',
    name: '李老师',
    department: '高中部',
    scope_status: 'enabled',
    conversation_count: 1
  }
];

export const conversations: Conversation[] = [
  {
    conversation_type: 'student',
    external_userid: 'external_xiaoyu',
    display_name: '沈晓雨',
    wechat_name: '小雨',
    summary: '先看交点，再看单调区间。',
    last_message_time: '2026-06-19T09:34:00',
    last_viewed_at: '2026-06-19T09:36:00',
    sort_basis: 'last_viewed'
  },
  {
    conversation_type: 'customer_chat',
    chat_id: 'chat_math',
    display_name: '初三数学群',
    summary: '暂不支持的 file 消息',
    last_message_time: '2026-06-19T09:31:00',
    sort_basis: 'last_message',
    member_count: 36,
    owner_name: '小王老师',
    observer_role: '群主'
  }
];

export const messages: Message[] = [
  {
    message_id: 1,
    msgid: 'msg_text',
    msg_type: 'text',
    is_supported: true,
    sender: { id: 'wang_teacher', type: 'employee', display_name: '小王老师' },
    content: { text: '先看交点，再看单调区间。' },
    msg_time: '2026-06-19T09:34:00',
    is_recalled: false
  },
  {
    message_id: 2,
    msgid: 'msg_image',
    msg_type: 'image',
    is_supported: true,
    sender: { id: 'external_xiaoyu', type: 'external_contact', display_name: '沈晓雨' },
    content: { text: '[图片]', attachment: { attachment_id: 1, type: 'image', download_status: 'pending' } },
    msg_time: '2026-06-19T09:35:00',
    is_recalled: false
  },
  {
    message_id: 3,
    msgid: 'msg_recalled',
    msg_type: 'text',
    is_supported: true,
    sender: { id: 'external_xiaoyu', type: 'external_contact', display_name: '沈晓雨' },
    content: { text: '这条消息稍后撤回' },
    msg_time: '2026-06-19T09:36:00',
    is_recalled: true,
    recalled_at: '2026-06-19T09:37:00'
  },
  {
    message_id: 4,
    msgid: 'msg_file',
    msg_type: 'file',
    is_supported: false,
    sender: { id: 'wang_teacher', type: 'employee', display_name: '小王老师' },
    content: { text: '暂不支持的 file 消息' },
    msg_time: '2026-06-19T09:38:00',
    is_recalled: false
  }
];
