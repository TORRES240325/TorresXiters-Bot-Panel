import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session as flask_session, flash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_models import Usuario, Producto, Key, inicializar_db, get_session
from functools import wraps
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///socios_bot.db') 

app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('SECRET_KEY', 'tu_clave_secreta_final_torres') 

try:
    engine = create_engine(DATABASE_URL)
    inicializar_db(engine)
except Exception as e:
    logging.error(f"Error CRÍTICO al inicializar la base de datos: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in flask_session:
            flash('Debes iniciar sesión para acceder a esta página.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        login_key_input = request.form.get('login_key') or request.form.get('password')

        db_session = get_session()
        try:
            usuario = db_session.query(Usuario).filter_by(
                username=username, 
                login_key=login_key_input, 
                es_admin=True
            ).first()

            if usuario:
                flask_session['logged_in'] = True
                flask_session['username'] = usuario.username
                flash('Inicio de sesión exitoso.', 'success')
                return redirect(url_for('manage_users')) 
            else:
                flash('Credenciales incorrectas o no eres administrador.', 'danger')
        finally:
            db_session.close()
    return render_template('login.html') 

@app.route('/logout')
def logout():
    flask_session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/users')
@app.route('/manage_users')
@login_required
def manage_users():
    db_session = get_session()
    try:
        usuarios = db_session.query(Usuario).all()
        if len(usuarios) > 1:
            usuarios = [u for u in usuarios if u.username != 'admin']
        return render_template('admin_users.html', usuarios=usuarios)
    finally:
        db_session.close()

@app.route('/adjust_saldo/<int:user_id>', methods=['GET', 'POST'])
@login_required
def adjust_saldo(user_id):
    db_session = get_session()
    try:
        usuario = db_session.query(Usuario).filter_by(id=user_id).first()
        if not usuario:
            flash('Usuario no encontrado.', 'danger')
            return redirect(url_for('manage_users'))

        if request.method == 'POST':
            try:
                monto = float(request.form.get('monto'))
                usuario.saldo += monto
                db_session.commit()
                flash(f'Saldo de {usuario.username} ajustado en ${monto:.2f}. Nuevo saldo: ${usuario.saldo:.2f}.', 'success')
                return redirect(url_for('manage_users'))
            except ValueError:
                flash('Monto inválido.', 'danger')
            except Exception as e:
                db_session.rollback()
                flash(f'Error al ajustar saldo: {e}', 'danger')
        
        return render_template('adjust_saldo.html', usuario=usuario)
    finally:
        db_session.close()

@app.route('/products')
@app.route('/manage_products')
@login_required
def manage_products():
    db_session = get_session()
    try:
        productos = db_session.query(Producto).all()
        for p in productos:
            p.stock_available = db_session.query(Key).filter(Key.producto_id == p.id, Key.estado == 'available').count()
        return render_template('manage_products.html', productos=productos)
    finally:
        db_session.close()

@app.route('/create_product', methods=['GET', 'POST'])
@login_required
def create_product():
    db_session = get_session()
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        categoria = request.form.get('categoria')
        precio = float(request.form.get('precio', 0.00))
        descripcion = request.form.get('descripcion')
        
        try:
            nuevo_producto = Producto(nombre=nombre, categoria=categoria, precio=precio, descripcion=descripcion)
            db_session.add(nuevo_producto)
            db_session.commit()
            flash(f'Producto "{nombre}" creado exitosamente.', 'success')
            return redirect(url_for('manage_products'))
        except Exception as e:
            db_session.rollback()
            flash(f'Error al crear producto: {e}', 'danger')
        finally:
            db_session.close()
    return render_template('create_product.html')

@app.route('/product/<int:product_id>/keys', methods=['GET', 'POST'])
@login_required
def manage_keys(product_id):
    db_session = get_session()
    try:
        producto = db_session.query(Producto).filter_by(id=product_id).first()
        if not producto:
            flash('Producto no encontrado.', 'danger')
            return redirect(url_for('manage_products'))

        if request.method == 'POST':
            licencias_text = request.form.get('licencias')
            lines = [line.strip() for line in licencias_text.split('\n') if line.strip()]
            
            count = 0
            for line in lines:
                nueva_key = Key(licencia=line, producto_id=product_id, estado='available')
                db_session.add(nueva_key)
                count += 1
                
            db_session.commit()
            flash(f'Se agregaron {count} keys al inventario de {producto.nombre}.', 'success')
            return redirect(url_for('manage_keys', product_id=product_id))

        available_keys = db_session.query(Key).filter_by(producto_id=product_id, estado='available').all()
        used_keys = db_session.query(Key).filter_by(producto_id=product_id, estado='used').all()
        
        return render_template('manage_keys.html', producto=producto, available_keys=available_keys, used_keys=used_keys)
    finally:
        db_session.close()
        
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    db_session = get_session()
    try:
        producto = db_session.query(Producto).filter_by(id=product_id).first()
        if not producto:
            flash('Producto no encontrado.', 'danger')
            return redirect(url_for('manage_products'))

        if request.method == 'POST':
            producto.nombre = request.form.get('nombre')
            producto.categoria = request.form.get('categoria')
            producto.precio = float(request.form.get('precio'))
            producto.descripcion = request.form.get('descripcion')
            
            db_session.commit()
            flash(f'Producto "{producto.nombre}" actualizado exitosamente.', 'success')
            return redirect(url_for('manage_products'))
        return render_template('edit_product.html', producto=producto)
    except Exception as e:
        db_session.rollback()
        flash(f'Error al editar producto: {e}', 'danger')
        return redirect(url_for('manage_products'))
    finally:
        db_session.close()

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    db_session = get_session()
    try:
        producto = db_session.query(Producto).filter_by(id=product_id).first()
        if producto:
            db_session.query(Key).filter_by(producto_id=product_id).delete()
            db_session.delete(producto)
            db_session.commit()
            flash(f'Producto "{producto.nombre}" y sus Keys eliminados exitosamente.', 'success')
        else:
            flash('Producto no encontrado.', 'danger')
    finally:
        db_session.close()
    return redirect(url_for('manage_products'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)