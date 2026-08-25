"""
Suite de Pruebas Automatizadas para la Fase 4 de Wiki-MDW:
Verifica la lógica avanzada de Bitácora (Timeline, MTTR, Runbooks vinculados) y 
el Control de Versiones / Auditoría con Reversión (Rollback) y Exportación.
"""
import unittest
from datetime import datetime, timezone, timedelta
from app import create_app
from app.database import init_db, get_db
from app.models import Server, MiddlewareInstance, RunbookCommand, IncidentLog, IncidentTimelineEntry, AuditLog
from app.services.audit_service import AuditService


class WikiMDWPhase4TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            init_db()

    def test_01_incident_lifecycle_and_timeline(self):
        """Verifica el ciclo de vida completo de un incidente y su línea de tiempo operativa."""
        with get_db() as session:
            # Limpiar datos previos si existen para idempotencia
            old_srv = session.query(Server).filter(Server.hostname == "srv-mq-phase4-test").first()
            if old_srv:
                session.query(IncidentLog).filter(IncidentLog.server_id == old_srv.id).delete()
                session.query(RunbookCommand).filter(RunbookCommand.server_id == old_srv.id).delete()
                session.delete(old_srv)
                session.commit()

            # 1. Crear servidor y runbook de prueba
            server = Server(
                hostname="srv-mq-phase4-test",
                ip_address="10.99.88.77",
                os_name="RHEL",
                environment="PROD",
                status="ACTIVE"
            )
            session.add(server)
            session.flush()

            runbook = RunbookCommand(
                title="Limpiar Colas MQ Bloqueadas",
                category="IBM MQ",
                command_text="strmqm QM_TEST && clear q(IN_QUEUE)",
                server_id=server.id
            )
            session.add(runbook)
            session.flush()

            server_id = server.id
            runbook_id = runbook.id

        # 2. Registrar incidente vía POST
        inc_data = {
            "ticket_ref": "INC-TEST-9999",
            "title": "Colas de pagos saturadas",
            "description": "El listener no procesa mensajes entrantes.",
            "severity": "HIGH",
            "status": "OPEN",
            "server_id": str(server_id),
            "applied_runbook_id": str(runbook_id),
            "operator_name": "Felipe Lagos"
        }
        res_create = self.client.post("/incidents/new", data=inc_data, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

        with get_db() as session:
            incident = session.query(IncidentLog).filter(IncidentLog.ticket_ref == "INC-TEST-9999").first()
            self.assertIsNotNone(incident)
            self.assertEqual(incident.severity, "HIGH")
            self.assertEqual(incident.applied_runbook_id, runbook_id)
            self.assertGreaterEqual(len(incident.timeline_updates), 1)
            incident_id = incident.id

        # 3. Agregar avance operacional en la línea de tiempo
        update_data = {
            "note": "Se contactó al equipo de infraestructura y se reinició el canal MQ.",
            "operator_name": "Carlos Gonzalez",
            "status": "IN_PROGRESS"
        }
        res_update = self.client.post(f"/incidents/{incident_id}/updates/new", data=update_data, follow_redirects=True)
        self.assertEqual(res_update.status_code, 200)

        with get_db() as session:
            inc_updated = session.query(IncidentLog).filter(IncidentLog.id == incident_id).first()
            self.assertEqual(inc_updated.status, "IN_PROGRESS")
            self.assertEqual(len(inc_updated.timeline_updates), 2)

        # 4. Marcar como Resuelto
        res_resolve = self.client.post(f"/incidents/{incident_id}/resolve", data={
            "resolution_notes": "Canal reactivado y colas drenadas exitosamente.",
            "applied_runbook_id": str(runbook_id)
        }, follow_redirects=True)
        self.assertEqual(res_resolve.status_code, 200)

        with get_db() as session:
            inc_resolved = session.query(IncidentLog).filter(IncidentLog.id == incident_id).first()
            self.assertEqual(inc_resolved.status, "RESOLVED")
            self.assertIsNotNone(inc_resolved.resolved_at)
            self.assertIn("Canal reactivado", inc_resolved.resolution_steps)
            print(f"✅ [OK] Ciclo de vida de incidente verificado (Duración: {inc_resolved.duration_display}).")

    def test_02_incident_export_csv_and_json(self):
        """Verifica la exportación de bitácora a CSV y JSON."""
        # CSV
        res_csv = self.client.get("/incidents/export/csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.content_type, "text/csv; charset=utf-8")
        self.assertIn("INC-TEST-9999", res_csv.get_data(as_text=True))

        # JSON
        res_json = self.client.get("/incidents/export/json")
        self.assertEqual(res_json.status_code, 200)
        data = res_json.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        print("✅ [OK] Exportadores de Bitácora (CSV con BOM y JSON) verificados.")

    def test_03_audit_diff_and_rollback(self):
        """Verifica el control de cambios, cálculo de diff y la reversión (Rollback) de una entidad."""
        with get_db() as session:
            old_target = session.query(Server).filter(Server.hostname == "srv-rollback-target").first()
            if old_target:
                session.query(AuditLog).filter(AuditLog.entity_type == "Server", AuditLog.entity_id == old_target.id).delete()
                session.delete(old_target)
                session.commit()

            # 1. Crear un servidor
            server = Server(
                hostname="srv-rollback-target",
                ip_address="10.55.66.77",
                os_name="Ubuntu",
                notes="Configuración Original v1"
            )
            session.add(server)
            session.flush()
            srv_id = server.id

            AuditService.log_change(
                session=session,
                entity_type="Server",
                entity_id=srv_id,
                action="CREATE",
                summary="Alta de servidor rollback",
                user_name="sysadmin",
                new_values=server.to_dict()
            )

        # 2. Modificar el servidor vía POST /servers/<id>/edit
        edit_data = {
            "hostname": "srv-rollback-target",
            "ip_address": "10.55.66.77",
            "os_name": "Ubuntu",
            "environment": "PROD",
            "status": "MAINTENANCE",
            "ssh_port": "2222",
            "notes": "Configuración Modificada Errónea v2"
        }
        res_edit = self.client.post(f"/servers/{srv_id}/edit", data=edit_data, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        # Verificar que la modificación generó auditoría con diff
        with get_db() as session:
            srv = session.query(Server).filter(Server.id == srv_id).first()
            self.assertEqual(srv.status, "MAINTENANCE")
            self.assertEqual(srv.ssh_port, 2222)

            last_audit = session.query(AuditLog).filter(
                AuditLog.entity_type == "Server",
                AuditLog.entity_id == srv_id,
                AuditLog.action == "UPDATE"
            ).order_by(AuditLog.id.desc()).first()

            self.assertIsNotNone(last_audit)
            self.assertIn("Configuración Original v1", str(last_audit.old_values))
            audit_to_rollback_id = last_audit.id

        # 3. Ejecutar ROLLBACK de la auditoría
        res_rollback = self.client.post(f"/audit/{audit_to_rollback_id}/rollback", follow_redirects=True)
        self.assertEqual(res_rollback.status_code, 200)

        # 4. Verificar que el servidor volvió al estado original y se registró auditoría ROLLBACK
        with get_db() as session:
            srv_restored = session.query(Server).filter(Server.id == srv_id).first()
            self.assertEqual(srv_restored.status, "ACTIVE")
            self.assertEqual(srv_restored.ssh_port, 22)
            self.assertEqual(srv_restored.notes, "Configuración Original v1")

            rollback_audit = session.query(AuditLog).filter(
                AuditLog.entity_type == "Server",
                AuditLog.entity_id == srv_id,
                AuditLog.action == "ROLLBACK"
            ).first()
            self.assertIsNotNone(rollback_audit)
            print(f"✅ [OK] Reversión de versión (Rollback) exitosa en Servidor #{srv_id}. Auditoría #{rollback_audit.id} creada.")

    def test_04_audit_export(self):
        """Verifica la exportación de logs de auditoría."""
        res_csv = self.client.get("/audit/export/csv")
        self.assertEqual(res_csv.status_code, 200)
        csv_text = res_csv.get_data(as_text=True)
        self.assertIn("ID;Fecha / Hora;Acción", csv_text)

        res_json = self.client.get("/audit/export/json")
        self.assertEqual(res_json.status_code, 200)
        data = res_json.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        print("✅ [OK] Exportador de Logs de Auditoría (CSV/JSON) verificado.")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 EJECUTANDO TEST SUITE DE FASE 4: BITÁCORA AVANZADA, AUDITORÍA Y ROLLBACK")
    print("=" * 70 + "\n")
    unittest.main()
