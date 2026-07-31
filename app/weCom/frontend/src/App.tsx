import {
  Archive,
  BarChart3,
  Check,
  ChevronRight,
  CircleHelp,
  Folder,
  Image,
  MessageSquare,
  Search,
  Settings,
  Users
} from 'lucide-react';
import { ChangeEvent, UIEvent, useEffect, useMemo, useRef, useState } from 'react';

import {
  fetchAnalysisCustomerChats,
  fetchAnalysisQuestions,
  fetchCustomerChatSummary,
  fetchObservedEmployeeSummary,
  fetchQuestionCategories,
  fetchResponseGroups
} from './api/analysisClient';
import type {
  AnalysisCustomerChat,
  AnalysisQuestion,
  AnalysisSummary,
  PagedResult,
  QuestionCategory,
  ResponseGroupSort,
  ResponseGroupStat
} from './api/analysisTypes';
import {
  fetchConversations,
  fetchDirectoryEmployees,
  fetchEmployees,
  fetchMessages,
  triggerAttachmentDownload,
  updateObservableEmployee
} from './api/client';
import type { Conversation, ConversationPage, DirectoryEmployee, Employee, Message, MessagePage } from './api/types';

type ProductView = 'archive' | 'config' | 'analysisEmployee' | 'analysisGroup';
type ConversationFilter = 'all' | 'student' | 'group';
type MobileArchiveView = 'scope' | 'list' | 'chat';
const assetToken = import.meta.env.VITE_INTERNAL_ADMIN_TOKEN || 'dev-admin-token';
const defaultAnalysisUserid = 'XiaoHaiYan_3';
const defaultAnalysisStart = '2026-07-23';
const defaultAnalysisEnd = '2026-07-29';

function fmt(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function avatarText(value?: string | null) {
  return (value || '—').slice(0, 1);
}

function Avatar({ name, src, variant = '' }: { name?: string | null; src?: string | null; variant?: string }) {
  const className = `avatar ${variant}`.trim();
  if (src) {
    return (
      <span className={className}>
        <img alt={name || '头像'} src={src} />
      </span>
    );
  }
  return <span className={className}>{avatarText(name)}</span>;
}

function uiConversationType(type: Conversation['conversation_type']): 'student' | 'group' {
  return type === 'customer_chat' ? 'group' : 'student';
}

function apiConversationType(type: ConversationFilter): string {
  return type === 'group' ? 'customer_chat' : type;
}

function conversationKey(conversation: Conversation) {
  return `${conversation.conversation_type}:${conversation.external_userid ?? conversation.chat_id}`;
}

function messageText(message: Message) {
  if (message.is_recalled) return '该消息已被撤回';
  if (!message.is_supported) return message.content.text || `暂不支持的 ${message.msg_type} 消息`;
  return message.content.text || message.content.link?.title || message.content.attachment?.type || '';
}

function authenticatedAssetUrl(url?: string | null) {
  if (!url) return null;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(assetToken)}`;
}

function emptyAnalysisSummary(): AnalysisSummary {
  return {
    overview: {
      single_message_count: 0,
      room_message_count: 0,
      received_message_count: 0,
      sent_message_count: 0,
      question_count: 0,
      avg_response_seconds: 0
    },
    message_trend: [],
    message_type_distribution: [],
    sentiment_summary: {
      positive_count: 0,
      neutral_count: 0,
      negative_count: 0,
      total_count: 0,
      covered_room_count: 0
    },
    hotwords: [],
    question_category_stats: [],
    response_daily_stats: []
  };
}

function formatSeconds(seconds?: number | null) {
  if (!seconds) return '00:00';
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="analysis-metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Bars({ items }: { items: { label: string; value: number }[] }) {
  const max = Math.max(1, ...items.map((item) => item.value));
  return (
    <div className="analysis-bars">
      {items.map((item) => (
        <div className="analysis-bar-row" key={item.label}>
          <span>{item.label}</span>
          <b style={{ width: `${Math.max(6, (item.value / max) * 100)}%` }} />
          <em>{item.value}</em>
        </div>
      ))}
    </div>
  );
}

function MiniLine({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  const points = values.length
    ? values.map((value, index) => `${(index / Math.max(1, values.length - 1)) * 100},${80 - (value / max) * 60}`).join(' ')
    : '0,80 100,80';
  return (
    <svg className="analysis-line" viewBox="0 0 100 90" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} />
    </svg>
  );
}

function normalizeMessagePage(page: MessagePage | Message[]): MessagePage {
  return Array.isArray(page) ? { items: page, next_cursor: null } : page;
}

function normalizeConversationPage(page: ConversationPage | Conversation[]): ConversationPage {
  return Array.isArray(page) ? { items: page, next_cursor: null } : page;
}

export default function App() {
  const [productView, setProductView] = useState<ProductView>('archive');
  const [mobileView, setMobileView] = useState<MobileArchiveView>('scope');
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [directoryEmployees, setDirectoryEmployees] = useState<DirectoryEmployee[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [employeeKeyword, setEmployeeKeyword] = useState('');
  const [directoryKeyword, setDirectoryKeyword] = useState('');
  const [selectedDirectoryUserids, setSelectedDirectoryUserids] = useState<Set<string>>(new Set());
  const [selectedObservedUserids, setSelectedObservedUserids] = useState<Set<string>>(new Set());
  const [configStatus, setConfigStatus] = useState('请选择左侧员工后添加，或在右侧选择员工后移出。');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageNextCursor, setMessageNextCursor] = useState<string | null>(null);
  const [loadingOlderMessages, setLoadingOlderMessages] = useState(false);
  const [conversationFilter, setConversationFilter] = useState<ConversationFilter>('all');
  const [conversationKeyword, setConversationKeyword] = useState('');
  const [conversationNextCursor, setConversationNextCursor] = useState<string | null>(null);
  const [loadingMoreConversations, setLoadingMoreConversations] = useState(false);
  const [messageSearchOpen, setMessageSearchOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [messageQuery, setMessageQuery] = useState('');
  const [messageSender, setMessageSender] = useState('');
  const [messageFrom, setMessageFrom] = useState('');
  const [messageTo, setMessageTo] = useState('');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [triggeringAttachmentIds, setTriggeringAttachmentIds] = useState<Set<number>>(new Set());
  const [analysisUserid, setAnalysisUserid] = useState(defaultAnalysisUserid);
  const [analysisStartDate, setAnalysisStartDate] = useState(defaultAnalysisStart);
  const [analysisEndDate, setAnalysisEndDate] = useState(defaultAnalysisEnd);
  const [analysisConversationType, setAnalysisConversationType] = useState<'all' | 'single' | 'room'>('all');
  const [analysisSummary, setAnalysisSummary] = useState<AnalysisSummary>(emptyAnalysisSummary);
  const [analysisQuestions, setAnalysisQuestions] = useState<PagedResult<AnalysisQuestion>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 50
  });
  const [analysisResponseGroups, setAnalysisResponseGroups] = useState<PagedResult<ResponseGroupStat>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 50
  });
  const [analysisResponseSort, setAnalysisResponseSort] = useState<ResponseGroupSort>('analysis_date');
  const [analysisResponseOrder, setAnalysisResponseOrder] = useState<'asc' | 'desc'>('desc');
  const [questionCategories, setQuestionCategories] = useState<QuestionCategory[]>([]);
  const [customerChats, setCustomerChats] = useState<PagedResult<AnalysisCustomerChat>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 50
  });
  const [selectedAnalysisRoomid, setSelectedAnalysisRoomid] = useState('');
  const [groupSummary, setGroupSummary] = useState<AnalysisSummary>(emptyAnalysisSummary);
  const [groupQuestions, setGroupQuestions] = useState<PagedResult<AnalysisQuestion>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 50
  });
  const conversationRequestRef = useRef(0);
  const messageRequestRef = useRef(0);

  const loadEmployees = () => {
    Promise.all([fetchEmployees(), fetchDirectoryEmployees()]).then(([observedItems, directoryItems]) => {
      setEmployees(observedItems);
      setDirectoryEmployees(directoryItems);
      setSelectedEmployee((current) => {
        if (!current) return observedItems[0] ?? null;
        return observedItems.find((item) => item.userid === current.userid) ?? observedItems[0] ?? null;
      });
    });
  };

  useEffect(() => {
    loadEmployees();
  }, []);

  useEffect(() => {
    fetchQuestionCategories().then((result) => setQuestionCategories(result.items.filter((item) => item.enabled)));
  }, []);

  useEffect(() => {
    if (productView !== 'analysisEmployee') return;
    Promise.all([
      fetchObservedEmployeeSummary(analysisUserid, {
        startDate: analysisStartDate,
        endDate: analysisEndDate,
        conversationType: analysisConversationType
      }),
      fetchAnalysisQuestions('employee', analysisUserid, {
        startDate: analysisStartDate,
        endDate: analysisEndDate,
        page: 1,
        pageSize: 50,
        sort: 'msg_time',
        order: 'desc'
      }),
      fetchResponseGroups(analysisUserid, {
        startDate: analysisStartDate,
        endDate: analysisEndDate,
        page: 1,
        pageSize: 50,
        sort: analysisResponseSort,
        order: analysisResponseOrder
      })
    ]).then(([summary, questionsPage, responsePage]) => {
      setAnalysisSummary(summary);
      setAnalysisQuestions(questionsPage);
      setAnalysisResponseGroups(responsePage);
    });
  }, [
    analysisConversationType,
    analysisEndDate,
    analysisResponseOrder,
    analysisResponseSort,
    analysisStartDate,
    analysisUserid,
    productView
  ]);

  useEffect(() => {
    if (productView !== 'analysisGroup') return;
    fetchAnalysisCustomerChats({
      observerUserid: analysisUserid,
      page: 1,
      pageSize: 50
    }).then((page) => {
      setCustomerChats(page);
      setSelectedAnalysisRoomid((current) => current || page.items[0]?.roomid || '');
    });
  }, [analysisUserid, productView]);

  useEffect(() => {
    if (productView !== 'analysisGroup' || !selectedAnalysisRoomid) return;
    Promise.all([
      fetchCustomerChatSummary(analysisUserid, selectedAnalysisRoomid, {
        startDate: analysisStartDate,
        endDate: analysisEndDate
      }),
      fetchAnalysisQuestions(
        'customerChat',
        selectedAnalysisRoomid,
        {
          startDate: analysisStartDate,
          endDate: analysisEndDate,
          page: 1,
          pageSize: 50,
          sort: 'msg_time',
          order: 'desc'
        },
        analysisUserid
      )
    ]).then(([summary, questionsPage]) => {
      setGroupSummary(summary);
      setGroupQuestions(questionsPage);
    });
  }, [analysisEndDate, analysisStartDate, analysisUserid, productView, selectedAnalysisRoomid]);

  useEffect(() => {
    const requestId = conversationRequestRef.current + 1;
    conversationRequestRef.current = requestId;
    if (!selectedEmployee) {
      setConversations([]);
      setSelectedConversation(null);
      setMessages([]);
      setMessageNextCursor(null);
      setConversationNextCursor(null);
      return;
    }
    setConversations([]);
    setSelectedConversation(null);
    setMessages([]);
    setMessageNextCursor(null);
    setConversationNextCursor(null);
    setLoadingMoreConversations(false);
    fetchConversations(selectedEmployee.userid, apiConversationType(conversationFilter)).then((page) => {
      if (conversationRequestRef.current !== requestId) return;
      const normalizedPage = normalizeConversationPage(page);
      const items = normalizedPage.items;
      setConversations(items);
      setConversationNextCursor(normalizedPage.next_cursor ?? null);
      setSelectedConversation((current) => {
        if (!current) return items[0] ?? null;
        return items.find((item) => conversationKey(item) === conversationKey(current)) ?? items[0] ?? null;
      });
    });
  }, [selectedEmployee, conversationFilter]);

  useEffect(() => {
    const requestId = messageRequestRef.current + 1;
    messageRequestRef.current = requestId;
    if (!selectedEmployee || !selectedConversation) {
      setMessages([]);
      setMessageNextCursor(null);
      return;
    }
    setMessages([]);
    setMessageNextCursor(null);
    fetchMessages(selectedEmployee.userid, selectedConversation).then((page) => {
      if (messageRequestRef.current !== requestId) return;
      const normalizedPage = normalizeMessagePage(page);
      setMessages(normalizedPage.items);
      setMessageNextCursor(normalizedPage.next_cursor ?? null);
    });
  }, [selectedEmployee, selectedConversation]);

  useEffect(() => {
    if (!selectedEmployee || !selectedConversation) return;
    if (!messages.some((message) => message.content.attachment?.download_status === 'downloading')) return;
    const timer = window.setTimeout(() => {
      const requestId = messageRequestRef.current;
      fetchMessages(selectedEmployee.userid, selectedConversation).then((page) => {
        if (messageRequestRef.current !== requestId) return;
        const normalizedPage = normalizeMessagePage(page);
        setMessages(normalizedPage.items);
        setMessageNextCursor(normalizedPage.next_cursor ?? null);
      });
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [messages, selectedConversation, selectedEmployee]);

  const filteredEmployees = useMemo(() => {
    const query = employeeKeyword.trim().toLowerCase();
    return employees.filter((employee) =>
      `${employee.name}${employee.userid}${employee.department ?? ''}`.toLowerCase().includes(query)
    );
  }, [employees, employeeKeyword]);

  const filteredDirectoryEmployees = useMemo(() => {
    const query = directoryKeyword.trim().toLowerCase();
    return directoryEmployees.filter((employee) =>
      `${employee.name}${employee.userid}${employee.department ?? ''}`.toLowerCase().includes(query)
    );
  }, [directoryEmployees, directoryKeyword]);

  const groupedDirectoryEmployees = useMemo(() => {
    const groups = new Map<string, DirectoryEmployee[]>();
    filteredDirectoryEmployees.forEach((employee) => {
      const key = employee.department || '未分组';
      groups.set(key, [...(groups.get(key) || []), employee]);
    });
    return [...groups.entries()];
  }, [filteredDirectoryEmployees]);

  const filteredConversations = useMemo(() => {
    const query = conversationKeyword.trim().toLowerCase();
    return conversations.filter((conversation) => {
      const matchesType =
        conversationFilter === 'all' || uiConversationType(conversation.conversation_type) === conversationFilter;
      const text = `${conversation.display_name}${conversation.wechat_name ?? ''}${conversation.summary ?? ''}${conversation.owner_name ?? ''}`.toLowerCase();
      return matchesType && text.includes(query);
    });
  }, [conversationFilter, conversationKeyword, conversations]);

  const searchableSenders = useMemo(() => {
    return [...new Map(messages.map((message) => [message.sender.id, message.sender.display_name || message.sender.id])).entries()];
  }, [messages]);

  const searchResults = useMemo(() => {
    const query = messageQuery.trim().toLowerCase();
    const from = messageFrom ? new Date(messageFrom).getTime() : null;
    const to = messageTo ? new Date(messageTo).getTime() : null;
    if (from && to && from > to) return [];
    return messages.filter((message) => {
      const time = new Date(message.msg_time).getTime();
      return (
        (!query || `${message.sender.display_name ?? ''}${messageText(message)}`.toLowerCase().includes(query)) &&
        (!messageSender || message.sender.id === messageSender) &&
        (!from || time >= from) &&
        (!to || time <= to)
      );
    });
  }, [messageFrom, messageQuery, messageSender, messageTo, messages]);

  const openArchive = () => {
    setProductView('archive');
    setDetailOpen(false);
    setMessageSearchOpen(false);
  };

  const openConfig = () => {
    setProductView('config');
    setDetailOpen(false);
    setMessageSearchOpen(false);
    setConfigStatus('请选择左侧员工后添加，或在右侧选择员工后移出。');
  };

  const openAnalysisEmployee = () => {
    setProductView('analysisEmployee');
    setDetailOpen(false);
    setMessageSearchOpen(false);
  };

  const openAnalysisGroup = () => {
    setProductView('analysisGroup');
    setDetailOpen(false);
    setMessageSearchOpen(false);
  };

  const toggleDirectorySelection = (employee: DirectoryEmployee) => {
    if (employee.scope_status === 'enabled') {
      setConfigStatus('该员工已在观测范围内，无需重复添加。');
      return;
    }
    setSelectedDirectoryUserids((current) => {
      const next = new Set(current);
      if (next.has(employee.userid)) next.delete(employee.userid);
      else next.add(employee.userid);
      setConfigStatus(next.size ? `已选择 ${next.size} 个通讯录账号，可添加到观测范围。` : '请选择左侧员工后添加，或在右侧选择员工后移出。');
      return next;
    });
  };

  const refreshMessages = () => {
    if (!selectedEmployee || !selectedConversation) return Promise.resolve([]);
    const requestId = messageRequestRef.current;
    return fetchMessages(selectedEmployee.userid, selectedConversation).then((page) => {
      if (messageRequestRef.current !== requestId) return messages;
      const normalizedPage = normalizeMessagePage(page);
      setMessages(normalizedPage.items);
      setMessageNextCursor(normalizedPage.next_cursor ?? null);
      return normalizedPage.items;
    });
  };

  const loadOlderMessages = async () => {
    if (!selectedEmployee || !selectedConversation || !messageNextCursor || loadingOlderMessages) return;
    const requestId = messageRequestRef.current;
    setLoadingOlderMessages(true);
    try {
      const page = normalizeMessagePage(
        await fetchMessages(selectedEmployee.userid, selectedConversation, messageNextCursor)
      );
      if (messageRequestRef.current !== requestId) return;
      setMessages((current) => [...page.items, ...current]);
      setMessageNextCursor(page.next_cursor ?? null);
    } finally {
      if (messageRequestRef.current === requestId) setLoadingOlderMessages(false);
    }
  };

  const handleMessageScroll = (event: UIEvent<HTMLDivElement>) => {
    if (event.currentTarget.scrollTop <= 8) {
      void loadOlderMessages();
    }
  };

  const loadMoreConversations = async () => {
    if (!selectedEmployee || !conversationNextCursor || loadingMoreConversations) return;
    const requestId = conversationRequestRef.current;
    setLoadingMoreConversations(true);
    try {
      const page = normalizeConversationPage(
        await fetchConversations(
          selectedEmployee.userid,
          apiConversationType(conversationFilter),
          conversationNextCursor
        )
      );
      if (conversationRequestRef.current !== requestId) return;
      setConversations((current) => {
        const existingKeys = new Set(current.map(conversationKey));
        return [
          ...current,
          ...page.items.filter((conversation) => !existingKeys.has(conversationKey(conversation)))
        ];
      });
      setConversationNextCursor(page.next_cursor ?? null);
    } finally {
      if (conversationRequestRef.current === requestId) setLoadingMoreConversations(false);
    }
  };

  const handleConversationScroll = (event: UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    if (target.scrollTop + target.clientHeight >= target.scrollHeight - 8) {
      void loadMoreConversations();
    }
  };

  const handleAttachmentDownload = async (message: Message) => {
    const attachment = message.content.attachment;
    if (!attachment || triggeringAttachmentIds.has(attachment.attachment_id)) return;
    setTriggeringAttachmentIds((current) => new Set(current).add(attachment.attachment_id));
    setMessages((current) =>
      current.map((item) =>
        item.msgid === message.msgid
          ? {
              ...item,
              content: {
                ...item.content,
                attachment: { ...attachment, download_status: 'downloading', download_error: null }
              }
            }
          : item
      )
    );
    try {
      await triggerAttachmentDownload(attachment.attachment_id);
      await refreshMessages();
    } finally {
      setTriggeringAttachmentIds((current) => {
        const next = new Set(current);
        next.delete(attachment.attachment_id);
        return next;
      });
    }
  };

  const toggleObservedSelection = (employee: Employee) => {
    setSelectedObservedUserids((current) => {
      const next = new Set(current);
      if (next.has(employee.userid)) next.delete(employee.userid);
      else next.add(employee.userid);
      setConfigStatus(next.size ? `已选择 ${next.size} 个已观测账号，可从观测范围移出。` : '请选择左侧员工后添加，或在右侧选择员工后移出。');
      return next;
    });
  };

  const addObserved = async () => {
    const userids = [...selectedDirectoryUserids];
    if (!userids.length) return;
    await Promise.all(userids.map((userid) => updateObservableEmployee(userid, 'enabled')));
    setSelectedDirectoryUserids(new Set());
    setConfigStatus(`已添加 ${userids.length} 个员工账号到观测范围。`);
    loadEmployees();
  };

  const removeObserved = async () => {
    const userids = [...selectedObservedUserids];
    if (!userids.length) return;
    await Promise.all(userids.map((userid) => updateObservableEmployee(userid, 'disabled')));
    setSelectedObservedUserids(new Set());
    setConfigStatus(`已移出 ${userids.length} 个观测员工账号。`);
    loadEmployees();
  };

  const closeDrawers = () => {
    setDetailOpen(false);
    setMessageSearchOpen(false);
  };

  const openMessageSearch = () => {
    setDetailOpen(false);
    setMessageSearchOpen(true);
  };

  const openDetail = () => {
    setMessageSearchOpen(false);
    setDetailOpen(true);
  };

  const timeRangeInvalid =
    Boolean(messageFrom && messageTo) && new Date(messageFrom).getTime() > new Date(messageTo).getTime();

  const analysisEmployeeOptions = useMemo(() => {
    const map = new Map<string, { userid: string; name: string; department?: string }>();
    map.set(defaultAnalysisUserid, { userid: defaultAnalysisUserid, name: '小海燕', department: '教学运营' });
    employees.forEach((employee) => map.set(employee.userid, employee));
    return [...map.values()];
  }, [employees]);

  const selectedGroupSummary = customerChats.items.find((item) => item.roomid === selectedAnalysisRoomid);

  const renderAnalysisFilters = (mode: 'employee' | 'group') => (
    <div className="analysis-filter-bar">
      <label className="field">
        <span>观测员工账号</span>
        <select value={analysisUserid} onChange={(event) => setAnalysisUserid(event.target.value)}>
          {analysisEmployeeOptions.map((employee) => (
            <option value={employee.userid} key={employee.userid}>
              {employee.userid} · {employee.name} · {employee.department || '未配置部门'}
            </option>
          ))}
        </select>
      </label>
      {mode === 'group' ? (
        <label className="field">
          <span>企业微信群</span>
          <select value={selectedAnalysisRoomid} onChange={(event) => setSelectedAnalysisRoomid(event.target.value)}>
            {customerChats.items.map((chat) => (
              <option value={chat.roomid} key={chat.roomid}>
                {chat.room_name} · {chat.member_count ?? '—'} 人
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="field">
          <span>会话类型</span>
          <select
            value={analysisConversationType}
            onChange={(event) => setAnalysisConversationType(event.target.value as 'all' | 'single' | 'room')}
          >
            <option value="all">全部</option>
            <option value="single">私聊</option>
            <option value="room">群聊</option>
          </select>
        </label>
      )}
      <label className="field">
        <span>开始日期</span>
        <input
          min="2026-07-20"
          type="date"
          value={analysisStartDate}
          onChange={(event) => setAnalysisStartDate(event.target.value)}
        />
      </label>
      <label className="field">
        <span>结束日期</span>
        <input
          min="2026-07-20"
          type="date"
          value={analysisEndDate}
          onChange={(event) => setAnalysisEndDate(event.target.value)}
        />
      </label>
      <button className="btn btn-primary" type="button">刷新</button>
    </div>
  );

  const renderQuestionTable = (page: PagedResult<AnalysisQuestion>) => (
    <div className="analysis-table-wrap">
      <table>
        <thead>
          <tr>
            <th>问题原文</th>
            <th>问题类型</th>
            <th>提问用户</th>
            <th>所在群名称</th>
            <th>消息发送时间</th>
          </tr>
        </thead>
        <tbody>
          {page.items.length ? (
            page.items.map((item) => (
              <tr key={item.id}>
                <td>{item.content_text}</td>
                <td><span className="tag">{item.question_category_name}</span></td>
                <td>{item.sender_display_name}</td>
                <td>{item.room_name}</td>
                <td className="mono">{item.msg_time || '—'}</td>
              </tr>
            ))
          ) : (
            <tr><td colSpan={5}>暂无问题明细</td></tr>
          )}
        </tbody>
      </table>
      <div className="pagination">50 条/页 · 共 {page.total} 条</div>
    </div>
  );

  const renderSummaryPanels = (summary: AnalysisSummary, questionsPage: PagedResult<AnalysisQuestion>) => {
    const sentiment = summary.sentiment_summary;
    const sentimentTotal = Math.max(1, sentiment.total_count);
    return (
      <>
        <section className="analysis-metric-grid">
          <MetricCard label="私聊消息总数" value={summary.overview.single_message_count} />
          <MetricCard label="群聊消息总数" value={summary.overview.room_message_count} />
          <MetricCard label="收到消息总数" value={summary.overview.received_message_count} />
          <MetricCard label="员工发送总数" value={summary.overview.sent_message_count} />
          <MetricCard label="已分类问题数" value={summary.overview.question_count} />
          <MetricCard label="平均响应时长" value={formatSeconds(summary.overview.avg_response_seconds)} />
        </section>

        <section className="analysis-panel">
          <div className="analysis-panel-head">
            <div>
              <h3>收发消息趋势</h3>
              <p>按 UTC+8 日期展示收到与发送消息。</p>
            </div>
          </div>
          <div className="analysis-chart-grid">
            <div className="analysis-chart-box">
              <MiniLine values={summary.message_trend.map((item) => item.received_count + item.sent_count)} />
              <div className="analysis-chart-caption">日期趋势 · {summary.message_trend.map((item) => item.analysis_date).join(' / ') || '暂无数据'}</div>
            </div>
            <div className="analysis-chart-box">
              <Bars
                items={summary.message_type_distribution.map((item) => ({
                  label: item.msg_type,
                  value: item.received_count + item.sent_count
                }))}
              />
            </div>
          </div>
        </section>

        <section className="analysis-panel">
          <div className="analysis-panel-head">
            <div>
              <h3>群聊舆情与热词</h3>
              <p>仅统计群内外部联系人文本消息。</p>
            </div>
            <span className="badge">覆盖 {sentiment.covered_room_count} 个群</span>
          </div>
          <div className="analysis-chart-grid">
            <div className="analysis-donut">
              <strong>{Math.round((sentiment.negative_count / sentimentTotal) * 100)}%</strong>
              <span>负向占比</span>
              <p>正向 {sentiment.positive_count} · 中性 {sentiment.neutral_count} · 负向 {sentiment.negative_count}</p>
            </div>
            <div className="analysis-hotwords">
              {summary.hotwords.length ? summary.hotwords.map((item) => (
                <span style={{ fontSize: `${13 + Math.min(16, item.count * 2)}px` }} key={item.word}>{item.word}</span>
              )) : <span>暂无热词</span>}
            </div>
          </div>
        </section>

        <section className="analysis-panel">
          <div className="analysis-panel-head">
            <div>
              <h3>群内问题分类</h3>
              <p>只展示模型判断为问题且已分类的消息。</p>
            </div>
            <select aria-label="问题类型筛选">
              <option value="">全部问题类型</option>
              {questionCategories.map((item) => (
                <option value={item.code} key={item.code}>{item.display_name}</option>
              ))}
            </select>
          </div>
          <Bars items={summary.question_category_stats.map((item) => ({ label: item.display_name, value: item.count }))} />
          {renderQuestionTable(questionsPage)}
        </section>
      </>
    );
  };

  const renderEmployeeAnalysis = () => (
    <section className="analysis-view">
      <div className="analysis-page-head">
        <div>
          <p className="section-title">数据统计</p>
          <h2>观测员工账号汇总</h2>
          <p>按观测员工账号和日期范围汇总私聊、群聊、舆情、问题分类与响应时长。</p>
        </div>
        <span className="scope-pill"><span className="dot" />统计日期按 UTC+8 归属</span>
      </div>
      {renderAnalysisFilters('employee')}
      {renderSummaryPanels(analysisSummary, analysisQuestions)}
      <section className="analysis-panel">
        <div className="analysis-panel-head">
          <div>
            <h3>响应时间统计</h3>
            <p>按日期展示精确响应样本的平均值、中位数和四分位数。</p>
          </div>
          <button
            className="btn"
            type="button"
            onClick={() => {
              setAnalysisResponseSort('median');
              setAnalysisResponseOrder('desc');
            }}
          >
            按中位数排序
          </button>
        </div>
        <div className="analysis-response-strip">
          {analysisSummary.response_daily_stats.map((item) => (
            <span key={item.analysis_date}>
              {item.analysis_date} · 中位 {formatSeconds(item.median_seconds)} · 样本 {item.sample_count}
            </span>
          ))}
        </div>
        <div className="analysis-table-wrap">
          <table>
            <thead>
              <tr><th>日期</th><th>群名称</th><th>平均值</th><th>中位数</th><th>下四分位数</th><th>上四分位数</th><th>最大值</th><th>最小值</th><th>样本数</th></tr>
            </thead>
            <tbody>
              {analysisResponseGroups.items.map((item) => (
                <tr key={`${item.analysis_date}-${item.roomid}`}>
                  <td className="mono">{item.analysis_date}</td>
                  <td>{item.room_name}</td>
                  <td className="mono">{formatSeconds(item.avg_seconds)}</td>
                  <td className="mono">{formatSeconds(item.median_seconds)}</td>
                  <td className="mono">{formatSeconds(item.q1_seconds)}</td>
                  <td className="mono">{formatSeconds(item.q3_seconds)}</td>
                  <td className="mono">{formatSeconds(item.max_seconds)}</td>
                  <td className="mono">{formatSeconds(item.min_seconds)}</td>
                  <td className="mono">{item.sample_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">服务端排序 · 共 {analysisResponseGroups.total} 条</div>
        </div>
      </section>
    </section>
  );

  const renderGroupAnalysis = () => (
    <section className="analysis-view">
      <div className="analysis-page-head">
        <div>
          <p className="section-title">数据统计</p>
          <h2>企业微信群聊统计</h2>
          <p>按当前观测员工可见群查看单群消息活跃、舆情、热词和问题明细。</p>
        </div>
        <span className="scope-pill"><span className="dot" />仅展示可见群</span>
      </div>
      {renderAnalysisFilters('group')}
      {selectedGroupSummary ? (
        <div className="notice">当前群：{selectedGroupSummary.room_name} · 群主 {selectedGroupSummary.owner_name || '—'}</div>
      ) : null}
      {renderSummaryPanels(groupSummary, groupQuestions)}
    </section>
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><Archive size={18} /></div>
          <div>
            <h1>会话存档</h1>
            <span>查看原始会话存档</span>
          </div>
        </div>
        <div className="top-actions">
          <span className="sync-pill"><span className="dot" />全局同步 09:34</span>
        </div>
      </header>

      <nav className="mobile-switcher" aria-label="移动端视图切换">
        {[
          ['scope', '员工'],
          ['list', '会话'],
          ['chat', '聊天']
        ].map(([value, label]) => (
          <button
            aria-pressed={mobileView === value}
            className={mobileView === value ? 'active' : ''}
            key={value}
            onClick={() => {
              setProductView('archive');
              setMobileView(value as MobileArchiveView);
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      <main
        className={`workspace ${
          productView === 'config'
            ? 'show-config'
            : productView === 'analysisEmployee' || productView === 'analysisGroup'
              ? 'show-analysis'
              : `show-${mobileView}`
        }`}
      >
        <aside className="side-menu" aria-label="消息存档菜单">
          <div className="menu-group">
            <span className="menu-title">功能目录</span>
            <div className="menu-parent">
              <MessageSquare size={18} />
              <span>会话消息</span>
            </div>
            <div className="menu-children">
              <button className={`menu-item ${productView === 'archive' ? 'active' : ''}`} onClick={openArchive}>
                <Archive size={17} />
                <span>消息存档</span>
              </button>
              <button className={`menu-item ${productView === 'config' ? 'active' : ''}`} onClick={openConfig}>
                <Settings size={17} />
                <span>配置观测员工账号</span>
              </button>
            </div>
          </div>
          <div className="menu-group">
            <div className="menu-parent">
              <BarChart3 size={18} />
              <span>数据统计</span>
            </div>
            <div className="menu-children">
              <button
                className={`menu-item ${productView === 'analysisEmployee' ? 'active' : ''}`}
                onClick={openAnalysisEmployee}
              >
                <BarChart3 size={17} />
                <span>观测员工账号汇总</span>
              </button>
              <button
                className={`menu-item ${productView === 'analysisGroup' ? 'active' : ''}`}
                onClick={openAnalysisGroup}
              >
                <Users size={17} />
                <span>企业微信群聊统计</span>
              </button>
            </div>
          </div>
        </aside>

        {productView === 'archive' ? (
          <>
            <aside className="rail">
              <p className="section-title">观测员工范围</p>
              <label className="search-box">
                <Search size={18} />
                <input
                  value={employeeKeyword}
                  onChange={(event) => setEmployeeKeyword(event.target.value)}
                  placeholder="员工姓名、userid、部门"
                  type="search"
                />
              </label>
              <div className="employee-list">
                {filteredEmployees.length ? (
                  filteredEmployees.map((employee) => (
                    <button
                      className={`employee-card ${employee.userid === selectedEmployee?.userid ? 'active' : ''}`}
                      key={employee.userid}
                      onClick={() => {
                        setSelectedEmployee(employee);
                        setMobileView('list');
                      }}
                    >
                      <Avatar name={employee.name} src={employee.avatar} />
                      <span className="employee-meta">
                        <strong>{employee.name}</strong>
                        <span>{employee.userid} · {employee.department || '未配置部门'}</span>
                      </span>
                      <span className="badge">{employee.conversation_count}</span>
                    </button>
                  ))
                ) : (
                  <div className="empty-state"><strong>暂无观测员工</strong><span>请到配置页添加账号</span></div>
                )}
              </div>
            </aside>

            <section className="list-pane">
              <div className="pane-head">
                <p className="section-title">当前观测员工</p>
                <h2>{selectedEmployee?.name ?? '未选择观测员工'}</h2>
                <div className="filter-row">
                  <label className="search-box">
                    <Search size={18} />
                    <input
                      value={conversationKeyword}
                      onChange={(event) => setConversationKeyword(event.target.value)}
                      placeholder="学员、群名、消息摘要"
                      type="search"
                    />
                  </label>
                  <button className="btn" onClick={() => setConversationKeyword('')}>重置</button>
                </div>
              </div>
              <div className="tabs" role="tablist" aria-label="会话类型">
                {[
                  ['all', '全部'],
                  ['student', '学员'],
                  ['group', '学员群']
                ].map(([value, label]) => (
                  <button
                    className={`tab ${conversationFilter === value ? 'active' : ''}`}
                    key={value}
                    onClick={() => setConversationFilter(value as ConversationFilter)}
                    role="tab"
                    aria-selected={conversationFilter === value}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="conversation-list" onScroll={handleConversationScroll}>
                {filteredConversations.length ? (
                  <>
                    {filteredConversations.map((conversation) => {
                      const type = uiConversationType(conversation.conversation_type);
                      return (
                        <button
                          className={`conversation-item ${conversationKey(conversation) === (selectedConversation ? conversationKey(selectedConversation) : '') ? 'active' : ''}`}
                          key={conversationKey(conversation)}
                          onClick={() => {
                            setSelectedConversation(conversation);
                            setMobileView('chat');
                          }}
                        >
                          {type === 'group' ? (
                            <span className="avatar group"><Users size={18} /></span>
                          ) : (
                            <Avatar name={conversation.display_name} src={conversation.avatar} variant="customer" />
                          )}
                          <span className="conversation-meta">
                            <span className="conversation-title-line">
                              <strong>{conversation.display_name}</strong>
                              <span className="badge">{type === 'group' ? '群' : '学员'}</span>
                              <span className="conversation-sort">{conversation.sort_basis === 'last_viewed' ? '最近查看' : '最近消息'}</span>
                            </span>
                            <span>{conversation.summary || '暂无消息'}</span>
                            <span className="conversation-foot">
                              <span>最近查看：{fmt(conversation.last_viewed_at)}</span>
                              <span>最近消息：{fmt(conversation.last_message_time)}</span>
                              {type === 'group' ? (
                                <span>{conversation.member_count ?? '—'} 人 · {conversation.observer_role || '成员'} · 群主 {conversation.owner_name || '—'}</span>
                              ) : (
                                <span>微信昵称：{conversation.wechat_name || '—'}</span>
                              )}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                    {conversationNextCursor ? (
                      <button
                        className="load-more-row"
                        disabled={loadingMoreConversations}
                        onClick={loadMoreConversations}
                      >
                        {loadingMoreConversations ? '加载中' : '加载更多会话'}
                      </button>
                    ) : null}
                  </>
                ) : (
                  <div className="empty-state"><strong>没有匹配会话</strong><span>请调整会话类型或关键词</span></div>
                )}
              </div>
            </section>

            <section className="chat-pane">
              <div className="chat-head">
                <div className="chat-title">
                  <Avatar
                    name={selectedConversation?.display_name}
                    src={selectedConversation?.avatar}
                    variant="customer"
                  />
                  <div>
                    <h2>{selectedConversation?.display_name ?? '未选择会话'}</h2>
                    <p className="muted">
                      {selectedConversation
                        ? `${uiConversationType(selectedConversation.conversation_type) === 'group' ? '学员群' : '学员单聊'} · 当前抽屉仅搜本会话`
                        : '请选择左侧会话'}
                    </p>
                  </div>
                </div>
                <div className="chat-tools">
                  <button className="btn btn-icon" aria-label="搜索对话消息" onClick={openMessageSearch}>
                    <Search size={18} />
                  </button>
                  <button className="btn btn-icon" aria-label="打开会话详情" onClick={openDetail}>
                    <CircleHelp size={18} />
                  </button>
                </div>
              </div>
              <div className="message-list" onScroll={handleMessageScroll}>
                {messageNextCursor ? (
                  <button className="load-more-row" disabled={loadingOlderMessages} onClick={loadOlderMessages}>
                    {loadingOlderMessages ? '加载中' : '查看更多历史消息'}
                  </button>
                ) : null}
                {messages.length ? (
                  messages.map((message) => {
                    const senderName = message.sender.display_name || message.sender.id;
                    const side = message.sender.id === selectedEmployee?.userid ? 'self' : 'other';
                    const attachment = message.content.attachment;
                    const imageUrl = authenticatedAssetUrl(attachment?.url);
                    const isImageAttachment = message.msg_type === 'image' && attachment?.type === 'image';
                    const isTriggering = attachment ? triggeringAttachmentIds.has(attachment.attachment_id) : false;
                    return (
                      <article className={`message ${side}`} data-message-id={message.msgid} key={message.msgid}>
                        <Avatar name={senderName} src={message.sender.avatar} />
                        <div className="bubble-wrap">
                          <span className="sender-line">{senderName}</span>
                          {message.is_recalled ? (
                            <div className="bubble">该消息已被撤回 <span className="badge status-neutral">已撤回</span></div>
                          ) : imageUrl ? (
                            <button className="bubble image-bubble image-preview-bubble" onClick={() => setImagePreview(imageUrl)}>
                              <img alt={`${senderName} 的图片消息`} src={imageUrl} />
                            </button>
                          ) : isImageAttachment && attachment.download_status === 'expired' ? (
                            <div className="bubble image-bubble image-status-bubble">
                              <Image size={18} />
                              <span>文件已过期/无法下载</span>
                            </div>
                          ) : isImageAttachment && attachment.download_status === 'downloading' ? (
                            <button className="bubble image-bubble image-status-bubble" disabled>
                              <Image size={18} /> 图片下载中
                            </button>
                          ) : isImageAttachment ? (
                            <button
                              className="bubble image-bubble image-status-bubble"
                              aria-label={attachment.download_status === 'failed' ? '重试下载图片' : '下载图片'}
                              disabled={isTriggering}
                              onClick={() => handleAttachmentDownload(message)}
                            >
                              <Image size={18} />
                              {attachment.download_status === 'failed' ? '重试下载图片' : '下载图片'}
                            </button>
                          ) : attachment ? (
                            <div className="bubble image-bubble image-status-bubble">
                              <Image size={18} /> 附件 · {attachment.download_status}
                            </div>
                          ) : !message.is_supported ? (
                            <div className="bubble">
                              <span>{message.content.text}</span>
                              <span className="unsupported-card">
                                <strong>暂不支持的 {message.msg_type} 消息</strong>
                                <span>Raw 消息已保留，当前版本不写入业务消息体。</span>
                              </span>
                            </div>
                          ) : message.content.link ? (
                            <div className="bubble link-card">
                              <strong>{message.content.link.title || '链接消息'}</strong>
                              <span>{message.content.link.description || message.content.link.url}</span>
                            </div>
                          ) : (
                            <div className="bubble">{message.content.text}</div>
                          )}
                        </div>
                      </article>
                    );
                  })
                ) : (
                  <div className="empty-state"><strong>暂无消息</strong><span>当前会话还没有可查看的存档消息</span></div>
                )}
                <div className="message-end-marker" aria-hidden="true">
                  <input type="text" placeholder="到底了" disabled tabIndex={-1} />
                </div>
              </div>
            </section>
          </>
        ) : productView === 'config' ? (
          <section className="config-pane">
            <div className="config-head">
              <div className="config-title">
                <p className="section-title">企业通讯录</p>
                <h2>配置观测员工账号</h2>
                <p>从企业通讯录按部门选择需要纳入消息存档观测的员工账号。该范围只控制前端查看入口，不影响底层通讯录、客户、客户群和消息的全量同步。</p>
              </div>
              <span className="scope-pill"><span className="dot" />{employees.length} 个账号已观测</span>
            </div>
            <div className="config-body">
              <section className="transfer-panel" aria-label="企业通讯录员工">
                <div className="transfer-head">
                  <h3>企业通讯录</h3>
                  <p>按部门树形图选择员工，支持姓名、userid、部门搜索。</p>
                </div>
                <div className="transfer-tools">
                  <label className="search-box">
                    <Search size={18} />
                    <input
                      value={directoryKeyword}
                      onChange={(event: ChangeEvent<HTMLInputElement>) => setDirectoryKeyword(event.target.value)}
                      placeholder="搜索员工姓名、userid、部门"
                      type="search"
                    />
                  </label>
                </div>
                <div className="directory-list directory-tree" role="tree" aria-label="企业通讯录部门与员工">
                  {groupedDirectoryEmployees.length ? (
                    groupedDirectoryEmployees.map(([department, rows]) => (
                      <details className="department tree-folder" key={department} open>
                        <summary>
                          <ChevronRight size={15} />
                          <Folder size={15} />
                          <span>{department}</span>
                          <span className="tree-count">{rows.length}</span>
                        </summary>
                        <div className="tree-branch">
                          {rows.map((employee) => {
                            const selected = selectedDirectoryUserids.has(employee.userid);
                            const observed = employee.scope_status === 'enabled';
                            return (
                              <button
                                aria-disabled={observed}
                                aria-pressed={selected}
                                className="directory-employee tree-leaf"
                                key={employee.userid}
                                onClick={() => toggleDirectorySelection(employee)}
                              >
                                <Avatar name={employee.name} src={employee.avatar} />
                                <span className="employee-meta">
                                  <strong>{employee.name}</strong>
                                  <span>{employee.userid} · {employee.department || '未配置部门'}</span>
                                </span>
                                <span className={observed ? 'badge badge-success' : 'employee-check'}>
                                  {observed ? '已观测' : <Check size={14} />}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </details>
                    ))
                  ) : (
                    <div className="empty-state"><strong>没有匹配员工</strong><span>换一个姓名、userid 或部门关键词</span></div>
                  )}
                </div>
              </section>

              <div className="transfer-actions" aria-label="穿梭框操作">
                <button className="btn btn-primary" disabled={!selectedDirectoryUserids.size} onClick={addObserved}>添加</button>
                <button className="btn" disabled={!selectedObservedUserids.size} onClick={removeObserved}>移出</button>
              </div>

              <section className="transfer-panel" aria-label="已观测员工">
                <div className="transfer-head">
                  <h3>已观测员工</h3>
                  <p>启用账号会出现在消息查看主流程；停用只收起前端入口，不删除已同步数据。</p>
                </div>
                <div className="transfer-tools">
                  <span className="badge">{selectedDirectoryUserids.size + selectedObservedUserids.size ? `已选择 ${selectedDirectoryUserids.size + selectedObservedUserids.size} 个账号` : '未选择'}</span>
                  <div className="status-row" aria-live="polite">{configStatus}</div>
                </div>
                <div className="selected-list">
                  {employees.length ? (
                    employees.map((employee) => (
                      <button
                        aria-pressed={selectedObservedUserids.has(employee.userid)}
                        className="selected-employee"
                        key={employee.userid}
                        onClick={() => toggleObservedSelection(employee)}
                      >
                        <Avatar name={employee.name} src={employee.avatar} />
                        <span className="employee-meta">
                          <strong>{employee.name}</strong>
                          <span>{employee.userid} · {employee.department || '未配置部门'}</span>
                        </span>
                        <span className="employee-check"><Check size={14} /></span>
                      </button>
                    ))
                  ) : (
                    <div className="empty-state"><strong>暂无观测员工</strong><span>右侧为空时，消息存档不会显示员工入口</span></div>
                  )}
                </div>
              </section>
            </div>
          </section>
        ) : productView === 'analysisEmployee' ? (
          renderEmployeeAnalysis()
        ) : (
          renderGroupAnalysis()
        )}

        <aside
          aria-hidden={!detailOpen}
          aria-label={`${selectedConversation?.display_name ?? '会话'}详情`}
          className={`detail-pane ${detailOpen ? 'open' : ''}`}
          hidden={!detailOpen}
          role="dialog"
          tabIndex={-1}
        >
          <div className="detail-head">
            <div className="detail-identity">
              <Avatar
                name={selectedConversation?.display_name}
                src={selectedConversation?.avatar}
                variant="customer"
              />
              <div className="detail-meta">
                <h2>{selectedConversation?.display_name ?? '会话详情'}</h2>
                <span>{selectedConversation?.conversation_type === 'customer_chat' ? 'chat_id · 学员群信息' : 'external_userid · 学员单聊'}</span>
              </div>
            </div>
            <button className="btn btn-icon" aria-label="关闭会话详情" onClick={() => setDetailOpen(false)}>×</button>
          </div>
          <div className="detail-body">
            <div className="info-block">
              <h3>{selectedConversation?.conversation_type === 'customer_chat' ? '群信息' : '学员信息'}</h3>
              <div className="kv"><span>展示名</span><strong>{selectedConversation?.display_name ?? '—'}</strong></div>
              <div className="kv"><span>微信昵称</span><strong>{selectedConversation?.wechat_name ?? '—'}</strong></div>
              <div className="kv"><span>成员数</span><strong>{selectedConversation?.member_count ?? '—'}</strong></div>
              <div className="kv"><span>群主</span><strong>{selectedConversation?.owner_name ?? '—'}</strong></div>
            </div>
            <div className="info-block">
              <h3>查看上下文</h3>
              <div className="kv"><span>观测员工</span><strong>{selectedEmployee?.name ?? '—'}</strong></div>
              <div className="kv"><span>排序依据</span><strong>{selectedConversation?.sort_basis === 'last_viewed' ? '最近查看' : '最近消息'} · 最近查看 {fmt(selectedConversation?.last_viewed_at)} · 最近消息 {fmt(selectedConversation?.last_message_time)}</strong></div>
              <div className="kv"><span>搜索边界</span><strong>仅当前会话内消息，不跨员工或会话</strong></div>
            </div>
          </div>
        </aside>

        <aside
          aria-hidden={!messageSearchOpen}
          aria-label="搜索对话消息"
          className={`message-search-pane ${messageSearchOpen ? 'open' : ''}`}
          hidden={!messageSearchOpen}
          role="dialog"
          tabIndex={-1}
        >
          <div className="search-drawer-head">
            <div>
              <h2>搜索对话消息</h2>
              <p className="muted">{selectedConversation?.display_name ?? '当前会话'} · 文本 / 发送人 / 时间范围</p>
            </div>
            <button className="btn btn-icon" aria-label="关闭消息搜索" onClick={() => setMessageSearchOpen(false)}>×</button>
          </div>
          <div className="search-drawer-form">
            <div className="search-form-grid">
              <label className="search-field">
                <span>文本内容</span>
                <input value={messageQuery} onChange={(event) => setMessageQuery(event.target.value)} placeholder="输入消息正文、图片说明或链接标题" type="search" />
              </label>
              <label className="search-field">
                <span>发送消息的用户</span>
                <select value={messageSender} onChange={(event) => setMessageSender(event.target.value)}>
                  <option value="">全部用户</option>
                  {searchableSenders.map(([senderId, senderName]) => (
                    <option value={senderId} key={senderId}>{senderName}</option>
                  ))}
                </select>
              </label>
              <label className="search-field">
                <span>开始时间</span>
                <input value={messageFrom} onChange={(event) => setMessageFrom(event.target.value)} type="datetime-local" />
              </label>
              <label className="search-field">
                <span>结束时间</span>
                <input value={messageTo} onChange={(event) => setMessageTo(event.target.value)} type="datetime-local" />
              </label>
            </div>
            <div className="search-actions">
              <span className="muted">只在当前已打开会话内检索，不跨员工或会话。</span>
              <button className="btn" onClick={() => {
                setMessageQuery('');
                setMessageSender('');
                setMessageFrom('');
                setMessageTo('');
              }}>
                清空
              </button>
            </div>
          </div>
          <div className="search-results-shell">
            <div className="search-results-head">
              <span className="search-results-title">检索结果</span>
              <span className="status-row">{timeRangeInvalid ? '开始时间不能晚于结束时间。' : `找到 ${searchResults.length} 条消息`}</span>
            </div>
            <div className="message-search-results">
              {timeRangeInvalid ? (
                <div className="empty-state"><strong>时间范围无效</strong><span>请重新选择开始和结束时间</span></div>
              ) : searchResults.length ? (
                searchResults.map((message) => (
                  <button className="message-result" key={message.msgid} onClick={() => setMessageSearchOpen(false)}>
                    <Avatar name={message.sender.display_name || message.sender.id} src={message.sender.avatar} />
                    <span className="result-main">
                      <span className="result-meta"><strong>{message.sender.display_name || message.sender.id}</strong><span>{fmt(message.msg_time)}</span></span>
                      <span className="result-text">{messageText(message)}</span>
                    </span>
                  </button>
                ))
              ) : (
                <div className="empty-state"><strong>没有匹配消息</strong><span>请调整文本、发送人或时间范围</span></div>
              )}
            </div>
          </div>
        </aside>
      </main>

      <div className={`drawer-backdrop ${detailOpen || messageSearchOpen ? 'open' : ''}`} onClick={closeDrawers} />

      <div className={`modal ${imagePreview ? 'open' : ''}`} aria-hidden={!imagePreview} hidden={!imagePreview} role="dialog" aria-label="图片消息预览">
        <div className="modal-card">
          <div className="modal-head">
            <h2>图片消息预览</h2>
            <button className="btn" onClick={() => setImagePreview(null)}>关闭</button>
          </div>
          <div className="modal-visual">
            {imagePreview ? <img alt="图片消息预览" src={imagePreview} /> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
