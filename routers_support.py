from datetime import datetime
from flask import Blueprint, request, jsonify, g

import models
from auth import require_auth
from support_ai import ask_support_ai

support_bp = Blueprint("support", __name__, url_prefix="/api/support")

# Phrases signaling the user explicitly wants a human — escalate immediately,
# no need to ask for confirmation since they already decided.
HUMAN_REQUEST_PHRASES = [
    "talk to human", "talk to a human", "human support", "real person",
    "speak to someone", "speak to an agent", "human agent", "talk to agent",
]

# Categories/phrases that require immediate escalation per spec — these skip
# the "do you want human help?" confirmation step entirely.
IMMEDIATE_ESCALATION_PHRASES = {
    "account_access": ["locked out", "can't log in", "cannot log in", "account locked",
                        "account access", "reset my account", "account hacked"],
    "security": ["hacked", "security concern", "someone accessed my account",
                 "suspicious login", "phishing", "scammed", "fraud"],
    "moderation": ["report a user", "reported me", "unfair suspension", "wrongly suspended",
                   "moderation", "appeal my suspension", "appeal suspension"],
    "dispute": ["dispute", "this decision is wrong", "automated decision", "unfair decision"],
}

CATEGORY_LABELS = {
    "account_access": "Account Access",
    "security": "Security",
    "moderation": "Report & Moderation",
    "dispute": "Dispute",
    "technical": "Technical Issue",
    "general": "General",
}


def _detect_immediate_category(text):
    lowered = text.lower()
    for category, phrases in IMMEDIATE_ESCALATION_PHRASES.items():
        for phrase in phrases:
            if phrase in lowered:
                return category
    return None


def _wants_human(text):
    lowered = text.lower()
    return any(phrase in lowered for phrase in HUMAN_REQUEST_PHRASES)


def _get_or_create_conversation(db, user):
    convo = (
        db.query(models.SupportConversation)
        .filter(models.SupportConversation.user_id == user.id)
        .filter(models.SupportConversation.status != "resolved")
        .order_by(models.SupportConversation.created_at.desc())
        .first()
    )
    if convo:
        return convo
    convo = models.SupportConversation(user_id=user.id, status="ai")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


def _save_message(db, conversation_id, sender_type, content):
    msg = models.SupportMessage(conversation_id=conversation_id, sender_type=sender_type, content=content)
    db.add(msg)
    db.commit()
    return msg


def _conversation_history_text(db, conversation_id, limit=10):
    msgs = (
        db.query(models.SupportMessage)
        .filter(models.SupportMessage.conversation_id == conversation_id)
        .order_by(models.SupportMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    msgs.reverse()
    lines = []
    for m in msgs:
        label = {"user": "User", "ai": "CREET Support (AI)", "agent": "CREET Support (Human)", "system": "System"}.get(m.sender_type, m.sender_type)
        lines.append(f"{label}: {m.content}")
    return "\n".join(lines)


def _search_knowledge_base(db, query, limit=4):
    like = f"%{query}%"
    words = [w for w in query.lower().split() if len(w) > 3][:5]
    articles = db.query(models.KnowledgeArticle).all()
    if not articles:
        return []
    scored = []
    for a in articles:
        text = (a.title + " " + a.content).lower()
        score = sum(1 for w in words if w in text)
        if score > 0:
            scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:limit]]


def _build_kb_context(articles):
    if not articles:
        return "No matching knowledge base articles found."
    parts = []
    for a in articles:
        parts.append(f"[{a.category}] {a.title}\n{a.content}")
    return "\n\n".join(parts)


def _create_ticket(db, user, conversation, category, subject, original_message):
    history = _conversation_history_text(db, conversation.id, limit=20)
    summary, _ = ask_support_ai(
        f"Summarize this support conversation in 1-2 sentences for a human agent:\n{history}",
        "N/A", ""
    )
    ticket = models.SupportTicket(
        user_id=user.id,
        conversation_id=conversation.id,
        category=category,
        subject=subject[:255],
        status="open",
        priority="high" if category in ("security", "moderation") else "normal",
        ai_summary=summary or original_message[:500],
        troubleshooting_attempted=history,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@support_bp.get("/conversation")
@require_auth
def get_conversation():
    db = g.db
    convo = _get_or_create_conversation(db, g.current_user)
    msgs = (
        db.query(models.SupportMessage)
        .filter(models.SupportMessage.conversation_id == convo.id)
        .order_by(models.SupportMessage.created_at.asc())
        .all()
    )
    ticket = (
        db.query(models.SupportTicket)
        .filter(models.SupportTicket.conversation_id == convo.id)
        .order_by(models.SupportTicket.created_at.desc())
        .first()
    )
    return jsonify({
        "conversation_id": convo.id,
        "status": convo.status,
        "messages": [
            {"id": m.id, "sender_type": m.sender_type, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in msgs
        ],
        "ticket": {
            "id": ticket.id, "status": ticket.status, "category": ticket.category,
        } if ticket else None,
    })


@support_bp.post("/message")
@require_auth
def send_message():
    db = g.db
    user = g.current_user
    data = request.get_json(force=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"detail": "Message is required"}), 422

    convo = _get_or_create_conversation(db, user)
    _save_message(db, convo.id, "user", text)

    # Human has already taken over — no AI involvement, just store the message
    # for the agent to see. Frontend should show "waiting for agent".
    if convo.status == "human":
        return jsonify({
            "conversation_id": convo.id,
            "status": "human",
            "reply": None,
        })

    # We previously asked "do you want human help?" — interpret this reply as yes/no.
    if convo.status == "awaiting_escalation_confirm":
        if any(w in text.lower() for w in ["yes", "yeah", "sure", "please", "human", "agent"]):
            ticket = _create_ticket(db, user, convo, convo_pending_category(db, convo), "Escalated by user", text)
            convo.status = "human"
            db.commit()
            reply = "You're connected to CREET human support. A real person will respond here shortly."
            _save_message(db, convo.id, "system", reply)
            return jsonify({"conversation_id": convo.id, "status": "human", "reply": reply, "ticket_id": ticket.id})
        else:
            convo.status = "ai"
            convo.unresolved_count = 0
            db.commit()
            reply = "No problem — let's keep going. What else can I help with?"
            _save_message(db, convo.id, "ai", reply)
            return jsonify({"conversation_id": convo.id, "status": "ai", "reply": reply})

    # Explicit human request — escalate immediately, no confirmation needed.
    if _wants_human(text):
        ticket = _create_ticket(db, user, convo, "general", text[:100], text)
        convo.status = "human"
        db.commit()
        reply = "Connecting you to CREET human support — a real person will respond here shortly."
        _save_message(db, convo.id, "system", reply)
        return jsonify({"conversation_id": convo.id, "status": "human", "reply": reply, "ticket_id": ticket.id})

    # Immediate-escalation categories (security, account access, moderation, dispute) —
    # per spec, these skip the confirmation step entirely.
    immediate_category = _detect_immediate_category(text)
    if immediate_category:
        ticket = _create_ticket(db, user, convo, immediate_category, text[:100], text)
        convo.status = "human"
        db.commit()
        reply = (
            "This needs a human CREET team member to review — I've created a support "
            "ticket and connected you to human support. Someone will respond here shortly."
        )
        _save_message(db, convo.id, "system", reply)
        return jsonify({"conversation_id": convo.id, "status": "human", "reply": reply, "ticket_id": ticket.id})

    # Normal AI path: retrieve knowledge base context, ask the AI, honestly report
    # low confidence rather than guessing.
    articles = _search_knowledge_base(db, text)
    kb_context = _build_kb_context(articles)
    history_text = _conversation_history_text(db, convo.id, limit=10)

    ai_reply, confident = ask_support_ai(text, kb_context, history_text)

    if not confident or not ai_reply:
        convo.unresolved_count = (convo.unresolved_count or 0) + 1
        db.commit()

        if convo.unresolved_count >= 3:
            ticket = _create_ticket(db, user, convo, "technical", text[:100], text)
            convo.status = "human"
            db.commit()
            reply = (
                "We've tried a few things without resolving this — I've created a support "
                "ticket and connected you to human support. Someone will respond here shortly."
            )
            _save_message(db, convo.id, "system", reply)
            return jsonify({"conversation_id": convo.id, "status": "human", "reply": reply, "ticket_id": ticket.id})

        convo.status = "awaiting_escalation_confirm"
        db.commit()
        reply = (
            "I don't have enough information to answer that confidently, and I don't want "
            "to guess. Would you like me to connect you with human CREET support?"
        )
        _save_message(db, convo.id, "ai", reply)
        return jsonify({"conversation_id": convo.id, "status": "awaiting_escalation_confirm", "reply": reply})

    convo.unresolved_count = 0
    db.commit()
    _save_message(db, convo.id, "ai", ai_reply)
    return jsonify({"conversation_id": convo.id, "status": "ai", "reply": ai_reply})


def convo_pending_category(db, convo):
    # Best-effort category guess from the first user message, used only when
    # escalation happens via the confirm-step path (not an immediate category hit).
    first = (
        db.query(models.SupportMessage)
        .filter(models.SupportMessage.conversation_id == convo.id, models.SupportMessage.sender_type == "user")
        .order_by(models.SupportMessage.created_at.asc())
        .first()
    )
    return _detect_immediate_category(first.content) if first else "general" or "general"


# --- Admin: knowledge base management ---

@support_bp.get("/admin/articles")
@require_auth
def list_articles():
    from auth import require_admin
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    articles = db.query(models.KnowledgeArticle).order_by(models.KnowledgeArticle.category, models.KnowledgeArticle.title).all()
    return jsonify({
        "articles": [
            {"id": a.id, "category": a.category, "title": a.title, "content": a.content,
             "updated_at": a.updated_at.isoformat() if a.updated_at else None}
            for a in articles
        ]
    })


@support_bp.post("/admin/articles")
@require_auth
def create_article():
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    data = request.get_json(force=True) or {}
    category = (data.get("category") or "").strip()
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not category or not title or not content:
        return jsonify({"detail": "category, title, and content are required"}), 422
    article = models.KnowledgeArticle(category=category, title=title, content=content)
    db.add(article)
    db.commit()
    db.refresh(article)
    return jsonify({"id": article.id})


@support_bp.put("/admin/articles/<int:article_id>")
@require_auth
def update_article(article_id):
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    article = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == article_id).first()
    if not article:
        return jsonify({"detail": "Article not found"}), 404
    data = request.get_json(force=True) or {}
    if "category" in data:
        article.category = data["category"].strip()
    if "title" in data:
        article.title = data["title"].strip()
    if "content" in data:
        article.content = data["content"].strip()
    db.commit()
    return jsonify({"success": True})


@support_bp.delete("/admin/articles/<int:article_id>")
@require_auth
def delete_article(article_id):
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    article = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.id == article_id).first()
    if not article:
        return jsonify({"detail": "Article not found"}), 404
    db.delete(article)
    db.commit()
    return jsonify({"success": True})


# --- Admin: ticket/conversation management ---

def _ticket_to_dict(t, user, agent):
    return {
        "id": t.id,
        "user": {"id": user.id, "username": user.username, "full_name": user.full_name} if user else None,
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "assigned_agent": {"id": agent.id, "full_name": agent.full_name} if agent else None,
        "ai_summary": t.ai_summary,
        "conversation_id": t.conversation_id,
    }


@support_bp.get("/admin/tickets")
@require_auth
def list_tickets():
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    status_filter = request.args.get("status")
    query = db.query(models.SupportTicket)
    if status_filter:
        query = query.filter(models.SupportTicket.status == status_filter)
    tickets = query.order_by(models.SupportTicket.created_at.desc()).all()

    results = []
    for t in tickets:
        user = db.query(models.User).filter(models.User.id == t.user_id).first()
        agent = db.query(models.User).filter(models.User.id == t.assigned_agent_id).first() if t.assigned_agent_id else None
        results.append(_ticket_to_dict(t, user, agent))
    return jsonify({"tickets": results})


@support_bp.get("/admin/tickets/<int:ticket_id>")
@require_auth
def get_ticket_detail(ticket_id):
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    t = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not t:
        return jsonify({"detail": "Ticket not found"}), 404
    user = db.query(models.User).filter(models.User.id == t.user_id).first()
    agent = db.query(models.User).filter(models.User.id == t.assigned_agent_id).first() if t.assigned_agent_id else None

    msgs = (
        db.query(models.SupportMessage)
        .filter(models.SupportMessage.conversation_id == t.conversation_id)
        .order_by(models.SupportMessage.created_at.asc())
        .all()
    )

    data = _ticket_to_dict(t, user, agent)
    data["internal_notes"] = t.internal_notes
    data["troubleshooting_attempted"] = t.troubleshooting_attempted
    data["messages"] = [
        {"id": m.id, "sender_type": m.sender_type, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in msgs
    ]
    return jsonify(data)


@support_bp.put("/admin/tickets/<int:ticket_id>")
@require_auth
def update_ticket(ticket_id):
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    t = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not t:
        return jsonify({"detail": "Ticket not found"}), 404
    data = request.get_json(force=True) or {}

    if "status" in data:
        t.status = data["status"]
    if "priority" in data:
        t.priority = data["priority"]
    if "assigned_agent_id" in data:
        t.assigned_agent_id = data["assigned_agent_id"]
    if "internal_notes" in data:
        t.internal_notes = data["internal_notes"]

    db.commit()
    return jsonify({"success": True})


@support_bp.post("/admin/tickets/<int:ticket_id>/reply")
@require_auth
def agent_reply(ticket_id):
    if not g.current_user.is_admin:
        return jsonify({"detail": "Admin access required"}), 403
    db = g.db
    t = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not t:
        return jsonify({"detail": "Ticket not found"}), 404
    data = request.get_json(force=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"detail": "content is required"}), 422

    _save_message(db, t.conversation_id, "agent", content)

    convo = db.query(models.SupportConversation).filter(models.SupportConversation.id == t.conversation_id).first()
    if convo:
        convo.status = "human"
        db.commit()

    if t.status == "open":
        t.status = "in_progress"
        db.commit()

    return jsonify({"success": True})
