import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { conversations, employees, messages } from './data/mock';
import type { Conversation } from './api/types';

vi.mock('./api/client', () => ({
  fetchEmployees: vi.fn(),
  fetchDirectoryEmployees: vi.fn(),
  fetchConversations: vi.fn(),
  fetchMessages: vi.fn(),
  triggerAttachmentDownload: vi.fn(),
  updateObservableEmployee: vi.fn()
}));

import {
  fetchConversations,
  fetchDirectoryEmployees,
  fetchEmployees,
  fetchMessages,
  triggerAttachmentDownload,
  updateObservableEmployee
} from './api/client';

const mockedFetchEmployees = vi.mocked(fetchEmployees);
const mockedFetchDirectoryEmployees = vi.mocked(fetchDirectoryEmployees);
const mockedFetchConversations = vi.mocked(fetchConversations);
const mockedFetchMessages = vi.mocked(fetchMessages);
const mockedTriggerAttachmentDownload = vi.mocked(triggerAttachmentDownload);
const mockedUpdateObservableEmployee = vi.mocked(updateObservableEmployee);

function messagePage(items: typeof messages, nextCursor: string | null = null) {
  return { items, next_cursor: nextCursor };
}

function conversationPage(items: Conversation[], nextCursor: string | null = null) {
  return { items, next_cursor: nextCursor };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedFetchEmployees.mockResolvedValue(employees);
    mockedFetchDirectoryEmployees.mockResolvedValue([
      ...employees,
      {
        userid: 'disabled_teacher',
        name: '未观测老师',
        department: '初中部',
        scope_status: 'disabled',
        conversation_count: 0
      }
    ]);
    mockedFetchConversations.mockResolvedValue(conversationPage(conversations));
    mockedFetchMessages.mockResolvedValue(messagePage(messages));
    mockedTriggerAttachmentDownload.mockResolvedValue({
      attachment_id: 1,
      type: 'image',
      download_status: 'downloading',
      url: null,
      download_error: null
    });
    mockedUpdateObservableEmployee.mockResolvedValue({ userid: 'disabled_teacher', scope_status: 'enabled' });
  });

  it('renders employee conversations and unsupported message placeholder', async () => {
    render(<App />);

    expect((await screen.findAllByText('小王老师')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('沈晓雨')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('暂不支持的 file 消息')).length).toBeGreaterThan(0);
  });

  it('only renders the observed employee messages on the self side', async () => {
    mockedFetchMessages.mockResolvedValue(messagePage([
      {
        message_id: 20,
        msgid: 'msg_from_observer',
        msg_type: 'text',
        is_supported: true,
        sender: { id: 'wang_teacher', type: 'employee', display_name: '小王老师' },
        content: { text: '我是观测员工' },
        msg_time: '2026-06-19T09:34:00',
        is_recalled: false
      },
      {
        message_id: 21,
        msgid: 'msg_from_other_employee',
        msg_type: 'text',
        is_supported: true,
        sender: { id: 'li_teacher', type: 'employee', display_name: '李老师' },
        content: { text: '我是群内其他员工' },
        msg_time: '2026-06-19T09:35:00',
        is_recalled: false
      }
    ]));

    const { container } = render(<App />);

    expect((await screen.findAllByText('我是群内其他员工')).length).toBeGreaterThan(0);
    expect(container.querySelector('[data-message-id="msg_from_observer"]')).toHaveClass('self');
    expect(container.querySelector('[data-message-id="msg_from_other_employee"]')).toHaveClass('other');
  });

  it('renders downloaded image attachments from their local content url', async () => {
    mockedFetchMessages.mockResolvedValue(messagePage([
      {
        message_id: 22,
        msgid: 'msg_downloaded_image',
        msg_type: 'image',
        is_supported: true,
        sender: {
          id: 'external_xiaoyu',
          type: 'external_contact',
          display_name: '沈晓雨',
          avatar: 'https://example.test/xiaoyu.png'
        },
        content: {
          text: '[图片]',
          attachment: {
            attachment_id: 1,
            type: 'image',
            download_status: 'downloaded',
            url: '/api/attachments/1/content'
          }
        },
        msg_time: '2026-06-19T09:35:00',
        is_recalled: false
      }
    ]));

    const { container } = render(<App />);

    const image = await screen.findByRole('img', { name: '沈晓雨 的图片消息' });
    expect(image).toHaveAttribute('src', '/api/attachments/1/content?token=dev-admin-token');
    await userEvent.click(image);
    expect(screen.getByRole('img', { name: '图片消息预览' })).toHaveAttribute(
      'src',
      '/api/attachments/1/content?token=dev-admin-token'
    );
    expect(screen.getByRole('img', { name: '沈晓雨' })).toHaveAttribute(
      'src',
      'https://example.test/xiaoyu.png'
    );
  });

  it('triggers image attachment download and refreshes messages while downloading', async () => {
    mockedFetchMessages
      .mockResolvedValueOnce(messagePage([
        {
          message_id: 23,
          msgid: 'msg_pending_image',
          msg_type: 'image',
          is_supported: true,
          sender: { id: 'external_xiaoyu', type: 'external_contact', display_name: '沈晓雨' },
          content: {
            text: '[图片]',
            attachment: {
              attachment_id: 1,
              type: 'image',
              download_status: 'pending',
              url: null
            }
          },
          msg_time: '2026-06-19T09:35:00',
          is_recalled: false
        }
      ]))
      .mockResolvedValueOnce(messagePage([
        {
          message_id: 23,
          msgid: 'msg_pending_image',
          msg_type: 'image',
          is_supported: true,
          sender: { id: 'external_xiaoyu', type: 'external_contact', display_name: '沈晓雨' },
          content: {
            text: '[图片]',
            attachment: {
              attachment_id: 1,
              type: 'image',
              download_status: 'downloading',
              url: null
            }
          },
          msg_time: '2026-06-19T09:35:00',
          is_recalled: false
        }
      ]));

    render(<App />);

    const callsBeforeClick = mockedFetchMessages.mock.calls.length;
    await userEvent.click(await screen.findByRole('button', { name: '下载图片' }));

    expect(mockedTriggerAttachmentDownload).toHaveBeenCalledWith(1);
    expect(mockedFetchMessages.mock.calls.length).toBeGreaterThan(callsBeforeClick);
    expect(await screen.findByText('图片下载中')).toBeInTheDocument();
  });

  it('shows retry for failed image downloads and expired text for expired media', async () => {
    mockedFetchMessages.mockResolvedValue(messagePage([
      {
        message_id: 24,
        msgid: 'msg_failed_image',
        msg_type: 'image',
        is_supported: true,
        sender: { id: 'external_xiaoyu', type: 'external_contact', display_name: '沈晓雨' },
        content: {
          text: '[图片]',
          attachment: {
            attachment_id: 2,
            type: 'image',
            download_status: 'failed',
            url: null,
            download_error: 'sdk failed'
          }
        },
        msg_time: '2026-06-19T09:35:00',
        is_recalled: false
      },
      {
        message_id: 25,
        msgid: 'msg_expired_image',
        msg_type: 'image',
        is_supported: true,
        sender: { id: 'external_xiaoyu', type: 'external_contact', display_name: '沈晓雨' },
        content: {
          text: '[图片]',
          attachment: {
            attachment_id: 3,
            type: 'image',
            download_status: 'expired',
            url: null,
            download_error: 'GetMediaData error code=10010'
          }
        },
        msg_time: '2026-06-19T09:36:00',
        is_recalled: false
      }
    ]));

    render(<App />);

    expect(await screen.findByRole('button', { name: '重试下载图片' })).toBeInTheDocument();
    expect(screen.getByText('文件已过期/无法下载')).toBeInTheDocument();
  });

  it('opens observation configuration panel', async () => {
    render(<App />);

    await userEvent.click(await screen.findByText('配置观测员工账号'));

    expect(screen.getByRole('heading', { name: '企业通讯录' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '已观测员工' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '添加' })).toBeDisabled();
    expect(screen.queryByText('员工名单导入')).not.toBeInTheDocument();
    expect(screen.queryByText('选择 CSV')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('搜索当前会话')).not.toBeInTheDocument();
    expect(screen.queryByText('初三数学群')).not.toBeInTheDocument();
  });

  it('renders empty states when backend returns no accessible data', async () => {
    mockedFetchEmployees.mockResolvedValue([]);
    mockedFetchDirectoryEmployees.mockResolvedValue([]);
    mockedFetchConversations.mockResolvedValue(conversationPage([]));
    mockedFetchMessages.mockResolvedValue(messagePage([]));

    render(<App />);

    expect(await screen.findByText('暂无观测员工')).toBeInTheDocument();
    expect(screen.getByText('请到配置页添加账号')).toBeInTheDocument();
    expect(screen.queryByText('沈晓雨')).not.toBeInTheDocument();
    expect(screen.queryByText('初三数学群')).not.toBeInTheDocument();
  });

  it('loads the next conversation page when the list is scrolled to the bottom', async () => {
    const nextConversation: Conversation = {
      conversation_type: 'student',
      external_userid: 'external_later',
      display_name: '后续学员',
      wechat_name: '后续微信',
      summary: '第二页会话',
      last_message_time: '2026-06-19T08:34:00',
      sort_basis: 'last_message'
    };
    mockedFetchConversations
      .mockResolvedValueOnce(conversationPage([conversations[0]], 'cursor-page-2'))
      .mockResolvedValueOnce(conversationPage([nextConversation], null));

    const { container } = render(<App />);

    expect((await screen.findAllByText('沈晓雨')).length).toBeGreaterThan(0);
    const conversationList = container.querySelector('.conversation-list') as HTMLDivElement;
    Object.defineProperty(conversationList, 'scrollTop', { value: 90, configurable: true });
    Object.defineProperty(conversationList, 'clientHeight', { value: 10, configurable: true });
    Object.defineProperty(conversationList, 'scrollHeight', { value: 100, configurable: true });

    await act(async () => {
      conversationList.dispatchEvent(new Event('scroll', { bubbles: true }));
    });

    expect(await screen.findByText('后续学员')).toBeInTheDocument();
    expect(mockedFetchConversations).toHaveBeenLastCalledWith('wang_teacher', 'all', 'cursor-page-2');
  });

  it('opens message search and conversation detail drawers', async () => {
    render(<App />);

    await userEvent.click(await screen.findByRole('button', { name: '搜索对话消息' }));

    expect(screen.getByRole('heading', { name: '搜索对话消息' })).toBeInTheDocument();
    expect(screen.getByText(/只在当前已打开会话内检索/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '关闭消息搜索' }));
    await userEvent.click(screen.getByRole('button', { name: '打开会话详情' }));

    expect(screen.getByRole('dialog', { name: /沈晓雨/ })).toBeInTheDocument();
    expect(screen.getByText('查看上下文')).toBeInTheDocument();
  });

  it('switches archive panes from the mobile switcher', async () => {
    const { container } = render(<App />);

    const workspace = container.querySelector('.workspace');
    expect(workspace).toHaveClass('show-scope');

    await userEvent.click(screen.getByRole('button', { name: '会话' }));
    expect(workspace).toHaveClass('show-list');

    await userEvent.click(screen.getByRole('button', { name: '聊天' }));
    expect(workspace).toHaveClass('show-chat');
  });

  it('does not let a stale employee message response replace the current employee messages', async () => {
    const firstEmployeeMessages = deferred<ReturnType<typeof messagePage>>();
    mockedFetchMessages.mockImplementation((userid) => {
      if (userid === 'wang_teacher') return firstEmployeeMessages.promise;
      return Promise.resolve(messagePage([
        {
          message_id: 30,
          msgid: 'msg_li_teacher_current',
          msg_type: 'text',
          is_supported: true,
          sender: { id: 'li_teacher', type: 'employee', display_name: '李老师' },
          content: { text: '李老师当前消息' },
          msg_time: '2026-06-19T10:00:00',
          is_recalled: false
        }
      ]));
    });

    const { container } = render(<App />);

    await userEvent.click(await screen.findByRole('button', { name: /李老师/ }));
    expect((await screen.findAllByText('李老师当前消息')).length).toBeGreaterThan(0);

    await act(async () => {
      firstEmployeeMessages.resolve(messagePage(messages));
      await firstEmployeeMessages.promise;
    });

    expect(container.querySelector('[data-message-id="msg_text"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-message-id="msg_li_teacher_current"]')).toBeInTheDocument();
    expect(screen.getAllByText('李老师当前消息').length).toBeGreaterThan(0);
  });
});
