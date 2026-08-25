"""
Suite de Pruebas Automatizadas para la Fase 3 de Wiki-MDW:
Verifica que todas las plantillas HTML se rendericen correctamente con Jinja2 en modo Dark Theme.
"""
import unittest
from app import create_app
from app.database import init_db


class WikiMDWTemplatesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app("testing")
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            init_db()

    def test_01_render_dashboard(self):
        """Verifica renderizado del Dashboard con tema oscuro."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Dashboard de Middleware", res.data)
        self.assertIn(b"data-bs-theme=\"dark\"", res.data)
        print("✅ [Render OK] / (Dashboard HTML)")

    def test_02_render_servers_views(self):
        """Verifica renderizado de lista, detalle y creación de Servidores."""
        # Lista
        res_list = self.client.get("/servers")
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(b"Inventario de Servidores", res_list.data)

        # Formulario de creación
        res_new = self.client.get("/servers/new")
        self.assertEqual(res_new.status_code, 200)
        self.assertIn(b"Alta de Servidor", res_new.data)
        print("✅ [Render OK] /servers y /servers/new (Servidores HTML)")

    def test_03_render_runbooks_views(self):
        """Verifica renderizado de Corta-Palos."""
        res_list = self.client.get("/runbooks")
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(b"Corta-Palos (Runbooks)", res_list.data)

        res_new = self.client.get("/runbooks/new")
        self.assertEqual(res_new.status_code, 200)
        self.assertIn(b"Alta de Corta-Palos", res_new.data)
        print("✅ [Render OK] /runbooks y /runbooks/new (Corta-Palos HTML)")

    def test_04_render_incidents_views(self):
        """Verifica renderizado de Bitácora de Incidentes."""
        res_list = self.client.get("/incidents")
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(b"Bit\xc3\xa1cora de Incidentes", res_list.data)

        res_new = self.client.get("/incidents/new")
        self.assertEqual(res_new.status_code, 200)
        self.assertIn(b"Nuevo Registro en Bit\xc3\xa1cora", res_new.data)
        print("✅ [Render OK] /incidents y /incidents/new (Bitácora HTML)")

    def test_05_render_projects_and_audit(self):
        """Verifica renderizado de Proyectos y Logs de Auditoría."""
        res_proj = self.client.get("/projects")
        self.assertEqual(res_proj.status_code, 200)
        self.assertIn(b"Proyectos y Aplicaciones", res_proj.data)

        res_audit = self.client.get("/audit")
        self.assertEqual(res_audit.status_code, 200)
        self.assertIn(b"Logs de Auditor\xc3\xada", res_audit.data)
        print("✅ [Render OK] /projects y /audit (Proyectos y Auditoría HTML)")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 EJECUTANDO TEST SUITE DE FASE 3: PLANTILLAS HTML Y UI DARK MODE")
    print("=" * 70 + "\n")
    unittest.main()
