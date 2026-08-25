import csv
import io
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, Response
from app.database import get_db
from app.models import AuditLog
from app.services.audit_service import AuditService

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.route("")
def list_audits():
    """Listado del log general de auditoría y control de cambios."""
    entity_type = request.args.get("entity_type", "").strip()
    action = request.args.get("action", "").strip()
    user_name = request.args.get("user_name", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    with get_db() as session:
        query = session.query(AuditLog)

        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if action:
            query = query.filter(AuditLog.action == action)
        if user_name:
            query = query.filter(AuditLog.user_name.ilike(f"%{user_name}%"))

        total_count = query.count()
        logs = (
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        entities = [r[0] for r in session.query(AuditLog.entity_type).distinct().all() if r[0]]
        actions = [r[0] for r in session.query(AuditLog.action).distinct().all() if r[0]]

        return render_template(
            "audit/list.html",
            logs=logs,
            entities=entities,
            actions=actions,
            filters={"entity_type": entity_type, "action": action, "user_name": user_name},
            page=page,
            total_pages=(total_count + per_page - 1) // per_page,
            total_count=total_count
        )


@audit_bp.route("/<int:audit_id>")
def view_audit(audit_id: int):
    """Retorna los detalles completos de una entrada de auditoría."""
    with get_db() as session:
        log = session.query(AuditLog).filter(AuditLog.id == audit_id).first()
        if not log:
            return jsonify({"error": "Audit log not found"}), 404

        return jsonify({
            "id": log.id,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "action": log.action,
            "user_name": log.user_name,
            "summary": log.summary,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat()
        })


@audit_bp.route("/<int:audit_id>/rollback", methods=["POST"])
def rollback_audit(audit_id: int):
    """
    Revierte una entidad al estado previo registrado en la auditoría (Rollback de versión).
    """
    with get_db() as session:
        user_name = request.headers.get("X-User", "sysadmin")
        success, message = AuditService.rollback_change(
            session=session,
            audit_id=audit_id,
            user_name=user_name,
            ip_address=request.remote_addr
        )

        if success:
            flash(message, "success")
        else:
            flash(f"Error al revertir cambio: {message}", "danger")

        # Redireccionar de vuelta a la página anterior o a auditoría
        referer = request.headers.get("Referer")
        if referer:
            return redirect(referer)
        return redirect(url_for("audit.list_audits"))


# ==========================================
# EXPORTADORES DE AUDITORÍA (CSV & JSON)
# ==========================================

@audit_bp.route("/export/csv")
def export_csv():
    """Exporta el historial de auditoría a CSV con UTF-8 BOM."""
    with get_db() as session:
        logs = session.query(AuditLog).order_by(AuditLog.created_at.desc()).all()

        output = io.StringIO()
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';')

        writer.writerow([
            "ID", "Fecha / Hora", "Acción", "Tipo Entidad",
            "ID Entidad", "Usuario", "IP Origen", "Resumen"
        ])

        for log in logs:
            writer.writerow([
                log.id,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                log.action,
                log.entity_type,
                log.entity_id,
                log.user_name,
                log.ip_address or "",
                log.summary
            ])

        output.seek(0)
        filename = f"auditoria_logs_mdw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )


@audit_bp.route("/export/json")
def export_json():
    """Exporta los registros de auditoría en JSON."""
    with get_db() as session:
        logs = session.query(AuditLog).order_by(AuditLog.created_at.desc()).all()
        data = [log.to_dict() for log in logs]
        filename = f"auditoria_logs_mdw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return Response(
            jsonify(data).get_data(as_text=True),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
