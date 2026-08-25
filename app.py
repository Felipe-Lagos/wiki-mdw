import os
from app import create_app

# Crear la instancia de la aplicación Flask
app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    default_port = int(os.getenv("PORT", 5050))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ["true", "1", "yes"]
    
    ports_to_try = [default_port, 5050, 8080, 8000, 5001]
    started = False
    
    for p in ports_to_try:
        try:
            print(f"🚀 Iniciando Servidor Wiki-MDW en http://127.0.0.1:{p} (Debug: {debug})")
            app.run(host="0.0.0.0", port=p, debug=debug)
            started = True
            break
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"⚠️ Puerto {p} ocupado. Intentando siguiente puerto...")
                continue
            raise e
