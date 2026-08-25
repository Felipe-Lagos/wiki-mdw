import csv
import io
from datetime import datetime, timezone
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, Response
from sqlalchemy import or_
from app.database import get_db
from app.models import IncidentLog, IncidentTimelineEntry, Server, MiddlewareInstance, Project, RunbookCommand, AuditLog
from app.services.audit_service import AuditService

incidents_bp = Blueprint("incidents", __name__, url_prefix="/incidents")


@incidents_bp.route("")
def list_incidents():
    """Listado y filtro de la bitácora de incidentes y operaciones."""
    q = request.args.get("q", "").strip()
    severity = request.args.get("severity", "").strip()
    status = request.args.get("status", "").strip()
    server_id = request.args.get("server_id", type=int)

    with get_db() as session:
        query = session.query(IncidentLog)

        if q:
            query = query.filter(
                or_(
                    IncidentLog.ticket_ref.ilike(f"%{q}%"),
                    IncidentLog.title.ilike(f"%{q}%"),
                    IncidentLog.description.ilike(f"%{q}%"),
                    IncidentLog.root_cause.ilike(f"%{q}%"),
                    IncidentLog.operator_name.ilike(f"%{q}%")
                )
            )
        if severity:
            query = query.filter(IncidentLog.severity == severity)
        if status:
            query = query.filter(IncidentLog.status == status)
        if server_id:
            query = query.filter(IncidentLog.server_id == server_id)

        incidents = query.order_by(IncidentLog.occurred_at.desc()).all()
        servers = session.query(Server).order_by(Server.hostname.asc()).all()

        # Métricas de bitácora
        total_count = len(incidents)
        open_count = sum(1 for i in incidents if i.status in ["OPEN", "IN_PROGRESS"])
        resolved_count = sum(1 for i in incidents if i.status in ["RESOLVED", "CLOSED"])

        return render_template(
            "incidents/list.html",
            incidents=incidents,
            servers=servers,
            filters={"q": q, "severity": severity, "status": status, "server_id": server_id},
            stats={"total": total_count, "open": open_count, "resolved": resolved_count}
        )


@incidents_bp.route("/new", methods=["GET", "POST"])
def create_incident():
    """Registro de nuevo evento u operación en la bitácora."""
    with get_db() as session:
        if request.method == "POST":
            data = request.form
            
            occurred_at_str = data.get("occurred_at")
            if occurred_at_str:
                try:
                    occurred_at = datetime.fromisoformat(occurred_at_str)
                except ValueError:
                    occurred_at = datetime.now(timezone.utc)
            else:
                occurred_at = datetime.now(timezone.utc)

            incident = IncidentLog(
                ticket_ref=data.get("ticket_ref", "").strip() or None,
                title=data.get("title", "").strip(),
                description=data.get("description", "").strip(),
                severity=data.get("severity", "MEDIUM").strip(),
                status=data.get("status", "OPEN").strip(),
                actions_taken=data.get("actions_taken", "").strip() or None,
                root_cause=data.get("root_cause", "").strip() or None,
                resolution_steps=data.get("resolution_steps", "").strip() or None,
                operator_name=data.get("operator_name", "").strip() or "Sysadmin MDW",
                server_id=int(data["server_id"]) if data.get("server_id") else None,
                middleware_id=int(data["middleware_id"]) if data.get("middleware_id") else None,
                project_id=int(data["project_id"]) if data.get("project_id") else None,
                applied_runbook_id=int(data["applied_runbook_id"]) if data.get("applied_runbook_id") else None,
                occurred_at=occurred_at
            )
            session.add(incident)
            session.flush()

            # Registrar nota inicial en la línea de tiempo
            initial_note = IncidentTimelineEntry(
                incident_id=incident.id,
                operator_name=incident.operator_name,
                note=f"Apertura del incidente con severidad {incident.severity}.",
                status_at_time=incident.status
            )
            session.add(initial_note)
            session.flush()

            AuditService.log_change(
                session=session,
                entity_type="IncidentLog",
                entity_id=incident.id,
                action="CREATE",
                summary=f"Registro de incidente [{incident.severity}] {incident.title}",
                user_name=incident.operator_name,
                new_values=incident.to_dict(),
                ip_address=request.remote_addr
            )

            flash(f"Incidente '{incident.title}' registrado en bitácora.", "success")
            return redirect(url_for("incidents.view_incident", incident_id=incident.id))

        servers = session.query(Server).order_by(Server.hostname.asc()).all()
        middlewares = session.query(MiddlewareInstance).order_by(MiddlewareInstance.name.asc()).all()
        projects = session.query(Project).order_by(Project.name.asc()).all()
        runbooks = session.query(RunbookCommand).order_by(RunbookCommand.title.asc()).all()
        
        return render_template(
            "incidents/create.html", 
            servers=servers, 
            middlewares=middlewares, 
            projects=projects,
            runbooks=runbooks
        )


@incidents_bp.route("/<int:incident_id>")
def view_incident(incident_id: int):
    """Detalle completo del incidente, análisis de causa raíz, timeline de avances y resolución."""
    with get_db() as session:
        incident = session.query(IncidentLog).filter(IncidentLog.id == incident_id).first()
        if not incident:
            flash("Incidente no encontrado.", "danger")
            return redirect(url_for("incidents.list_incidents"))

        audit_history = session.query(AuditLog).filter(
            AuditLog.entity_type == "IncidentLog",
            AuditLog.entity_id == incident_id
        ).order_by(AuditLog.created_at.desc()).all()

        runbooks = session.query(RunbookCommand).order_by(RunbookCommand.title.asc()).all()

        return render_template(
            "incidents/view.html", 
            incident=incident, 
            audit_history=audit_history,
            runbooks=runbooks
        )


@incidents_bp.route("/<int:incident_id>/updates/new", methods=["POST"])
def add_timeline_update(incident_id: int):
    """Agrega una nota u observación intermedia al seguimiento del incidente."""
    with get_db() as session:
        incident = session.query(IncidentLog).filter(IncidentLog.id == incident_id).first()
        if not incident:
            flash("Incidente no encontrado.", "danger")
            return redirect(url_for("incidents.list_incidents"))

        note_text = request.form.get("note", "").strip()
        operator = request.form.get("operator_name", "").strip() or request.headers.get("X-User", "Sysadmin MDW")
        new_status = request.form.get("status", "").strip()

        if note_text:
            entry = IncidentTimelineEntry(
                incident_id=incident.id,
                operator_name=operator,
                note=note_text,
                status_at_time=new_status or incident.status
            )
            session.add(entry)

            # Si se especificó un cambio de estado en la nota de avance
            if new_status and new_status != incident.status:
                old_data = incident.to_dict()
                incident.status = new_status
                if new_status in ["RESOLVED", "CLOSED"] and not incident.resolved_at:
                    incident.resolved_at = datetime.now(timezone.utc)
                elif new_status in ["OPEN", "IN_PROGRESS"]:
                    incident.resolved_at = None

                session.flush()
                new_data = incident.to_dict()

                AuditService.log_change(
                    session=session,
                    entity_type="IncidentLog",
                    entity_id=incident.id,
                    action="UPDATE",
                    summary=f"Cambio de estado a {new_status} con avance operativo",
                    user_name=operator,
                    old_values=old_data,
                    new_values=new_data,
                    ip_address=request.remote_addr
                )

            flash("Avance registrado en la bitácora del incidente.", "info")

        return redirect(url_for("incidents.view_incident", incident_id=incident_id))


@incidents_bp.route("/<int:incident_id>/edit", methods=["GET", "POST"])
def edit_incident(incident_id: int):
    """Actualización del estado o resolución del incidente."""
    with get_db() as session:
        incident = session.query(IncidentLog).filter(IncidentLog.id == incident_id).first()
        if not incident:
            flash("Incidente no encontrado.", "danger")
            return redirect(url_for("incidents.list_incidents"))

        if request.method == "POST":
            old_data = incident.to_dict()
            data = request.form

            incident.ticket_ref = data.get("ticket_ref", "").strip() or None
            incident.title = data.get("title", incident.title).strip()
            incident.description = data.get("description", incident.description).strip()
            incident.severity = data.get("severity", incident.severity).strip()
            
            new_status = data.get("status", incident.status).strip()
            if new_status in ["RESOLVED", "CLOSED"] and incident.status not in ["RESOLVED", "CLOSED"]:
                incident.resolved_at = datetime.now(timezone.utc)
            elif new_status in ["OPEN", "IN_PROGRESS"]:
                incident.resolved_at = None
            incident.status = new_status

            incident.actions_taken = data.get("actions_taken", "").strip() or None
            incident.root_cause = data.get("root_cause", "").strip() or None
            incident.resolution_steps = data.get("resolution_steps", "").strip() or None
            incident.operator_name = data.get("operator_name", incident.operator_name).strip()
            incident.server_id = int(data["server_id"]) if data.get("server_id") else None
            incident.middleware_id = int(data["middleware_id"]) if data.get("middleware_id") else None
            incident.project_id = int(data["project_id"]) if data.get("project_id") else None
            incident.applied_runbook_id = int(data["applied_runbook_id"]) if data.get("applied_runbook_id") else None

            session.flush()
            new_data = incident.to_dict()

            diff = AuditService.calculate_diff(old_data, new_data)
            if diff:
                AuditService.log_change(
                    session=session,
                    entity_type="IncidentLog",
                    entity_id=incident.id,
                    action="UPDATE",
                    summary=f"Actualización de incidente #{incident.id} ({', '.join(diff.keys())})",
                    user_name=request.headers.get("X-User", incident.operator_name),
                    old_values=old_data,
                    new_values=new_data,
                    ip_address=request.remote_addr
                )

            flash(f"Incidente #{incident.id} actualizado correctamente.", "success")
            return redirect(url_for("incidents.view_incident", incident_id=incident.id))

        servers = session.query(Server).order_by(Server.hostname.asc()).all()
        middlewares = session.query(MiddlewareInstance).order_by(MiddlewareInstance.name.asc()).all()
        projects = session.query(Project).order_by(Project.name.asc()).all()
        runbooks = session.query(RunbookCommand).order_by(RunbookCommand.title.asc()).all()

        return render_template(
            "incidents/edit.html",
            incident=incident,
            servers=servers,
            middlewares=middlewares,
            projects=projects,
            runbooks=runbooks
        )


@incidents_bp.route("/<int:incident_id>/resolve", methods=["POST"])
def resolve_incident(incident_id: int):
    """Acción rápida para marcar un incidente como Resuelto."""
    with get_db() as session:
        incident = session.query(IncidentLog).filter(IncidentLog.id == incident_id).first()
        if not incident:
            flash("Incidente no encontrado.", "danger")
            return redirect(url_for("incidents.list_incidents"))

        old_data = incident.to_dict()
        incident.status = "RESOLVED"
        incident.resolved_at = datetime.now(timezone.utc)
        
        resolution_notes = request.form.get("resolution_notes", "").strip()
        if resolution_notes:
            incident.resolution_steps = resolution_notes

        applied_rb_id = request.form.get("applied_runbook_id")
        if applied_rb_id:
            incident.applied_runbook_id = int(applied_rb_id)

        session.flush()
        new_data = incident.to_dict()

        AuditService.log_change(
            session=session,
            entity_type="IncidentLog",
            entity_id=incident.id,
            action="UPDATE",
            summary=f"Incidente #{incident.id} marcado como RESUELTO",
            user_name=request.headers.get("X-User", "sysadmin"),
            old_values=old_data,
            new_values=new_data,
            ip_address=request.remote_addr
        )

        flash(f"Incidente #{incident.id} marcado como Resuelto.", "success")
        return redirect(url_for("incidents.view_incident", incident_id=incident.id))


# ==========================================
# EXPORTADORES DE BITÁCORA (CSV & JSON)
# ==========================================

@incidents_bp.route("/export/csv")
def export_csv():
    """Exporta todos los incidentes o filtrados a formato CSV (UTF-8 con BOM para Excel)."""
    with get_db() as session:
        incidents = session.query(IncidentLog).order_by(IncidentLog.occurred_at.desc()).all()

        output = io.StringIO()
        # UTF-8 BOM para apertura perfecta en Excel
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';')
        
        writer.writerow([
            "ID", "Ticket Ref", "Título", "Severidad", "Estado",
            "Servidor", "Middleware", "Proyecto", "Operador",
            "Fecha Ocurrencia", "Fecha Resolución", "Duración",
            "Causa Raíz", "Pasos Resolución"
        ])

        for i in incidents:
            writer.writerow([
                i.id,
                i.ticket_ref or "",
                i.title,
                i.severity,
                i.status,
                i.server.hostname if i.server else "",
                i.middleware.name if i.middleware else "",
                i.project.name if i.project else "",
                i.operator_name,
                i.occurred_at.strftime('%Y-%m-%d %H:%M:%S') if i.occurred_at else "",
                i.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if i.resolved_at else "",
                i.duration_display,
                i.root_cause or "",
                i.resolution_steps or ""
            ])

        output.seek(0)
        filename = f"bitacora_incidentes_mdw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )


@incidents_bp.route("/export/json")
def export_json():
    """Exporta la bitácora completa en formato JSON para integraciones externas."""
    with get_db() as session:
        incidents = session.query(IncidentLog).order_by(IncidentLog.occurred_at.desc()).all()
        data = [i.to_dict() for i in incidents]
        filename = f"bitacora_incidentes_mdw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return Response(
            jsonify(data).get_data(as_text=True),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
