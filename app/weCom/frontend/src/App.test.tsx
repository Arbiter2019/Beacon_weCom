import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { conversations, employees, messages } from './data/mock';

vi.mock('./api/client', () => ({
  fetchEmployees: vi.fn(),
  fetchDirectoryEmployees: vi.fn(),
  fetchConversations: vi.fn(),
  fetchMessages: vi.fn(),
  updateObservableEmployee: vi.fn()
}));

import {
  fetchConversations,
  fetchDirectoryEmployees,
  fetchEmployees,
  fetchMessages,
  updateObservableEmployee
} from './api/client';

const mockedFetchEmployees = vi.mocked(fetchEmployees);
const mockedFetchDirectoryEmployees = vi.mocked(fetchDirectoryEmployees);
const mockedFetchConversations = vi.mocked(fetchConversations);
const mockedFetchMessages = vi.mocked(fetchMessages);
const mockedUpdateObservableEmployee = vi.mocked(updateObservableEmployee);

describe('App', () => {
  beforeEach(() => {
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
    mockedFetchConversations.mockResolvedValue(conversations);
    mockedFetchMessages.mockResolvedValue(messages);
    mockedUpdateObservableEmployee.mockResolvedValue({ userid: 'disabled_teacher', scope_status: 'enabled' });
  });

  it('renders employee conversations and unsupported message placeholder', async () => {
    render(<App />);

    expect((await screen.findAllByText('小王老师')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('沈晓雨')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('暂不支持的 file 消息')).length).toBeGreaterThan(0);
  });

  it('only renders the observed employee messages on the self side', async () => {
    mockedFetchMessages.mockResolvedValue([
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
    ]);

    const { container } = render(<App />);

    expect((await screen.findAllByText('我是群内其他员工')).length).toBeGreaterThan(0);
    expect(container.querySelector('[data-message-id="msg_from_observer"]')).toHaveClass('self');
    expect(container.querySelector('[data-message-id="msg_from_other_employee"]')).toHaveClass('other');
  });

  it('renders downloaded image attachments from their local content url', async () => {
    mockedFetchMessages.mockResolvedValue([
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
    ]);

    render(<App />);

    const image = await screen.findByRole('img', { name: '沈晓雨 的图片消息' });
    expect(image).toHaveAttribute('src', '/api/attachments/1/content');
    expect(screen.getByRole('img', { name: '沈晓雨' })).toHaveAttribute(
      'src',
      'https://example.test/xiaoyu.png'
    );
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
    mockedFetchConversations.mockResolvedValue([]);
    mockedFetchMessages.mockResolvedValue([]);

    render(<App />);

    expect(await screen.findByText('暂无观测员工')).toBeInTheDocument();
    expect(screen.getByText('请到配置页添加账号')).toBeInTheDocument();
    expect(screen.queryByText('沈晓雨')).not.toBeInTheDocument();
    expect(screen.queryByText('初三数学群')).not.toBeInTheDocument();
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
});
