import type { Conversation, DirectoryEmployee, Employee, Message } from './types';

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

async function postFormJson<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData
  });
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchEmployees(): Promise<Employee[]> {
  const data = await getJson<{ items: Employee[] }>('/api/observable-employees', { items: [] });
  return data.items;
}

export async function fetchDirectoryEmployees(): Promise<DirectoryEmployee[]> {
  const data = await getJson<{ items: DirectoryEmployee[] }>('/api/directory-employees', { items: [] });
  return data.items;
}

export async function updateObservableEmployee(userid: string, scopeStatus: 'enabled' | 'disabled') {
  return postJson('/api/observable-employees', {
    userid,
    scope_status: scopeStatus
  });
}

export async function importEmployeesCsv(file: File): Promise<{ imported: number; created: number; updated: number; scoped: number }> {
  const formData = new FormData();
  formData.append('file', file);
  return postFormJson('/api/observable-employees/import', formData);
}

export async function fetchConversations(userid: string, type: string): Promise<Conversation[]> {
  const data = await getJson<{ items: Conversation[] }>(
    `/api/observed-employees/${userid}/conversations?type=${type}`,
    { items: [] }
  );
  return data.items;
}

export async function fetchMessages(userid: string, conversation: Conversation): Promise<Message[]> {
  const path =
    conversation.conversation_type === 'student'
      ? `/api/observed-employees/${userid}/student-conversations/${conversation.external_userid}/messages`
      : `/api/observed-employees/${userid}/customer-chat-conversations/${conversation.chat_id}/messages`;
  const data = await getJson<{ items: Message[] }>(path, { items: [] });
  return data.items;
}
