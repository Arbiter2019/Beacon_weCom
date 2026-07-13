import { Image, MessageSquare, Search, Settings, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { fetchConversations, fetchEmployees, fetchMessages } from './api/client';
import type { Conversation, Employee, Message } from './api/types';

function fmt(value?: string | null) {
  if (!value) return '暂无';
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function App() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationType, setConversationType] = useState('all');
  const [keyword, setKeyword] = useState('');
  const [messageSearch, setMessageSearch] = useState('');
  const [panel, setPanel] = useState<'detail' | 'config'>('detail');

  useEffect(() => {
    fetchEmployees().then((items) => {
      setEmployees(items);
      setSelectedEmployee(items[0] ?? null);
    });
  }, []);

  useEffect(() => {
    if (!selectedEmployee) return;
    fetchConversations(selectedEmployee.userid, conversationType).then((items) => {
      setConversations(items);
      setSelectedConversation(items[0] ?? null);
    });
  }, [selectedEmployee, conversationType]);

  useEffect(() => {
    if (!selectedEmployee || !selectedConversation) return;
    fetchMessages(selectedEmployee.userid, selectedConversation).then(setMessages);
  }, [selectedEmployee, selectedConversation]);

  const filteredConversations = useMemo(() => {
    if (!keyword) return conversations;
    return conversations.filter((item) => `${item.display_name}${item.summary ?? ''}`.includes(keyword));
  }, [conversations, keyword]);

  const searchedMessages = useMemo(() => {
    if (!messageSearch) return messages;
    return messages.filter((item) => `${item.sender.display_name ?? ''}${item.content.text ?? ''}`.includes(messageSearch));
  }, [messages, messageSearch]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">微</div>
          <div>
            <h1>消息存档</h1>
            <span>企业微信会话查看工作台</span>
          </div>
        </div>
        <div className="top-actions">
          <span className="sync-pill"><span className="dot" /> 本地开发模式</span>
          <span className="scope-pill">{selectedEmployee?.name ?? '未选择员工'}</span>
        </div>
      </header>

      <section className="workspace">
        <nav className="side-menu">
          <button className={`menu-item ${panel === 'detail' ? 'active' : ''}`} onClick={() => setPanel('detail')}>
            <MessageSquare size={18} /> 消息查看
          </button>
          <button className={`menu-item ${panel === 'config' ? 'active' : ''}`} onClick={() => setPanel('config')}>
            <Settings size={18} /> 观测配置
          </button>
        </nav>

        <aside className="rail">
          <div className="pane-title">
            <h2>观测员工</h2>
            <span>{employees.length} 个启用</span>
          </div>
          <div className="employee-list">
            {employees.map((employee) => (
              <button
                className={`employee-row ${employee.userid === selectedEmployee?.userid ? 'active' : ''}`}
                key={employee.userid}
                onClick={() => setSelectedEmployee(employee)}
              >
                <span className="avatar">{employee.name.slice(0, 1)}</span>
                <span>
                  <strong>{employee.name}</strong>
                  <small>{employee.department} · {employee.userid}</small>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <aside className="list-pane">
          <div className="pane-title">
            <h2>会话</h2>
            <span>{filteredConversations.length}</span>
          </div>
          <label className="search-box">
            <Search size={16} />
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索学员或学员群" />
          </label>
          <div className="tabs">
            {['all', 'student', 'customer_chat'].map((type) => (
              <button className={conversationType === type ? 'active' : ''} key={type} onClick={() => setConversationType(type)}>
                {type === 'all' ? '全部' : type === 'student' ? '学员' : '学员群'}
              </button>
            ))}
          </div>
          <div className="conversation-list">
            {filteredConversations.map((conversation) => (
              <button
                className={`conversation-row ${conversation === selectedConversation ? 'active' : ''}`}
                key={`${conversation.conversation_type}:${conversation.external_userid ?? conversation.chat_id}`}
                onClick={() => setSelectedConversation(conversation)}
              >
                <div>
                  <strong>{conversation.display_name}</strong>
                  <p>{conversation.summary || '暂无消息'}</p>
                </div>
                <small>{conversation.sort_basis === 'last_viewed' ? '最近查看' : '最近消息'} · {fmt(conversation.last_viewed_at || conversation.last_message_time)}</small>
              </button>
            ))}
          </div>
        </aside>

        <section className="chat-pane">
          <div className="chat-head">
            <div>
              <h2>{selectedConversation?.display_name ?? '未选择会话'}</h2>
              <span>{selectedConversation?.conversation_type === 'customer_chat' ? `${selectedConversation.member_count ?? 0} 名成员` : selectedConversation?.wechat_name}</span>
            </div>
            <label className="message-search">
              <Search size={16} />
              <input value={messageSearch} onChange={(event) => setMessageSearch(event.target.value)} placeholder="搜索当前会话" />
            </label>
          </div>
          <div className="timeline">
            {searchedMessages.map((message) => (
              <article className={`message ${message.sender.type === 'employee' ? 'mine' : ''}`} key={message.msgid}>
                <button className="sender" onClick={() => setPanel('detail')}>{message.sender.display_name ?? message.sender.id}</button>
                <div className={`bubble ${message.is_recalled ? 'recalled' : ''} ${!message.is_supported ? 'unsupported' : ''}`}>
                  {message.is_recalled ? '该消息已被撤回' : !message.is_supported ? message.content.text : message.content.attachment ? (
                    <span className="image-message"><Image size={18} /> 图片消息 · {message.content.attachment.download_status}</span>
                  ) : message.content.link ? (
                    <a href={message.content.link.url ?? '#'}>{message.content.link.title ?? message.content.link.url}</a>
                  ) : (
                    message.content.text
                  )}
                </div>
                <time>{fmt(message.msg_time)}</time>
              </article>
            ))}
          </div>
        </section>

        <aside className="detail-pane">
          {panel === 'config' ? (
            <div className="detail-card">
              <h2><Users size={18} /> 观测范围配置</h2>
              <p>观测范围只影响前端查看权限，不影响底层通讯录、客户、客户群和消息的全量同步。</p>
              {employees.map((employee) => (
                <div className="config-row" key={employee.userid}>
                  <span>{employee.name}</span>
                  <strong>{employee.scope_status === 'enabled' ? '启用' : '停用'}</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="detail-card">
              <h2>{selectedConversation?.display_name ?? '详情'}</h2>
              <dl>
                <dt>类型</dt>
                <dd>{selectedConversation?.conversation_type === 'customer_chat' ? '学员群' : '学员'}</dd>
                <dt>最近消息</dt>
                <dd>{fmt(selectedConversation?.last_message_time)}</dd>
                <dt>排序依据</dt>
                <dd>{selectedConversation?.sort_basis === 'last_viewed' ? '最近查看' : '最近消息'}</dd>
                <dt>边界</dt>
                <dd>当前仅查看此员工关联会话，不跨员工或跨会话搜索。</dd>
              </dl>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}
