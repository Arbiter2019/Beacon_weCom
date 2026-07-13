import type { Conversation, Employee, Message } from './types';
import { conversations as mockConversations, employees as mockEmployees, messages as mockMessages } from '../data/mock';

const token = import.meta.env.VITE_INTERNAL_ADMIN_TOKEN || 'dev-admin-token';

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(path, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function fetchEmployees(): Promise<Employee[]> {
  const data = await getJson<{ items: Employee[] }>('/api/observable-employees', { items: mockEmployees });
  return data.items;
}

export async function fetchConversations(userid: string, type: string): Promise<Conversation[]> {
  const data = await getJson<{ items: Conversation[] }>(
    `/api/observed-employees/${userid}/conversations?type=${type}`,
    { items: mockConversations }
  );
  return data.items;
}

export async function fetchMessages(userid: string, conversation: Conversation): Promise<Message[]> {
  const path =
    conversation.conversation_type === 'student'
      ? `/api/observed-employees/${userid}/student-conversations/${conversation.external_userid}/messages`
      : `/api/observed-employees/${userid}/customer-chat-conversations/${conversation.chat_id}/messages`;
  const data = await getJson<{ items: Message[] }>(path, { items: mockMessages });
  return data.items;
}
