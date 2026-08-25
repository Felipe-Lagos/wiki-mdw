from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from sqlalchemy import or_
from app.database import get_db
from app.models import RunbookCommand, Server, MiddlewareInstance, AuditLog
from app.services.audit_service import AuditService

runbooks_bp = Blueprint("runbooks", __name__, url_prefix="/runbooks")


@runbooks_bp.route("")
def list_runbooks():
    """Listado y búsqueda de Corta-Palos y procedimientos operativos."""
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    server_id = request.args.get("server_id", type=int)
    is_dangerous = request.args.get("is_dangerous")
    
    with get_db() as session:
        query = session.query(RunbookCommand)
        
        if q:
            query = query.filter(
                or_(
                    RunbookCommand.title.ilike(f"%{q}%"),
                    RunbookCommand.description.ilike(f"%{q}%"),
                    RunbookCommand.command_text.ilike(f"%{q}%"),
                    RunbookCommand.category.ilike(f"%{q}%")
                )
            )
        if category:
            query = query.filter(RunbookCommand.category == category)
        if server_id:
            query = query.filter(RunbookCommand.server_id == server_id)
        if is_dangerous in ["1", "true", "True"]:
            query = query.filter(RunbookCommand.is_dangerous == True)  # noqa: E712

        runbooks = query.order_by(RunbookCommand.category.asc(), RunbookCommand.execution_order.asc()).all()
        
        # Categorías disponibles para filtros
        categories = [r[0] for r in session.query(RunbookCommand.category).distinct().all() if r[0]]
        servers = session.query(Server).order_by(Server.hostname.asc()).all()

        return render_template(
            "runbooks/list.html",
            runbooks=runbooks,
            categories=categories,
            servers=servers,
            filters={"q": q, "category": category, "server_id": server_id, "is_dangerous": is_dangerous}
        )


@runbooks_bp.route("/new", methods=["GET", "POST"])
def create_runbook():
    """Alta de nuevo comando o procedimiento en el Corta-Palos."""
    with get_db() as session:
        if request.method == "POST":
            data = request.form
            runbook = RunbookCommand(
                title=data.get("title", "").strip(),
                category=data.get("category", "General").strip(),
                description=data.get("description", "").strip() or None,
                command_text=data.get("command_text", "").strip(),
                execution_order=int(data.get("execution_order", 1)),
                is_dangerous=True if data.get("is_dangerous") else False,
                requires_sudo=True if data.get("requires_sudo") else False,
                created_by=request.headers.get("X-User", "sysadmin"),
                server_id=int(data["server_id"]) if data.get("server_id") else None,
                middleware_id=int(data["middleware_id"]) if data.get("middleware_id") else None
            )
            session.add(runbook)
            session.flush()

            AuditService.log_change(
                session=session,
                entity_type="RunbookCommand",
                entity_id=runbook.id,
                action="CREATE",
                summary=f"Nuevo corta-palos: [{runbook.category}] {runbook.title}",
                user_name=request.headers.get("X-User", "sysadmin"),
                new_values=runbook.to_dict(),
                ip_address=request.remote_addr
            )

            flash(f"Corta-palos '{runbook.title}' registrado exitosamente.", "success")
            return redirect(url_for("runbooks.list_runbooks"))

        servers = session.query(Server).order_by(Server.hostname.asc()).all()
        middlewares = session.query(MiddlewareInstance).order_by(MiddlewareInstance.name.asc()).all()
        return render_template("runbooks/create.html", servers=servers, middlewares=middlewares)


@runbooks_bp.route("/<int:runbook_id>")
def view_runbook(runbook_id: int):
    """Detalle de un comando o procedimiento específico."""
    with get_db() as session:
        runbook = session.query(RunbookCommand).filter(RunbookCommand.id == runbook_id).first()
        if not runbook:
            flash("Corta-palos no encontrado.", "danger")
            return redirect(url_for("runbooks.list_runbooks"))

        audit_history = session.query(AuditLog).filter(
            AuditLog.entity_type == "RunbookCommand",
            AuditLog.entity_id == runbook_id
        ).order_by(AuditLog.created_at.desc()).all()

        return render_template("runbooks/view.html", runbook=runbook, audit_history=audit_history)


@runbooks_bp.route("/<int:runbook_id>/edit", methods=["GET", "POST"])
def edit_runbook(runbook_id: int):
    """Edición de un procedimiento corta-palos con registro de auditoría."""
    with get_db() as session:
        runbook = session.query(RunbookCommand).filter(RunbookCommand.id == runbook_id).first()
        if not runbook:
            flash("Corta-palos no encontrado.", "danger")
            return redirect(url_for("runbooks.list_runbooks"))

        if request.method == "POST":
            old_data = runbook.to_dict()
            data = request.form

            runbook.title = data.get("title", runbook.title).strip()
            runbook.category = data.get("category", runbook.category).strip()
            runbook.description = data.get("description", "").strip() or None
            runbook.command_text = data.get("command_text", runbook.command_text).strip()
            runbook.execution_order = int(data.get("execution_order", 1))
            runbook.is_dangerous = True if data.get("is_dangerous") else False
            runbook.requires_sudo = True if data.get("requires_sudo") else False
            runbook.server_id = int(data["server_id"]) if data.get("server_id") else None
            runbook.middleware_id = int(data["middleware_id"]) if data.get("middleware_id") else None

            session.flush()
            new_data = runbook.to_dict()

            diff = AuditService.calculate_diff(old_data, new_data)
            if diff:
                AuditService.log_change(
                    session=session,
                    entity_type="RunbookCommand",
                    entity_id=runbook.id,
                    action="UPDATE",
                    summary=f"Actualización en corta-palos {runbook.title} ({', '.join(diff.keys())})",
                    user_name=request.headers.get("X-User", "sysadmin"),
                    old_values=old_data,
                    new_values=new_data,
                    ip_address=request.remote_addr
                )

            flash(f"Corta-palos '{runbook.title}' actualizado.", "success")
            return redirect(url_for("runbooks.view_runbook", runbook_id=runbook.id))

        servers = session.query(Server).order_by(Server.hostname.asc()).all()
        middlewares = session.query(MiddlewareInstance).order_by(MiddlewareInstance.name.asc()).all()
        return render_template("runbooks/edit.html", runbook=runbook, servers=servers, middlewares=middlewares)


@runbooks_bp.route("/<int:runbook_id>/delete", methods=["POST"])
def delete_runbook(runbook_id: int):
    """Eliminación de procedimiento con log de auditoría."""
    with get_db() as session:
        runbook = session.query(RunbookCommand).filter(RunbookCommand.id == runbook_id).first()
        if not runbook:
            flash("Corta-palos no encontrado.", "danger")
            return redirect(url_for("runbooks.list_runbooks"))

        title = runbook.title
        old_data = runbook.to_dict()
        session.delete(runbook)
        session.flush()

        AuditService.log_change(
            session=session,
            entity_type="RunbookCommand",
            entity_id=runbook_id,
            action="DELETE",
            summary=f"Eliminación de corta-palos: {title}",
            user_name=request.headers.get("X-User", "sysadmin"),
            old_values=old_data,
            ip_address=request.remote_addr
        )

        flash(f"Corta-palos '{title}' eliminado.", "warning")
        return redirect(url_for("runbooks.list_runbooks"))
