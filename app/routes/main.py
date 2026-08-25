from flask import Blueprint, render_template, jsonify
from sqlalchemy import func
from app.database import get_db
from app.models import Server, MiddlewareInstance, RunbookCommand, IncidentLog, AuditLog, Project
from app.models.user import User
from app.routes.auth import login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    """Vista principal con métricas, estado global y últimos accesos."""
    with get_db() as session:
        total_servers = session.query(func.count(Server.id)).scalar() or 0
        total_middlewares = session.query(func.count(MiddlewareInstance.id)).scalar() or 0
        total_runbooks = session.query(func.count(RunbookCommand.id)).scalar() or 0
        total_projects = session.query(func.count(Project.id)).scalar() or 0

        open_incidents = session.query(IncidentLog).filter(
            IncidentLog.status.in_(["OPEN", "IN_PROGRESS"])
        ).count()

        critical_incidents = session.query(IncidentLog).filter(
            IncidentLog.severity == "CRITICAL",
            IncidentLog.status.in_(["OPEN", "IN_PROGRESS"])
        ).count()

        middleware_distribution = (
            session.query(MiddlewareInstance.name, func.count(MiddlewareInstance.id))
            .group_by(MiddlewareInstance.name)
            .order_by(func.count(MiddlewareInstance.id).desc())
            .limit(5).all()
        )

        recent_incidents = (
            session.query(IncidentLog)
            .order_by(IncidentLog.occurred_at.desc())
            .limit(5).all()
        )

        recent_audits = (
            session.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(6).all()
        )

        recent_servers = (
            session.query(Server)
            .order_by(Server.created_at.desc())
            .limit(4).all()
        )

        # Últimos usuarios logueados (auditoría de LOGIN)
        recent_logins = (
            session.query(AuditLog)
            .filter(AuditLog.action == "LOGIN")
            .order_by(AuditLog.created_at.desc())
            .limit(10).all()
        )

        stats = {
            "total_servers": total_servers,
            "total_middlewares": total_middlewares,
            "total_runbooks": total_runbooks,
            "total_projects": total_projects,
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "middleware_distribution": middleware_distribution,
            "recent_incidents": recent_incidents,
            "recent_audits": recent_audits,
            "recent_servers": recent_servers,
            "recent_logins": recent_logins,
        }

        return render_template("dashboard/index.html", **stats)


@main_bp.route("/health")
def health_check():
    """Endpoint de salud para monitorización (sin autenticación)."""
    return jsonify({
        "status": "UP",
        "service": "Wiki-MDW",
        "database": "SQLite",
        "version": "2.0.0"
    })
