from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from wecom_app.api.deps import require_admin, require_observable_userid
from wecom_app.db.session import get_db
from wecom_app.models import (
    ConversationViewHistory,
    CustomerChat,
    CustomerChatMember,
    Employee,
    EmployeeExternalContact,
    ExternalContact,
    Message,
)
from wecom_app.schemas.archive import (
    ConversationOut,
    ConversationViewIn,
    CustomerChatDetailOut,
    MessageContentOut,
    MessageOut,
    SenderOut,
    StudentDetailOut,
)

router = APIRouter(
    prefix="/api/observed-employees/{userid}",
    dependencies=[Depends(require_admin), Depends(require_observable_userid)],
)


def _message_summary(message: Message | None) -> str | None:
    if message is None:
        return None
    if message.is_recalled:
        return "已撤回"
    if not message.is_supported:
        return f"暂不支持的 {message.msg_type} 消息"
    return message.content_text or message.link_title or f"[{message.msg_type}]"


def _latest_single_message(db: Session, userid: str, external_userid: str) -> Message | None:
    return db.scalar(
        select(Message)
        .where(
            Message.conversation_type == "single",
            or_(
                and_(Message.sender_id == userid, MessageRecipientAlias.recipient_id == external_userid),
                and_(Message.sender_id == external_userid, MessageRecipientAlias.recipient_id == userid),
            ),
        )
        .join(MessageRecipientAlias, MessageRecipientAlias.message_id == Message.id)
        .order_by(desc(Message.msg_time))
        .limit(1)
    )


from wecom_app.models import MessageRecipient as MessageRecipientAlias  # noqa: E402


@router.get("/conversations", response_model=dict)
def list_conversations(
    userid: str,
    type: str = "all",
    keyword: str = "",
    limit: int = Query(default=30, le=100),
    db: Session = Depends(get_db),
) -> dict:
    items: list[ConversationOut] = []
    if type in ("all", "student"):
        stmt = (
            select(EmployeeExternalContact, ExternalContact, ConversationViewHistory)
            .join(ExternalContact, ExternalContact.external_userid == EmployeeExternalContact.external_userid)
            .outerjoin(
                ConversationViewHistory,
                and_(
                    ConversationViewHistory.observer_userid == userid,
                    ConversationViewHistory.conversation_type == "student",
                    ConversationViewHistory.external_userid == ExternalContact.external_userid,
                ),
            )
            .where(EmployeeExternalContact.userid == userid, EmployeeExternalContact.is_deleted.is_(False))
        )
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    EmployeeExternalContact.remark.like(like),
                    ExternalContact.name.like(like),
                    ExternalContact.external_userid.like(like),
                )
            )
        for rel, contact, history in db.execute(stmt).all():
            latest = _latest_single_message(db, userid, contact.external_userid)
            items.append(
                ConversationOut(
                    conversation_type="student",
                    external_userid=contact.external_userid,
                    chat_id=None,
                    display_name=rel.remark or contact.name or contact.external_userid,
                    wechat_name=contact.name,
                    avatar=contact.avatar,
                    summary=_message_summary(latest),
                    last_message_time=latest.msg_time if latest else None,
                    last_viewed_at=history.last_viewed_at if history else None,
                    sort_basis="last_viewed" if history else "last_message",
                )
            )
    if type in ("all", "customer_chat"):
        stmt = (
            select(CustomerChat, CustomerChatMember, ConversationViewHistory)
            .join(CustomerChatMember, CustomerChatMember.chat_id == CustomerChat.chat_id)
            .outerjoin(
                ConversationViewHistory,
                and_(
                    ConversationViewHistory.observer_userid == userid,
                    ConversationViewHistory.conversation_type == "customer_chat",
                    ConversationViewHistory.chat_id == CustomerChat.chat_id,
                ),
            )
            .where(CustomerChatMember.member_userid == userid, CustomerChatMember.is_active.is_(True))
        )
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(CustomerChat.name.like(like), CustomerChat.chat_id.like(like)))
        for chat, member, history in db.execute(stmt).all():
            latest = db.scalar(
                select(Message)
                .where(Message.conversation_type == "room", Message.roomid == chat.chat_id)
                .order_by(desc(Message.msg_time))
                .limit(1)
            )
            items.append(
                ConversationOut(
                    conversation_type="customer_chat",
                    external_userid=None,
                    chat_id=chat.chat_id,
                    display_name=chat.name or chat.chat_id,
                    summary=_message_summary(latest),
                    last_message_time=latest.msg_time if latest else None,
                    last_viewed_at=history.last_viewed_at if history else None,
                    sort_basis="last_viewed" if history else "last_message",
                    member_count=chat.member_count,
                    owner_name=chat.owner_userid,
                    observer_role=member.role,
                )
            )
    items.sort(key=lambda item: item.last_viewed_at or item.last_message_time or datetime.min, reverse=True)
    return {"items": [item.model_dump() for item in items[:limit]], "next_cursor": None}


def _sender_out(db: Session, message: Message, observer_userid: str) -> SenderOut:
    display_name = message.sender_name
    avatar = None
    if message.sender_type == "employee":
        if message.roomid:
            member = db.scalar(
                select(CustomerChatMember).where(
                    CustomerChatMember.chat_id == message.roomid,
                    CustomerChatMember.member_userid == message.sender_id,
                )
            )
            if member is not None:
                display_name = member.group_nickname or member.name or display_name
        employee = db.scalar(select(Employee).where(Employee.userid == message.sender_id))
        if employee is not None:
            display_name = display_name or employee.name
            avatar = employee.avatar
    elif message.sender_type == "external_contact":
        contact = db.scalar(
            select(ExternalContact).where(ExternalContact.external_userid == message.sender_id)
        )
        relation = db.scalar(
            select(EmployeeExternalContact).where(
                EmployeeExternalContact.userid == observer_userid,
                EmployeeExternalContact.external_userid == message.sender_id,
            )
        )
        display_name = (
            (relation.remark if relation is not None else None)
            or (contact.name if contact is not None else None)
            or display_name
        )
        avatar = contact.avatar if contact is not None else None
    return SenderOut(
        id=message.sender_id,
        type=message.sender_type,
        display_name=display_name or message.sender_id,
        avatar=avatar,
    )


def _message_out(db: Session, message: Message, observer_userid: str) -> MessageOut:
    attachment = message.attachments[0] if message.attachments else None
    return MessageOut(
        message_id=message.id,
        msgid=message.msgid,
        msg_type=message.msg_type,
        is_supported=message.is_supported,
        sender=_sender_out(db, message, observer_userid),
        content=MessageContentOut(
            text=_message_summary(message),
            link=(
                {"title": message.link_title, "url": message.link_url, "description": message.link_description}
                if message.link_url
                else None
            ),
            attachment=(
                {
                    "attachment_id": attachment.id,
                    "type": attachment.attachment_type,
                    "download_status": attachment.download_status,
                    "url": (
                        f"/api/attachments/{attachment.id}/content"
                        if attachment.download_status == "downloaded"
                        else None
                    ),
                }
                if attachment
                else None
            ),
        ),
        msg_time=message.msg_time,
        is_recalled=message.is_recalled,
        recalled_at=message.recalled_at,
    )


@router.get("/student-conversations/{external_userid}/messages", response_model=dict)
def list_student_messages(userid: str, external_userid: str, limit: int = 50, db: Session = Depends(get_db)) -> dict:
    stmt = (
        select(Message)
        .join(MessageRecipientAlias, MessageRecipientAlias.message_id == Message.id)
        .where(
            Message.conversation_type == "single",
            or_(
                and_(Message.sender_id == userid, MessageRecipientAlias.recipient_id == external_userid),
                and_(Message.sender_id == external_userid, MessageRecipientAlias.recipient_id == userid),
            ),
        )
        .order_by(Message.msg_time.asc())
        .limit(limit)
    )
    return {
        "items": [
            _message_out(db, message, userid).model_dump()
            for message in db.scalars(stmt).all()
        ],
        "next_cursor": None,
    }


@router.get("/customer-chat-conversations/{chat_id}/messages", response_model=dict)
def list_chat_messages(userid: str, chat_id: str, limit: int = 50, db: Session = Depends(get_db)) -> dict:
    membership = db.scalar(
        select(CustomerChatMember).where(
            CustomerChatMember.chat_id == chat_id,
            CustomerChatMember.member_userid == userid,
            CustomerChatMember.is_active.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="not a member of this chat")
    stmt = (
        select(Message)
        .where(Message.conversation_type == "room", Message.roomid == chat_id)
        .order_by(Message.msg_time.asc())
        .limit(limit)
    )
    return {
        "items": [
            _message_out(db, message, userid).model_dump()
            for message in db.scalars(stmt).all()
        ],
        "next_cursor": None,
    }


@router.get("/conversations/{conversation_type}/{conversation_id}/message-search", response_model=dict)
def search_current_conversation(
    userid: str,
    conversation_type: str,
    conversation_id: str,
    keyword: str = "",
    sender_id: str | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Message)
    if conversation_type == "student":
        stmt = stmt.join(MessageRecipientAlias, MessageRecipientAlias.message_id == Message.id).where(
            Message.conversation_type == "single",
            or_(
                and_(Message.sender_id == userid, MessageRecipientAlias.recipient_id == conversation_id),
                and_(Message.sender_id == conversation_id, MessageRecipientAlias.recipient_id == userid),
            ),
        )
    elif conversation_type == "customer_chat":
        stmt = stmt.where(Message.conversation_type == "room", Message.roomid == conversation_id)
    else:
        raise HTTPException(status_code=422, detail="invalid conversation type")
    if keyword:
        stmt = stmt.where(Message.content_text.like(f"%{keyword}%"))
    if sender_id:
        stmt = stmt.where(Message.sender_id == sender_id)
    stmt = stmt.order_by(desc(Message.msg_time)).limit(limit)
    return {
        "items": [
            _message_out(db, message, userid).model_dump()
            for message in db.scalars(stmt).all()
        ],
        "next_cursor": None,
    }


@router.post("/conversation-view-history", response_model=dict)
def update_view_history(userid: str, payload: ConversationViewIn, db: Session = Depends(get_db)) -> dict:
    stmt = select(ConversationViewHistory).where(
        ConversationViewHistory.observer_userid == userid,
        ConversationViewHistory.conversation_type == payload.conversation_type,
    )
    if payload.conversation_type == "student":
        stmt = stmt.where(ConversationViewHistory.external_userid == payload.external_userid)
    else:
        stmt = stmt.where(ConversationViewHistory.chat_id == payload.chat_id)
    history = db.scalar(stmt)
    if history is None:
        history = ConversationViewHistory(
            observer_userid=userid,
            conversation_type=payload.conversation_type,
            external_userid=payload.external_userid,
            chat_id=payload.chat_id,
            view_count=0,
        )
        db.add(history)
    history.view_count += 1
    history.last_viewed_at = datetime.utcnow()
    db.commit()
    return {"last_viewed_at": history.last_viewed_at, "view_count": history.view_count}


@router.get("/students/{external_userid}", response_model=StudentDetailOut)
def student_detail(userid: str, external_userid: str, db: Session = Depends(get_db)) -> StudentDetailOut:
    row = db.execute(
        select(EmployeeExternalContact, ExternalContact)
        .join(ExternalContact, ExternalContact.external_userid == EmployeeExternalContact.external_userid)
        .where(EmployeeExternalContact.userid == userid, ExternalContact.external_userid == external_userid)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="student not found")
    rel, contact = row
    return StudentDetailOut(
        external_userid=contact.external_userid,
        display_name=rel.remark or contact.name or contact.external_userid,
        wechat_name=contact.name,
        avatar=contact.avatar,
        remark=rel.remark,
        description=rel.description,
        corp_name=contact.corp_name,
        gender=contact.gender,
        unionid=contact.unionid,
        related_userid=userid,
        add_time=rel.add_time,
        tag_ids=rel.tag_ids or [],
    )


@router.get("/customer-chats/{chat_id}", response_model=CustomerChatDetailOut)
def chat_detail(userid: str, chat_id: str, db: Session = Depends(get_db)) -> CustomerChatDetailOut:
    chat = db.scalar(select(CustomerChat).where(CustomerChat.chat_id == chat_id))
    if chat is None:
        raise HTTPException(status_code=404, detail="chat not found")
    members = db.scalars(select(CustomerChatMember).where(CustomerChatMember.chat_id == chat_id)).all()
    return CustomerChatDetailOut(
        chat_id=chat.chat_id,
        name=chat.name,
        owner_userid=chat.owner_userid,
        notice=chat.notice,
        member_count=chat.member_count,
        admin_userids=chat.admin_userids or [],
        status=chat.status,
        members=[
            {
                "member_userid": member.member_userid,
                "name": member.group_nickname or member.name or member.member_userid,
                "member_type": member.member_type,
                "role": member.role,
                "is_active": member.is_active,
            }
            for member in members
        ],
    )
