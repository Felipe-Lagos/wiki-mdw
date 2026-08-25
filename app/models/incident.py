from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class IncidentLog(BaseModel):
    """
    Bitácora de Incidentes, Mantenimientos y Operaciones.
    Permite a los administradores registrar eventos y su solución histórica.
    """
    __tablename__ = "incidents"

    ticket_ref = Column(String(50), nullable=True, index=True)  # Ej: 'INC-2026-0819', 'CHG-9941'
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    
    severity = Column(String(20), default="MEDIUM", nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    status = Column(String(20), default="OPEN", nullable=False, index=True)      # OPEN, IN_PROGRESS, RESOLVED, CLOSED
    
    actions_taken = Column(Text, nullable=True)     # Pasos operativos ejecutados durante el incidente
    root_cause = Column(Text, nullable=True)        # Causa raíz detectada
    resolution_steps = Column(Text, nullable=True)  # Solución final / recomendación preventiva
    
    operator_name = Column(String(100), nullable=False, index=True)  # Sysadmin responsable
    occurred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)

    # Entidades afectadas
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True)
    middleware_id = Column(Integer, ForeignKey("middlewares.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    applied_runbook_id = Column(Integer, ForeignKey("runbooks.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relaciones
    server = relationship("Server", back_populates="incidents")
    middleware = relationship("MiddlewareInstance", back_populates="incidents")
    project = relationship("Project", back_populates="incidents")
    applied_runbook = relationship("RunbookCommand")
    timeline_updates = relationship("IncidentTimelineEntry", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentTimelineEntry.created_at.asc()")

    @property
    def duration_display(self) -> str:
        """Calcula de forma legible el tiempo transcurrido o la duración total del incidente."""
        end_time = self.resolved_at or datetime.now(timezone.utc)
        start_time = self.occurred_at
        
        # Asegurar compatibilidad de timezones en SQLite
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        diff = end_time - start_time
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0:
            total_seconds = 0

        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if hours > 0:
            formatted = f"{hours}h {minutes}m"
        else:
            formatted = f"{minutes} min"

        if not self.resolved_at:
            return f"Activo ({formatted})"
        return formatted

    def __repr__(self):
        return f"<Incident [{self.severity}] {self.ticket_ref or '#' + str(self.id)}: {self.title}>"


class IncidentTimelineEntry(BaseModel):
    """
    Seguimiento cronológico y notas operativas intermedias durante la atención de un incidente.
    """
    __tablename__ = "incident_timeline"

    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_name = Column(String(100), nullable=False)
    note = Column(Text, nullable=False)
    status_at_time = Column(String(20), nullable=True)

    incident = relationship("IncidentLog", back_populates="timeline_updates")

    def __repr__(self):
        return f"<TimelineEntry #{self.id} for Incident #{self.incident_id}>"
