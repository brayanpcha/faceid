import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from datetime import datetime
import pandas as pd
from reportlab.pdfgen import canvas
from io import BytesIO
import threading
import time

# Cargar variables de entorno
load_dotenv()

# Configuración de la aplicación Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-123')

# Configuración de MongoDB Atlas (usando tu URI)
app.config["MONGO_URI"] = "mongodb+srv://andresbrayan285:fgPSZLu4c5lj8Dc1@cluster0.yhmkyqy.mongodb.net/stockmaster?retryWrites=true&w=majority"
mongo = PyMongo(app)

# Función para verificar la conexión a la base de datos
def check_db_connection():
    try:
        # Intenta listar las colecciones para verificar la conexión
        collections = mongo.db.list_collection_names()
        print("Conexión exitosa a MongoDB Atlas")
        print(f"Colecciones disponibles: {collections}")
        return True
    except Exception as e:
        print(f"Error al conectar a MongoDB Atlas: {e}")
        return False

# Verificar conexión al iniciar
if not check_db_connection():
    raise RuntimeError("No se pudo conectar a MongoDB Atlas. Verifica tu URI y conexión a internet.")

# Sincronización de usuarios (ejemplo básico)
def sync_users():
    while True:
        try:
            # Aquí iría la lógica de sincronización entre bases de datos
            print("Sincronización de usuarios ejecutada:", datetime.now())
            time.sleep(60)  # Sincronizar cada 60 segundos
        except Exception as e:
            print(f"Error en sincronización: {e}")

# Iniciar hilo de sincronización en segundo plano
sync_thread = threading.Thread(target=sync_users, daemon=True)
sync_thread.start()

# Rutas de la aplicación
@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Datos para el dashboard
    dashboard_data = {
        'total_products': mongo.db.products.count_documents({}),
        'low_stock_products': mongo.db.products.count_documents({'stock': {'$lt': 5}}),
        'today_sales': 0,  # Actualizar con tu lógica de ventas
        'total_customers': mongo.db.customers.count_documents({}) if 'customers' in mongo.db.list_collection_names() else 0
    }
    
    return render_template('dashboard.html', **dashboard_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = mongo.db.users.find_one({'username': username})
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['role'] = user.get('role', 'user')
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# CRUD de Productos
@app.route('/products')
def products():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    products = list(mongo.db.products.find())
    return render_template('products.html', products=products)

@app.route('/add_product', methods=['POST'])
def add_product():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        product = {
            'name': request.form['name'],
            'description': request.form['description'],
            'price': float(request.form['price']),
            'stock': int(request.form['stock']),
            'category': request.form['category'],
            'created_at': datetime.now()
        }
        
        mongo.db.products.insert_one(product)
        return redirect(url_for('products'))
    except Exception as e:
        return render_template('error.html', error=f"Error al agregar producto: {e}")

@app.route('/update_product/<product_id>', methods=['POST'])
def update_product(product_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        mongo.db.products.update_one(
            {'_id': ObjectId(product_id)},
            {'$set': {
                'name': request.form['name'],
                'description': request.form['description'],
                'price': float(request.form['price']),
                'stock': int(request.form['stock']),
                'category': request.form['category'],
                'updated_at': datetime.now()
            }}
        )
        return redirect(url_for('products'))
    except Exception as e:
        return render_template('error.html', error=f"Error al actualizar producto: {e}")

@app.route('/delete_product/<product_id>')
def delete_product(product_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        mongo.db.products.delete_one({'_id': ObjectId(product_id)})
        return redirect(url_for('products'))
    except Exception as e:
        return render_template('error.html', error=f"Error al eliminar producto: {e}")

# Generación de Reportes
@app.route('/report/products/excel')
def report_products_excel():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        products = list(mongo.db.products.find())
        df = pd.DataFrame(products)
        
        # Eliminar la columna _id
        if '_id' in df.columns:
            df.drop('_id', axis=1, inplace=True)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Productos', index=False)
        
        output.seek(0)
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment;filename=productos.xlsx"}
        )
    except Exception as e:
        return render_template('error.html', error=f"Error al generar reporte Excel: {e}")

@app.route('/report/products/pdf')
def report_products_pdf():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        products = list(mongo.db.products.find())
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        
        # Encabezado del reporte
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 800, "Reporte de Productos - StockMaster")
        p.setFont("Helvetica", 12)
        p.drawString(100, 780, f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        p.drawString(100, 760, f"Total de productos: {len(products)}")
        
        # Detalles de productos
        y = 730
        p.setFont("Helvetica-Bold", 12)
        p.drawString(100, y, "Nombre")
        p.drawString(300, y, "Stock")
        p.drawString(400, y, "Precio")
        
        y -= 20
        p.setFont("Helvetica", 10)
        for product in products:
            p.drawString(100, y, product['name'][:30])  # Limitar a 30 caracteres
            p.drawString(300, y, str(product['stock']))
            p.drawString(400, y, f"${product['price']:.2f}")
            y -= 15
            if y < 50:  # Nueva página si queda poco espacio
                p.showPage()
                y = 800
        
        p.save()
        buffer.seek(0)
        
        return Response(
            buffer,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment;filename=productos.pdf'}
        )
    except Exception as e:
        return render_template('error.html', error=f"Error al generar reporte PDF: {e}")

# API para el dashboard
@app.route('/api/dashboard')
def api_dashboard():
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    data = {
        'total_products': mongo.db.products.count_documents({}),
        'low_stock_products': mongo.db.products.count_documents({'stock': {'$lt': 5}}),
        'today_sales': 0,  # Actualizar con tu lógica de ventas
        'total_customers': mongo.db.customers.count_documents({}) if 'customers' in mongo.db.list_collection_names() else 0
    }
    
    return jsonify(data)

# Manejo de errores
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error='Página no encontrada'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error='Error interno del servidor'), 500

if __name__ == '__main__':
    # Crear usuario admin inicial si no existe
    if not mongo.db.users.find_one({'username': 'admin'}):
        mongo.db.users.insert_one({
            'username': 'admin',
            'password': generate_password_hash('admin123'),
            'role': 'admin',
            'created_at': datetime.now()
        })
        print("Usuario admin creado: admin/admin123")
    
    app.run(debug=True, host='0.0.0.0', port=5000)