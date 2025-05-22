from pymongo import MongoClient
import threading
import time
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

class UserSynchronizer:
    def __init__(self):
        # Configuración de conexiones
        self.atlas_uri = os.getenv('MONGO_URI_ATLAS', 'mongodb+srv://user:password@cluster0.mongodb.net/stockmaster?retryWrites=true&w=majority')
        self.local_uri = 'mongodb://localhost:27017/'
        
        # Conexión a las bases de datos
        self.client_atlas = MongoClient(self.atlas_uri)
        self.client_local = MongoClient(self.local_uri)
        
        self.db_atlas = self.client_atlas.get_database()
        self.db_local = self.client_local['stockmaster_local']
        
        self.sync_interval = 60  # segundos
        self.running = False

    def sync_databases(self):
        """Sincroniza usuarios en ambas direcciones"""
        try:
            # Registro de sincronización
            sync_time = datetime.now()
            print(f"\nIniciando sincronización: {sync_time}")
            
            # Atlas → Local
            atlas_users = list(self.db_atlas.users.find())
            local_count = 0
            for user in atlas_users:
                result = self.db_local.users.update_one(
                    {'username': user['username']},
                    {'$set': {
                        'username': user['username'],
                        'password': user['password'],
                        'role': user.get('role', 'user'),
                        'last_sync': sync_time
                    }},
                    upsert=True
                )
                if result.upserted_id or result.modified_count > 0:
                    local_count += 1
            
            # Local → Atlas
            local_users = list(self.db_local.users.find())
            atlas_count = 0
            for user in local_users:
                result = self.db_atlas.users.update_one(
                    {'username': user['username']},
                    {'$set': {
                        'username': user['username'],
                        'password': user['password'],
                        'role': user.get('role', 'user'),
                        'last_sync': sync_time
                    }},
                    upsert=True
                )
                if result.upserted_id or result.modified_count > 0:
                    atlas_count += 1
            
            print(f"Sincronización completada. Actualizados: {local_count} local, {atlas_count} Atlas")
            
            # Limpieza de usuarios eliminados (opcional)
            # self.clean_deleted_users()
            
        except Exception as e:
            print(f"Error durante la sincronización: {str(e)}")

    def clean_deleted_users(self):
        """Elimina usuarios que no existen en la otra base de datos"""
        atlas_usernames = {u['username'] for u in self.db_atlas.users.find()}
        local_usernames = {u['username'] for u in self.db_local.users.find()}
        
        # Usuarios solo en local
        only_local = local_usernames - atlas_usernames
        if only_local:
            self.db_local.users.delete_many({'username': {'$in': list(only_local)}})
            print(f"Eliminados {len(only_local)} usuarios solo en local")
        
        # Usuarios solo en Atlas
        only_atlas = atlas_usernames - local_usernames
        if only_atlas:
            self.db_atlas.users.delete_many({'username': {'$in': list(only_atlas)}})
            print(f"Eliminados {len(only_atlas)} usuarios solo en Atlas")

    def start(self):
        """Inicia el servicio de sincronización"""
        self.running = True
        print("Servicio de sincronización iniciado")
        while self.running:
            self.sync_databases()
            time.sleep(self.sync_interval)

    def stop(self):
        """Detiene el servicio"""
        self.running = False
        print("Servicio de sincronización detenido")

if __name__ == '__main__':
    # Ejemplo de uso
    synchronizer = UserSynchronizer()
    
    try:
        # Ejecutar en primer plano para desarrollo
        synchronizer.start()
    except KeyboardInterrupt:
        synchronizer.stop()
    finally:
        synchronizer.client_atlas.close()
        synchronizer.client_local.close()