import { CheckCircle2, Image, MessageSquare, Search, Settings, Upload, Users } from 'lucide-react';
import { ChangeEvent, useEffect, useMemo, useState } from 'react';

import { fetchConversations, fetchEmployees, fetchMessages, importEmployeesCsv } from './api/client';
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
  const [selectedImportFile, setSelectedImportFile] = useState<File | null>(null);
  const [importStatus, setImportStatus] = useState<string>('未导入');

  const enabledEmployeeCount = employees.filter((employee) => employee.scope_status === 'enabled').length;
  const disabledEmployeeCount = employees.length - enabledEmployeeCount;

  const reloadEmployees = () => {
    fetchEmployees().then((items) => {
      setEmployees(items);
      setSelectedEmployee((current) => {
        if (!current) return items[0] ?? null;
        return items.find((item) => item.userid === current.userid) ?? items[0] ?? null;
      });
    });
  };

  useEffect(() => {
    reloadEmployees();
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

  const onImportFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedImportFile(file);
    setImportStatus(file ? file.name : '未导入');
  };

  const onImportEmployees = async () => {
    if (!selectedImportFile) return;
    setImportStatus('导入中');
    try {
      const result = await importEmployeesCsv(selectedImportFile);
      setImportStatus(`已导入 ${result.imported} 条`);
      reloadEmployees();
    } catch {
      setImportStatus('导入失败');
    }
  };

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

      <section className={`workspace ${panel === 'config' ? 'config-workspace' : ''}`}>
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

        {panel === 'config' ? (
          <section className="config-pane">
            <div className="config-head">
              <div>
                <h2><Users size={18} /> 观测范围配置</h2>
                <span>管理员名单、部门归属、导入状态</span>
              </div>
              <span className="scope-pill"><CheckCircle2 size={16} /> {enabledEmployeeCount} 个启用</span>
            </div>

            <div className="metric-row">
              <div className="metric-tile">
                <span>配置名单</span>
                <strong>{employees.length}</strong>
              </div>
              <div className="metric-tile">
                <span>启用员工</span>
                <strong>{enabledEmployeeCount}</strong>
              </div>
              <div className="metric-tile">
                <span>停用员工</span>
                <strong>{disabledEmployeeCount}</strong>
              </div>
            </div>

            <div className="import-panel">
              <div>
                <h3><Upload size={17} /> 员工名单导入</h3>
                <span>{importStatus}</span>
              </div>
              <div className="import-actions">
                <label className="file-picker">
                  <Upload size={16} />
                  <input accept=".csv,text/csv" type="file" onChange={onImportFileChange} />
                  选择 CSV
                </label>
                <button className="primary-action" disabled={!selectedImportFile || importStatus === '导入中'} onClick={onImportEmployees}>
                  导入名单
                </button>
              </div>
            </div>

            <div className="config-table">
              <div className="config-table-head">
                <span>员工</span>
                <span>部门</span>
                <span>状态</span>
                <span>会话数</span>
              </div>
              {employees.map((employee) => (
                <div className="config-table-row" key={employee.userid}>
                  <span>
                    <strong>{employee.name}</strong>
                    <small>{employee.userid}</small>
                  </span>
                  <span>{employee.department ?? '未配置'}</span>
                  <span className={`status-badge ${employee.scope_status}`}>
                    {employee.scope_status === 'enabled' ? '启用' : '停用'}
                  </span>
                  <span>{employee.conversation_count}</span>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <>
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
            </aside>
          </>
        )}
      </section>
    </main>
  );
}
