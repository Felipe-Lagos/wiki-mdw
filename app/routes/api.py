from flask import Blueprint, request, jsonify
from sqlalchemy import or_, func
from app.database import get_db
from app.models import Server, MiddlewareInstance, RunbookCommand, IncidentLog, Project

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.route("/search")
def global_search():
    """Búsqueda global rápida por host, IP, middleware, corta-palos o incidentes."""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": []})

    results = []
    with get_db() as session:
        # Buscar en Servidores
        servers = session.query(Server).filter(
            or_(
                Server.hostname.ilike(f"%{q}%"),
                Server.ip_address.ilike(f"%{q}%"),
                Server.os_name.ilike(f"%{q}%")
            )
        ).limit(5).all()

        for s in servers:
            results.append({
                "type": "server",
                "title": f"Servidor: {s.hostname} ({s.ip_address})",
                "subtitle": f"{s.os_name} | {s.environment}",
                "url": f"/servers/{s.id}"
            })

        # Buscar en Middlewares
        middlewares = session.query(MiddlewareInstance).filter(
            or_(
                MiddlewareInstance.name.ilike(f"%{q}%"),
                MiddlewareInstance.install_path.ilike(f"%{q}%"),
                MiddlewareInstance.domain_or_instance.ilike(f"%{q}%")
            )
        ).limit(5).all()

        for m in middlewares:
            results.append({
                "type": "middleware",
                "title": f"Middleware: {m.name} ({m.domain_or_instance or m.version})",
                "subtitle": f"En {m.server.hostname if m.server else 'N/A'} - {m.install_path}",
                "url": f"/servers/{m.server_id}"
            })

        # Buscar en Corta-Palos
        runbooks = session.query(RunbookCommand).filter(
            or_(
                RunbookCommand.title.ilike(f"%{q}%"),
                RunbookCommand.category.ilike(f"%{q}%"),
                RunbookCommand.command_text.ilike(f"%{q}%")
            )
        ).limit(5).all()

        for rb in runbooks:
            results.append({
                "type": "runbook",
                "title": f"Corta-Palos: [{rb.category}] {rb.title}",
                "subtitle": "Comando operativo",
                "url": f"/runbooks/{rb.id}"
            })

        # Buscar en Incidentes
        incidents = session.query(IncidentLog).filter(
            or_(
                IncidentLog.title.ilike(f"%{q}%"),
                IncidentLog.ticket_ref.ilike(f"%{q}%"),
                IncidentLog.description.ilike(f"%{q}%")
            )
        ).limit(5).all()

        for inc in incidents:
            results.append({
                "type": "incident",
                "title": f"Incidente: {inc.ticket_ref or '#' + str(inc.id)} - {inc.title}",
                "subtitle": f"Severidad: {inc.severity} | Estado: {inc.status}",
                "url": f"/incidents/{inc.id}"
            })

    return jsonify({"query": q, "count": len(results), "results": results})


@api_bp.route("/stats")
def get_stats():
    """Retorna métricas JSON para dashboards y componentes frontend."""
    with get_db() as session:
        servers_count = session.query(func.count(Server.id)).scalar() or 0
        middlewares_count = session.query(func.count(MiddlewareInstance.id)).scalar() or 0
        incidents_open = session.query(IncidentLog).filter(
            IncidentLog.status.in_(["OPEN", "IN_PROGRESS"])
        ).count()
        runbooks_count = session.query(func.count(RunbookCommand.id)).scalar() or 0

        return jsonify({
            "servers": servers_count,
            "middlewares": middlewares_count,
            "incidents_open": incidents_open,
            "runbooks": runbooks_count
        })
