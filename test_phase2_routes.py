"""
Suite de Pruebas Automatizadas para la Fase 2 de Wiki-MDW:
Verifica el correcto funcionamiento de la fábrica Flask, Blueprints y Rutas.
"""
import unittest
from app import create_app
from app.database import init_db, get_db
from app.models import Server, AuditLog


class WikiMDWRoutesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            init_db()

    def test_01_health_check(self):
        """Verifica el endpoint de salud /health"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "UP")
        self.assertEqual(data["service"], "Wiki-MDW")
        print("✅ [200 OK] /health verificado.")

    def test_02_dashboard_route(self):
        """Verifica la ruta principal /"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        print("✅ [200 OK] / (Dashboard) verificado.")

    def test_03_servers_routes(self):
        """Verifica listado, creación y validación de duplicados de servidores."""
        # Limpiar registro previo si existiera para garantizar idempotencia
        with get_db() as session:
            existing = session.query(Server).filter(Server.hostname == "srv-jboss-test01").first()
            if existing:
                session.query(AuditLog).filter(AuditLog.entity_type == "Server", AuditLog.entity_id == existing.id).delete()
                session.delete(existing)
                session.commit()

        # 1. Listado
        response = self.client.get("/servers")
        self.assertEqual(response.status_code, 200)

        # 2. Creación exitosa
        post_data = {
            "hostname": "srv-jboss-test01",
            "ip_address": "10.30.40.50",
            "os_name": "Red Hat Enterprise Linux",
            "os_version": "9.2",
            "environment": "DEV",
            "status": "ACTIVE",
            "cpu_cores": "4",
            "ram_gb": "16",
            "notes": "Servidor de pruebas JBoss creado desde test"
        }
        res_create = self.client.post("/servers/new", data=post_data, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

        # 3. Verificar en BD y Auditoría
        with get_db() as session:
            server = session.query(Server).filter(Server.hostname == "srv-jboss-test01").first()
            self.assertIsNotNone(server)
            self.assertEqual(server.ip_address, "10.30.40.50")

            audit = session.query(AuditLog).filter(
                AuditLog.entity_type == "Server",
                AuditLog.entity_id == server.id,
                AuditLog.action == "CREATE"
            ).first()
            self.assertIsNotNone(audit)

        # 4. Verificar control de duplicados (debe retornar 400 sin romper la aplicación)
        res_duplicate = self.client.post("/servers/new", data=post_data, follow_redirects=False)
        self.assertEqual(res_duplicate.status_code, 400)
        print(f"✅ [200 OK] /servers, POST /servers/new y validación de duplicados (400) verificados.")

    def test_04_projects_routes(self):
        """Verifica listado de proyectos."""
        response = self.client.get("/projects")
        self.assertEqual(response.status_code, 200)
        print("✅ [200 OK] /projects verificado.")

    def test_05_runbooks_routes(self):
        """Verifica listado de corta-palos."""
        response = self.client.get("/runbooks")
        self.assertEqual(response.status_code, 200)
        print("✅ [200 OK] /runbooks verificado.")

    def test_06_incidents_routes(self):
        """Verifica listado de incidentes / bitácora."""
        response = self.client.get("/incidents")
        self.assertEqual(response.status_code, 200)
        print("✅ [200 OK] /incidents verificado.")

    def test_07_audit_routes(self):
        """Verifica visor de auditoría."""
        response = self.client.get("/audit")
        self.assertEqual(response.status_code, 200)
        print("✅ [200 OK] /audit verificado.")

    def test_08_api_search_and_stats(self):
        """Verifica endpoints REST de búsqueda y estadísticas."""
        # Stats
        res_stats = self.client.get("/api/v1/stats")
        self.assertEqual(res_stats.status_code, 200)
        data = res_stats.get_json()
        self.assertIn("servers", data)
        self.assertIn("middlewares", data)
        self.assertIn("incidents_open", data)

        # Búsqueda
        res_search = self.client.get("/api/v1/search?q=jboss")
        self.assertEqual(res_search.status_code, 200)
        search_data = res_search.get_json()
        self.assertGreaterEqual(search_data["count"], 1)
        print(f"✅ [200 OK] /api/v1/stats y /api/v1/search verificados (Búsqueda 'jboss': {search_data['count']} resultados).")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 EJECUTANDO TEST SUITE DE FASE 2: RUTAS Y CONTROLADORES FLASK")
    print("=" * 70 + "\n")
    unittest.main()
